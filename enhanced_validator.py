#!/usr/bin/env python3
"""
Enhanced Validator for Project ALPHA EVOLVE
Improved AI validation with scientific context and better error handling.
"""

import os
import random
import re
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
import argparse
import sys
from typing import Dict, Any, Optional
import numpy as np

# Import advanced metrics
try:
    from advanced_oct_metrics import AdvancedOCTMetrics
    ADVANCED_METRICS_AVAILABLE = True
except ImportError:
    print("WARNING: advanced_oct_metrics not available, skipping advanced metrics")
    ADVANCED_METRICS_AVAILABLE = False
    AdvancedOCTMetrics = None

# --- API SETUP ---
try:
    from load_api_key import get_api_key

    GOOGLE_API_KEY = get_api_key()
    if not GOOGLE_API_KEY:
        raise ValueError(
            "Gemini API key not set. Copy env.example to .env and set GEMINI_API_KEY."
        )
    genai.configure(api_key=GOOGLE_API_KEY)

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    generation_config = genai.GenerationConfig(
        temperature=0.0,
        top_p=0.1,
        max_output_tokens=8192,
        response_mime_type="application/json"
    )

    llm_model = genai.GenerativeModel(
        'gemini-3-pro-preview',
        generation_config=generation_config,
        safety_settings=safety_settings
    )
except Exception as e:
    print(f"!!! CRITICAL ERROR setting up Gemini: {e}", file=sys.stderr)
    llm_model = None

# --- Define the standard target size for all images ---
TARGET_SIZE = (1024, 1024)

# --- Load validator prompt configuration ---
def load_validator_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load validator prompt configuration from JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent / "agent_configs" / "validator_prompt_config.json"
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✓ Loaded validator config from: {config_path}")
        return config
    except FileNotFoundError:
        print(f"WARNING: Config file not found at {config_path}, using default prompts")
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in config file {config_path}: {e}")
        return {}


# Cache the config at module load time
_VALIDATOR_CONFIG = load_validator_config()


def create_horizontal_panel(items: list, output_path: Path) -> Path:
    """Create a horizontal comparison panel with standardized image sizes."""
    images_to_close = []
    
    print(f"-> Normalizing all images by resampling to target size: {TARGET_SIZE}")

    # This list will hold the 1024x1024 resized images
    normalized_images = []
    try:
        for item_path, item_type in items:
            img = Image.open(item_path).convert("RGB")
            images_to_close.append(img)
            # Resize every image to the standard 1024x1024 size
            normalized_img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
            normalized_images.append(normalized_img)
    except FileNotFoundError as e:
        print(f"!!! ERROR: Could not open image file: {e}", file=sys.stderr)
        # Clean up already opened images
        for img in images_to_close:
            img.close()
        return None

    # Create panel from the now-standardized images
    target_height_display = 300  # Height for the final panel image
    display_size = (target_height_display, target_height_display)
    
    total_width = display_size[0] * len(normalized_images)
    panel = Image.new('RGB', (total_width, display_size[1]), 'white')
    draw = ImageDraw.Draw(panel)
    
    try:
        font = ImageFont.truetype("arial.ttf", size=24)
    except IOError:
        font = ImageFont.load_default()

    labels = "ABCDE"
    x_offset = 0
    for i, img in enumerate(normalized_images):
        # Resize for display panel AFTER normalization
        display_img = img.resize(display_size, Image.Resampling.LANCZOS)
        panel.paste(display_img, (x_offset, 0))
        text_pos = (x_offset + 10, 10)
        label = labels[i]
        # Draw text with a black outline for better visibility
        draw.text((text_pos[0]-1, text_pos[1]), label, font=font, fill="black")
        draw.text((text_pos[0]+1, text_pos[1]), label, font=font, fill="black")
        draw.text((text_pos[0], text_pos[1]-1), label, font=font, fill="black")
        draw.text((text_pos[0], text_pos[1]+1), label, font=font, fill="black")
        draw.text(text_pos, label, fill="yellow", font=font)
        x_offset += display_size[0]

    panel.save(output_path)
    
    # After saving, close all original image objects to release file handles
    for img in images_to_close:
        img.close()
        
    return output_path


def ask_dr_orlova_physics_json(panel_image: Image.Image, generator_code: str) -> str:
    """Enhanced AI analysis with scientific context and configurable prompts."""
    if not llm_model:
        return json.dumps({"error": "LLM model is not initialized."})

    config_code_match = re.search(r"class ConfigV18:(.+?)(?=\n\n\n)", generator_code, re.DOTALL)
    config_code = "class ConfigV18:" + config_code_match.group(1) if config_code_match else "Config not found."

    # Build prompt from configuration
    prompt_lines = []
    
    # Use config if available, otherwise fall back to hardcoded prompts
    if _VALIDATOR_CONFIG and "validator_prompt" in _VALIDATOR_CONFIG:
        config = _VALIDATOR_CONFIG["validator_prompt"]
        
        # Check if we should use the full prompt text
        if config.get("use_full_prompt", False) and config.get("full_prompt_text"):
            # Use the full prompt text directly
            full_prompt = config.get("full_prompt_text", "")
            # Add information about the comparison panel
            full_prompt += "\n\nПЕРЕД ТОБОЙ ПАНЕЛЬ СРАВНЕНИЯ: Пять ОКТ B-сканов (обозначены буквами A, B, C, D, E). Четыре из них — реальные сканы, один — синтетический. Твоя задача — найти синтетический скан и провести детальный анализ по всем шести критериям.\n"
            full_prompt += "\nКОД ГЕНЕРАТОРА (для справки):\n" + config_code[:2000] + "\n"
            prompt_lines = [full_prompt]
        else:
            # Use structured prompt (old format)
            # Role and task
            prompt_lines.append(config.get("role_description", "YOU ARE AN EXPERT IN OCT DIAGNOSTICS AND MONTE CARLO LIGHT TRANSPORT."))
            prompt_lines.append(config.get("task_description", "Your task is to analyze this comparison panel and identify the synthetic OCT scan."))
            prompt_lines.append("")
            
            # Scientific context
            prompt_lines.append("SCIENTIFIC CONTEXT:")
            sci_ctx = config.get("scientific_context", {})
            prompt_lines.append(sci_ctx.get("description", "The synthetic image was generated using Monte Carlo principles (MCman.pdf) and morphological guides (Olsen-2015)."))
            criteria = sci_ctx.get("evaluation_criteria", [])
            if criteria:
                prompt_lines.append("Evaluate whether the following appear physically and anatomically plausible:")
                for criterion in criteria:
                    prompt_lines.append(f"- {criterion}")
            prompt_lines.append("")
            
            # Analysis task
            prompt_lines.append("ANALYSIS TASK:")
            task_steps = config.get("analysis_task", {}).get("steps", [])
            for step_info in task_steps:
                if isinstance(step_info, dict):
                    step_num = step_info.get("step", "")
                    desc = step_info.get("description", "")
                    prompt_lines.append(f"{step_num}. {desc}")
                    # Add scoring details if present
                    if "scoring" in step_info:
                        for score, meaning in step_info["scoring"].items():
                            prompt_lines.append(f"   - {score}: {meaning}")
                else:
                    prompt_lines.append(f"  {step_info}")
            prompt_lines.append("")
            
            # Critical emphasis
            prompt_lines.append("CRITICAL EMPHASIS:")
            emphases = config.get("critical_emphasis", [])
            for emph in emphases:
                if isinstance(emph, dict):
                    priority = emph.get("priority", "")
                    desc = emph.get("description", "")
                    if priority:
                        prompt_lines.append(f"- Priority {priority}: {desc}")
                    else:
                        prompt_lines.append(f"- {desc}")
                else:
                    prompt_lines.append(f"- {emph}")
            prompt_lines.append("")
            
            # Structural focus (if enabled)
            struct_focus = config.get("structural_focus", {})
            if struct_focus and isinstance(struct_focus, dict):
                prompt_lines.append("STRUCTURAL FOCUS:")
                for struct_name, struct_info in struct_focus.items():
                    if isinstance(struct_info, dict):
                        priority = struct_info.get("priority", "")
                        desc = struct_info.get("description", "")
                        markers = struct_info.get("visual_markers", [])
                        issues = struct_info.get("common_issues", [])
                        
                        if desc:
                            prompt_lines.append(f"- {struct_name.upper().replace('_', ' ')} ({priority}): {desc}")
                        
                        if markers:
                            prompt_lines.append("  Visual markers:")
                            for marker in markers[:3]:  # Limit to first 3
                                prompt_lines.append(f"    • {marker}")
                        
                        if issues:
                            prompt_lines.append("  Common issues to check:")
                            for issue in issues[:2]:  # Limit to first 2
                                prompt_lines.append(f"    • {issue}")
                prompt_lines.append("")
            
            # Requirements
            prompt_lines.append("REQUIREMENTS:")
            requirements = config.get("requirements", [])
            for req in requirements:
                prompt_lines.append(f"- {req}")
            prompt_lines.append("")
            
            # Output format
            prompt_lines.append("OUTPUT FORMAT:")
            output_fmt = config.get("output_format", {})
            example = output_fmt.get("example", "")
            prompt_lines.append(example)
            prompt_lines.append("")
    else:
        # Fallback to old hardcoded prompt
        prompt_lines = [
            "YOU ARE AN EXPERT IN OCT DIAGNOSTICS AND MONTE CARLO LIGHT TRANSPORT.",
            "Your task is to analyze this comparison panel and identify the synthetic OCT scan.",
            "",
            "SCIENTIFIC CONTEXT:",
            "The synthetic image was generated using Monte Carlo principles (MCman.pdf) and morphological guides (Olsen-2015).",
            "Evaluate whether the light attenuation, speckle patterns, and layer boundaries appear physically and anatomically plausible.",
            "",
            "ANALYSIS TASK:",
            "1. Identify the synthetic scan (indicate its letter from A to E)",
            "2. Assess the degree of difference on a scale from 0 to 100:",
            "   - 100 (Maximum Difference): Completely different, empty, or noise-only",
            "   - 50-80 (High Difference): Major differences in layer brightness, structure",
            "   - 10-30 (Moderate Difference): Noticeable but acceptable differences",
            "   - 0-10 (Low Difference): Subtle differences, very realistic",
            "3. Provide specific parameter recommendations for improvement",
            "",
            "CRITICAL EMPHASIS:",
            "- First, evaluate and comment on the absolute brightness of the superficial layers: stratum corneum and viable epidermis.",
            "- If the stratum corneum is not the brightest layer or its brightness contrast to viable epidermis is unrealistic, prioritize adjusting amplitude_logmean for these layers.",
            "- When proposing parameters, prefer adjustments to amplitude_logmean and density for STRATUM_CORNEUM and VIABLE_EPIDERMIS before geometric tweaks.",
            "",
            "REQUIREMENTS:",
            "- Four scans are real-world OCT images, one is synthetic",
            "- Focus on physical plausibility of light transport and tissue morphology",
            "- Suggest ONLY existing parameter adjustments, do NOT invent new parameters",
            "- Your response MUST be a valid JSON object",
            "",
            "OUTPUT FORMAT:",
            '{"synthetic_scan": "A", "difference_score": 75, "degradation_detected": true, "comments": "Description of differences", "recommendations": {"parameters": {"parameter_name": new_value}}}',
            ""
        ]
    
    # Always add generator configuration at the end
    prompt_lines.append("GENERATOR CONFIGURATION:")
    prompt_lines.append("```python")
    prompt_lines.append(config_code)
    prompt_lines.append("```")
    
    prompt = "\n".join(prompt_lines)

    try:
        response = llm_model.generate_content([prompt, panel_image], request_options={"timeout": 300})
        return response.text
    except Exception as e:
        return json.dumps({"error": str(e)})


def validate_synthetic_scan(synthetic_file: Path, real_pool: Path, generator_code: Path, report_dir: Path) -> dict:
    """
    Enhanced validation function with better error handling and scientific context.
    
    Args:
        synthetic_file: Path to the synthetic scan image
        real_pool: Path to directory containing real scan images
        generator_code: Path to the generator code file
        report_dir: Path to directory for saving reports
        
    Returns:
        Dictionary containing validation results
    """
    print(f"=== Enhanced AI Validation ===")
    print(f"Synthetic scan: {synthetic_file}")
    print(f"Real scans pool: {real_pool}")
    print(f"Generator code: {generator_code}")
    print(f"Report directory: {report_dir}")
    
    # Ensure report directory exists
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # Get real scans from the pool
    all_reals = list(real_pool.glob("*.png")) + list(real_pool.glob("*.jpg"))
    if len(all_reals) < 4:
        error_msg = f"Need at least 4 real scans in the pool '{real_pool}', found {len(all_reals)}"
        print(f"ERROR: {error_msg}")
        return {"error": error_msg}

    # Select 4 random real scans
    selected_reals = random.sample(all_reals, 4)
    print(f"Selected {len(selected_reals)} real scans for comparison")

    # Create comparison items
    test_items = [(p, 'real') for p in selected_reals]
    test_items.append((synthetic_file, 'synthetic'))
    random.shuffle(test_items)
    print(f"Created comparison panel with {len(test_items)} images")

    # Create unlabeled panel
    panel_path = report_dir / f"comparison_panel_{synthetic_file.stem}.png"
    if not create_horizontal_panel(test_items, panel_path):
        error_msg = "Failed to create comparison panel"
        print(f"ERROR: {error_msg}")
        return {"error": error_msg}

    print(f"Comparison panel created: {panel_path}")

    # Run AI analysis
    try:
        with open(generator_code, 'r', encoding='utf-8') as f:
            code_content = f.read()
        
        with Image.open(panel_path) as panel_image_pil:
            ai_response = ask_dr_orlova_physics_json(panel_image_pil, code_content)

        # Parse AI response
        try:
            ai_results = json.loads(ai_response)
            print("AI analysis completed successfully")
        except json.JSONDecodeError as e:
            print(f"WARNING: Failed to parse AI response as JSON: {e}")
            ai_results = {
                "error": "Failed to parse AI response",
                "raw_response": ai_response
            }

        # Create labeled panel for human review
        labeled_panel = report_dir / f"comparison_panel_labeled_{synthetic_file.stem}.png"
        # For now, copy the unlabeled panel as labeled
        # In a full implementation, we would add labels here
        import shutil
        shutil.copy2(panel_path, labeled_panel)

        # Calculate advanced metrics if available
        advanced_metrics = {}
        if ADVANCED_METRICS_AVAILABLE and AdvancedOCTMetrics:
            try:
                # Load images for metric calculation
                synthetic_img = np.array(Image.open(synthetic_file).convert('L'))
                real_scans_images = [np.array(Image.open(str(r)).convert('L')) for r in selected_reals]
                
                # Initialize metrics calculator
                metrics_calc = AdvancedOCTMetrics()
                
                # Calculate all advanced metrics
                comparison_scan = real_scans_images[0] if real_scans_images else None
                advanced_results = metrics_calc.calculate_all_metrics(
                    generated_scan=synthetic_img,
                    real_scans_pool=real_scans_images,
                    comparison_scan=comparison_scan
                )
                
                advanced_metrics = {
                    "ms_ssim": advanced_results.get('ms_ssim', 0.0),
                    "ssim": advanced_results.get('ssim', 0.0),
                    "snr_db": advanced_results.get('snr', {}).get('snr_db', 0.0),
                    "cnr_db": advanced_results.get('snr', {}).get('cnr_db', 0.0),
                    "mmd": advanced_results.get('mmd', {}).get('mmd', 0.0) if isinstance(advanced_results.get('mmd'), dict) else 0.0
                }
                
                print(f"Advanced metrics calculated: MS-SSIM={advanced_metrics['ms_ssim']:.4f}, SNR={advanced_metrics['snr_db']:.2f}dB")
                
            except Exception as e:
                print(f"WARNING: Failed to calculate advanced metrics: {e}")
                advanced_metrics = {}

        # Create comprehensive results
        results = {
            "synthetic_scan_file": str(synthetic_file),
            "ai_analysis": ai_results,
            "advanced_metrics": advanced_metrics if advanced_metrics else None,
            "panel_files": {
                "unlabeled": str(panel_path),
                "labeled": str(labeled_panel)
            },
            "real_scans_used": [str(p) for p in selected_reals],
            "validation_timestamp": str(Path.cwd() / "timestamp.txt")
        }

        # Save results
        results_file = report_dir / "validation_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Validation results saved: {results_file}")
        return results

    except Exception as e:
        error_msg = f"AI validation failed: {e}"
        print(f"ERROR: {error_msg}")
        return {"error": error_msg}


# --- SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced OCT Scan Validator for Alpha Evolve")
    parser.add_argument("--synthetic_file", type=Path, required=True)
    parser.add_argument("--real_pool", type=Path, required=True)
    parser.add_argument("--generator_code", type=Path, required=True)
    parser.add_argument("--report_dir", type=Path, required=True)
    args = parser.parse_args()

    results = validate_synthetic_scan(
        synthetic_file=args.synthetic_file,
        real_pool=args.real_pool,
        generator_code=args.generator_code,
        report_dir=args.report_dir
    )
    
    if "error" in results:
        print(f"Validation failed: {results['error']}")
        sys.exit(1)
    else:
        print("Validation completed successfully")
        print(f"Results: {json.dumps(results, indent=2)}")
