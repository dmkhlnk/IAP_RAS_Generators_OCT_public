# agent_validator.py - Alpha Evolve Validator Agent

import google.generativeai as genai
from PIL import Image
import os
import random
import json
import textwrap
import re
import time
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import cv2
import time
from skimage.metrics import structural_similarity as ssim
from skimage.metrics import peak_signal_noise_ratio as psnr

def create_comparison_panel(generated_scan_path: str, real_scans_dir: str, iteration: int, run_history_dir: str = "run_history"):
    """Creates comparison panel (1 generated + 4 real) with labels and separation"""
    try:
        print(f"[Comparison Panel] Creating comparison panel for iteration {iteration}")
        
        # Load generated scan
        generated_img = np.array(Image.open(generated_scan_path).convert('L'))
        print(f"[Comparison Panel] Loaded generated scan: {generated_img.shape}")
        
        # Load 4 random real scans
        real_scans_paths = [os.path.join(real_scans_dir, f) for f in os.listdir(real_scans_dir) 
                           if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if len(real_scans_paths) < 4:
            print(f"[Comparison Panel] Insufficient real scans: {len(real_scans_paths)}")
            return None
        
        chosen_real_scans = random.sample(real_scans_paths, 4)
        real_imgs = []
        for scan_path in chosen_real_scans:
            img = np.array(Image.open(scan_path).convert('L'))
            real_imgs.append(img)
            print(f"[Comparison Panel] Loaded real scan: {img.shape}")
        
        # Create figure with 5 subplots
        fig, axes = plt.subplots(1, 5, figsize=(20, 4))
        fig.suptitle(f'Alpha Evolve - Iteration {iteration}: Scan Comparison', fontsize=16, fontweight='bold')
        
        # Settings for all subplots
        for i, ax in enumerate(axes):
            ax.set_xticks([])
            ax.set_yticks([])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['left'].set_visible(False)
        
        # Display generated scan (first)
        axes[0].imshow(generated_img, cmap='gray', aspect='auto')
        axes[0].set_title('SYNTHETIC\n(Generated)', 
                         fontsize=12, fontweight='bold', color='red')
        axes[0].add_patch(plt.Rectangle((0, 0), generated_img.shape[1]-1, generated_img.shape[0]-1, 
                                       linewidth=3, edgecolor='red', facecolor='none'))
        
        # Display real scans
        for i, real_img in enumerate(real_imgs):
            axes[i+1].imshow(real_img, cmap='gray', aspect='auto')
            axes[i+1].set_title(f'REAL #{i+1}\n(Reference)', 
                               fontsize=12, fontweight='bold', color='green')
            axes[i+1].add_patch(plt.Rectangle((0, 0), real_img.shape[1]-1, real_img.shape[0]-1, 
                                            linewidth=2, edgecolor='green', facecolor='none'))
        
        # Add general information
        fig.text(0.5, 0.02, 
                f'Task for validator: Identify which scan is synthetic (AI-generated)',
                ha='center', fontsize=10, style='italic')
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.85, bottom=0.15)
        
        # Save panel to run_history
        run_dir = Path(run_history_dir) / f"iteration_{iteration}"
        run_dir.mkdir(parents=True, exist_ok=True)
        
        panel_path = run_dir / "comparison_panel.png"
        plt.savefig(panel_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        print(f"[Comparison Panel] Comparison panel saved: {panel_path}")
        return str(panel_path)
        
    except Exception as e:
        print(f"[Validator] Error creating comparison panel: {e}")
        return None

def save_validation_result(result: dict, iteration: int, run_history_dir: str = "run_history"):
    """Saves validation result to run_history"""
    run_dir = Path(run_history_dir) / f"iteration_{iteration}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = run_dir / "validation_result.json"
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"[Alpha Evolve] Validation result saved: {result_file}")
    return str(result_file)

def format_justification(text, width=80, indent='   '):
    if not text: return indent + "No justification provided."
    paragraphs = text.split('\n')
    formatted_paragraphs = []
    for p in paragraphs:
        if p.strip():
            formatted_paragraphs.append(textwrap.fill(p, width=width, initial_indent=indent, subsequent_indent=indent))
    return '\n\n'.join(formatted_paragraphs)

def run_validation_test(generated_scan_path: str, real_scans_dir: str, model_name: str, iteration: int = 1) -> dict:
    """Conducts validation test by sending images to Gemini."""
    NUM_REAL_SCANS_IN_TEST = 4
    lineup = [] # Initialize lineup here so it's available in except blocks
    
    # Alpha Evolve: Load validator context
    validator_context = load_validator_context(iteration)
    print(f"[Validator] Validator context loaded: {len(validator_context)} characters")
    
    try:
        model = genai.GenerativeModel(model_name)
        real_scans_paths = [os.path.join(real_scans_dir, f) for f in os.listdir(real_scans_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        if len(real_scans_paths) < NUM_REAL_SCANS_IN_TEST:
            return {"error": f"Not enough real scans. Found {len(real_scans_paths)}, need {NUM_REAL_SCANS_IN_TEST}."}
        if not os.path.exists(generated_scan_path):
            return {"error": f"Generated scan not found: {generated_scan_path}"}
        
        chosen_real_scans = random.sample(real_scans_paths, NUM_REAL_SCANS_IN_TEST)
        lineup = [(path, 'real') for path in chosen_real_scans]
        lineup.append((generated_scan_path, 'fake'))
        random.shuffle(lineup)
        
        correct_answer_index = [i for i, item in enumerate(lineup) if item[1] == 'fake'][0] + 1
        images_to_test = [Image.open(path) for path, _ in lineup]
        
    except Exception as e:
        # Return lineup even on file preparation error
        return {"error": f"File preparation failed: {e}", "lineup": lineup}

    prompt_template = f"""
    Your Role: You are Professor Dr. Sarah Chen, a world-renowned expert in:
    - **Dermatology & Skin Anatomy** (25 years experience)
    - **Optical Coherence Tomography (OCT)** imaging (15 years)
    - **Medical Image Analysis** and AI (20 years)
    - **Biomedical Physics** and light-tissue interactions (18 years)
    - **Machine Learning** for medical imaging (12 years)

    Your Task: As Professor Chen, your primary goal is to perform a visual Turing test with the utmost scientific rigor. You will analyze {len(images_to_test)} OCT B-scans. One is synthetic, the rest are real.
    1. Identify the synthetic image with high confidence, providing a detailed, scientific justification.
    2. **BE EXTREMELY VIGILANT** for any synthetic artifacts, no matter how subtle. Your expertise is crucial for identifying even the most sophisticated fakes.
    3. Provide concrete, actionable feedback to the generator agent, explaining precisely what needs to be improved to achieve perfect realism.

    **ALPHA EVOLVE CONTEXT - PREVIOUS ANALYSES:**
    {validator_context[:1500] + "..." if len(validator_context) > 1500 else validator_context}

    Evaluation Criteria (Apply with the highest scientific scrutiny):

    1. **Layer Correspondence and Morphology:**
       1.1. Do the epidermal and dermal layers (Stratum Corneum, Viable Epidermis, Papillary Dermis, Reticular Dermis) exhibit realistic thickness, boundaries, and undulations (rete pegs)?
       1.2. Is the transition between layers smooth and natural, or are there abrupt, artificial changes?
       1.3. Are the overall shapes and contours of the layers consistent with real human skin OCT scans?

    2. **Global Inclusions and Shadows:**
       2.1. Are there any peculiarities in shadows from bright scatterers that would form global structures significantly different from other scans?
       2.2. Are there global structures present in the examined image that are absent in other images?
       2.3. **CRITICAL: Are hair follicles anatomically correct in size, shape, and distribution? Check for:
    - Realistic follicle count (3-6 per scan)
    - Proper width range (6-18 pixels)
    - Natural depth variation (30-95% of dermis)
    - Realistic wall thickness (2 pixels)
    - Natural angle variation (up to 15 degrees)**
       2.4. **CRITICAL: Are sebaceous glands anatomically correct? Check for:
    - Lobulated structure (4-8 lobes per gland)
    - Realistic size (8-20 pixels radius)
    - Natural shape variation (not perfect circles)
    - Proper duct connections to follicles
    - Realistic lobe asymmetry and branching
    - Natural attachment distance (5-15 pixels from follicle)**
       2.5. **CRITICAL: Are there suspiciously dark vertical stripes or shadows under follicles and sebaceous glands that appear too uniform or artificial?**

    3. **Background and Noise:**
       3.1. Does the background outside the tissue visually match other examples?
       3.2. Does the noise on the tissue match other examples?
       3.3. Is the speckle pattern (granular texture) realistic and consistent with physical OCT principles, or does it appear artificial/repetitive?

    4. **Synthetic Artifact Detection (CRITICAL for identifying fake images):**
       4.1. **UNREALISTIC ANATOMY:** Are any anatomical structures (follicles, glands, layers) proportionally incorrect or abnormally sized? (e.g., 'Follicles are too thick and prominent', 'Sebaceous glands are perfectly circular and too large')
       4.2. **ARTIFICIAL SHADOWS:** Are there dark stripes or shadows that appear unnaturally uniform, too sharp, or not physically plausible?
       4.3. **OVERSIZED STRUCTURES:** Are any structures (e.g., sebaceous glands, hair shafts) significantly larger than expected in real OCT scans?
       4.4. **UNNATURAL CONTRAST/BRIGHTNESS:** Does the image exhibit areas of unnaturally high or low contrast, or a brightness distribution that seems artificial?
       4.5. **SYMMETRICAL ARTIFACTS:** Are there any repetitive or perfectly symmetrical patterns that would not occur naturally in biological tissue?
       4.6. **MISSING DETAILS:** Are expected fine anatomical details (e.g., subtle ductal structures, micro-vasculature) absent or poorly rendered?

    Your output MUST be a JSON object with the following structure:
    ```json
    {{
        "verdict": "SYNTHETIC" or "REAL" or "INDISTINGUISHABLE",
        "confidence": "Low" or "Medium" or "High",
        "justification": "Step-by-step scientific reasoning for the verdict, referencing criteria.",
        "synthetic_artifacts_detected": {{
            "unrealistic_anatomy": ["Description of specific issues, e.g., 'Follicles are too thick.'"],
            "artificial_shadows": ["Description of specific issues."],
            "oversized_structures": ["Description of specific issues."],
            "unnatural_contrast": ["Description of specific issues."],
            "symmetrical_artifacts": ["Description of specific issues."],
            "missing_details": ["Description of specific issues."]
        }},
        "feedback_for_generator": "Specific, actionable recommendations for the generator to improve realism, e.g., 'Reduce follicle wall thickness to 2 pixels and increase depth variation.'"
    }}
    ```

    Images for Analysis:
    """
    prompt_parts = [prompt_template]
    for i, img in enumerate(images_to_test):
        prompt_parts.append(f"**Image {i+1}:**"); prompt_parts.append(img)
    prompt_parts.append("""
    Output Format:
    Provide your full analysis in a single JSON object.

    {
      "final_verdict": {
        "identified_synthetic_image_index": integer,
        "confidence_level": "High / Medium / Low",
        "detailed_justification_chain_of_thought": "Your detailed step-by-step reasoning. If you cannot identify the fake, explain why the images are indistinguishable based on the criteria."
      },
      "synthetic_artifacts_detected": {
        "unrealistic_anatomy": "Describe any proportionally incorrect or abnormally sized structures (e.g., 'Follicles are too thick and prominent', 'Sebaceous glands are oversized')",
        "artificial_shadows": "Describe any suspiciously perfect dark stripes or shadows (e.g., 'Uniform black stripes under follicles appear artificial')",
        "unnatural_contrast": "Describe any extreme contrast differences that seem unnatural (e.g., 'Extreme contrast between bright glands and dark shadows')",
        "synthetic_patterns": "Describe any suspiciously symmetrical or algorithmic patterns"
      },
      "feedback_for_generator": "Specific recommendations for improving synthetic image generation based on detected artifacts. Be concrete and actionable."
    }
    """)

    try:
        response = model.generate_content(prompt_parts)
        response_text = response.text
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if not json_match: json_match = re.search(r'(\{.*?\})', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group(1))
            result['correct_index'] = correct_answer_index
            result['lineup'] = lineup
            
            # Extract detailed feedback for generator
            if 'synthetic_artifacts_detected' in result:
                artifacts = result['synthetic_artifacts_detected']
                detailed_feedback = []
                
                if artifacts.get('unrealistic_anatomy'):
                    detailed_feedback.append(f"ANATOMY ISSUE: {artifacts['unrealistic_anatomy']}")
                if artifacts.get('artificial_shadows'):
                    detailed_feedback.append(f"SHADOW ISSUE: {artifacts['artificial_shadows']}")
                if artifacts.get('unnatural_contrast'):
                    detailed_feedback.append(f"CONTRAST ISSUE: {artifacts['unnatural_contrast']}")
                if artifacts.get('synthetic_patterns'):
                    detailed_feedback.append(f"PATTERN ISSUE: {artifacts['synthetic_patterns']}")
                
                if detailed_feedback:
                    result['detailed_artifacts'] = "\n".join(detailed_feedback)
                
            if 'feedback_for_generator' in result:
                result['generator_feedback'] = result['feedback_for_generator']
            
            # Alpha Evolve: Create comparison panel
            panel_path = create_comparison_panel(generated_scan_path, real_scans_dir, iteration)
            if panel_path:
                result['comparison_panel_path'] = panel_path
            
            # Alpha Evolve: Save validation result
            save_validation_result(result, iteration)
            
            return result
        else:
            # Return lineup and raw response on JSON parsing error
            return {"error": "Failed to parse JSON from model response.", "raw_response": response_text, "lineup": lineup}
    except Exception as e:
        # Return lineup on any other API error
        return {"error": f"Gemini API call failed: {e}", "lineup": lineup}


def multi_model_validation(generated_scan_path: str, real_scans_dir: str, iteration: int = 1) -> dict:
    """Multi-model validation for improved Alpha Evolve accuracy"""
    print(f"[Multi-Model] Starting multi-model validation for iteration {iteration}")
    
    models = ["gemini-3-pro-preview"]  # Currently only Gemini, but structure ready for expansion
    
    results = []
    for model_name in models:
        try:
            print(f"[Multi-Model] Validation with {model_name}...")
            result = run_validation_test(generated_scan_path, real_scans_dir, model_name, iteration)
            if "error" not in result:
                results.append(result)
                print(f"[Multi-Model] {model_name}: Success")
            else:
                print(f"[Multi-Model] {model_name}: Error - {result['error']}")
        except Exception as e:
            print(f"[Multi-Model] {model_name}: Critical error - {e}")
    
    if not results:
        return {"error": "All validation models failed", "lineup": []}
    
    # Aggregate results from all models
    if len(results) == 1:
        return results[0]
    
    # If multiple models - take consensus
    consensus_result = aggregate_validation_results(results)
    print(f"[Multi-Model] Consensus obtained from {len(results)} models")
    
    return consensus_result


def aggregate_validation_results(results: list) -> dict:
    """Aggregates results from multiple validation models"""
    if not results:
        return {"error": "No results to aggregate"}
    
    # Take first result as base
    consensus = results[0].copy()
    
    # Aggregate confidence scores if available
    confidence_scores = []
    for result in results:
        if 'confidence' in result:
            confidence_scores.append(result['confidence'])
    
    if confidence_scores:
        consensus['confidence'] = sum(confidence_scores) / len(confidence_scores)
        consensus['model_count'] = len(results)
    
    # Add consensus information
    consensus['multi_model_consensus'] = True
    consensus['models_used'] = len(results)
    
    return consensus


def detailed_quality_metrics(generated_scan_path: str, real_scans_dir: str) -> dict:
    """Detailed quality analytics for Alpha Evolve"""
    print(f"[Quality Analytics] Quality analysis: {generated_scan_path}")
    
    try:
        # Load generated scan
        generated_img = cv2.imread(generated_scan_path, cv2.IMREAD_GRAYSCALE)
        if generated_img is None:
            return {"error": "Failed to load generated scan"}
        
        # Load real scans for comparison
        real_scans = list(Path(real_scans_dir).glob("*.png"))
        if not real_scans:
            return {"error": "No real scans for comparison"}
        
        # Choose random real scan for comparison
        reference_scan = random.choice(real_scans)
        reference_img = cv2.imread(str(reference_scan), cv2.IMREAD_GRAYSCALE)
        
        if reference_img is None:
            return {"error": "Failed to load reference scan"}
        
        # Resize to same dimensions
        if generated_img.shape != reference_img.shape:
            reference_img = cv2.resize(reference_img, (generated_img.shape[1], generated_img.shape[0]))
        
        # Calculate quality metrics
        metrics = {}
        
        # 1. Structural Similarity (SSIM)
        try:
            ssim_score = ssim(generated_img, reference_img)
            metrics['ssim'] = float(ssim_score)
            print(f"[Quality Analytics] SSIM: {ssim_score:.4f}")
        except Exception as e:
            print(f"[Quality Analytics] SSIM error: {e}")
            metrics['ssim'] = 0.0
        
        # 2. Peak Signal-to-Noise Ratio (PSNR)
        try:
            psnr_score = psnr(generated_img, reference_img)
            metrics['psnr'] = float(psnr_score)
            print(f"[Quality Analytics] PSNR: {psnr_score:.2f} dB")
        except Exception as e:
            print(f"[Quality Analytics] PSNR error: {e}")
            metrics['psnr'] = 0.0
        
        # 3. Histogram comparison
        try:
            hist_generated = cv2.calcHist([generated_img], [0], None, [256], [0, 256])
            hist_reference = cv2.calcHist([reference_img], [0], None, [256], [0, 256])
            hist_correlation = cv2.compareHist(hist_generated, hist_reference, cv2.HISTCMP_CORREL)
            metrics['histogram_correlation'] = float(hist_correlation)
            print(f"[Quality Analytics] Histogram correlation: {hist_correlation:.4f}")
        except Exception as e:
            print(f"[Quality Analytics] Histogram error: {e}")
            metrics['histogram_correlation'] = 0.0
        
        # 4. Texture analysis (LBP - Local Binary Pattern)
        try:
            lbp_generated = calculate_lbp(generated_img)
            lbp_reference = calculate_lbp(reference_img)
            texture_similarity = np.corrcoef(lbp_generated.flatten(), lbp_reference.flatten())[0, 1]
            metrics['texture_similarity'] = float(texture_similarity) if not np.isnan(texture_similarity) else 0.0
            print(f"[Quality Analytics] Texture similarity: {texture_similarity:.4f}")
        except Exception as e:
            print(f"[Quality Analytics] Texture error: {e}")
            metrics['texture_similarity'] = 0.0
        
        # 5. Overall quality score
        quality_score = (
            metrics['ssim'] * 0.4 +
            min(metrics['psnr'] / 50.0, 1.0) * 0.3 +  # Normalize PSNR
            metrics['histogram_correlation'] * 0.2 +
            metrics['texture_similarity'] * 0.1
        )
        metrics['overall_quality'] = float(quality_score)
        
        print(f"[Quality Analytics] Overall quality score: {quality_score:.4f}")
        
        return {
            "quality_metrics": metrics,
            "reference_scan": str(reference_scan),
            "analysis_timestamp": time.time()
        }
        
    except Exception as e:
        print(f"[Quality Analytics] Critical error: {e}")
        return {"error": f"Quality analysis error: {e}"}


def calculate_lbp(image):
    """Calculates Local Binary Pattern for texture analysis"""
    # Simplified LBP version
    rows, cols = image.shape
    lbp = np.zeros_like(image)
    
    for i in range(1, rows-1):
        for j in range(1, cols-1):
            center = image[i, j]
            binary_string = ""
            # 8-neighbor LBP
            neighbors = [
                image[i-1, j-1], image[i-1, j], image[i-1, j+1],
                image[i, j+1], image[i+1, j+1], image[i+1, j],
                image[i+1, j-1], image[i, j-1]
            ]
            
            for neighbor in neighbors:
                binary_string += "1" if neighbor >= center else "0"
            
            lbp[i, j] = int(binary_string, 2)
    
    return lbp


def evolve_validator_system(iteration: int, model_name: str) -> dict:
    """Validator can evolve its own prompts and criteria"""
    print(f"[Validator Evolution] Starting validator evolution for iteration {iteration}")
    
    # Try to load API key using centralized utility
    try:
        import sys
        from pathlib import Path
        # Add parent directory to path to import load_api_key
        parent_dir = Path(__file__).parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        from load_api_key import get_api_key
        api_key = get_api_key()
        if api_key:
            os.environ['GOOGLE_API_KEY'] = api_key
            os.environ['GEMINI_API_KEY'] = api_key
    except ImportError:
        pass  # Fallback to environment variable
    
    if not os.getenv('GOOGLE_API_KEY') and not os.getenv('GEMINI_API_KEY'):
        return {"status": "error", "message": "No API key. Please set GEMINI_API_KEY or create .env file"}
    
    try:
        model = genai.GenerativeModel(model_name)
        
        # Load current validator state
        current_validator = open("agent_validator.py", 'r').read()
        
        evolution_prompt = f"""
        You are the Validator Evolution Controller. You can modify your own validation criteria and prompts to become more effective.
        
        **VALIDATOR EVOLUTION CAPABILITIES:**
        - Update validation criteria for better artifact detection
        - Improve scientific assessment methods
        - Enhance feedback quality
        - Optimize validation algorithms
        - Add new detection methods
        
        **CURRENT ITERATION:** {iteration}
        
        **EVOLUTION TASK:**
        Analyze your current validation approach and suggest improvements to:
        1. Better detect synthetic artifacts
        2. Provide more actionable feedback
        3. Improve scientific accuracy
        4. Enhance validation efficiency
        
        **OUTPUT FORMAT:**
        Provide JSON with:
        {{
            "validator_improvements": {{
                "enhanced_criteria": "Updated validation criteria",
                "improved_prompts": "Better validation prompts",
                "new_detection_methods": "Additional artifact detection"
            }},
            "reasoning": "Why these improvements will help",
            "expected_benefits": ["List of expected improvements"]
        }}
        """
        
        response = model.generate_content(evolution_prompt)
        
        # Parse response
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response.text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\{.*?\})', response.text, re.DOTALL)
        
        if json_match:
            evolution_data = json.loads(json_match.group(1))
            return {
                "status": "success",
                "evolution_data": evolution_data,
                "raw_response": response.text
            }
        else:
            return {
                "status": "error",
                "message": "Could not parse validator evolution",
                "raw_response": response.text
            }
            
    except Exception as e:
        print(f"[Validator Evolution] Error: {e}")
        return {"status": "error", "message": str(e)}

def load_validator_context(iteration: int, run_history_dir: str = "run_history") -> str:
    """Loads complete context for validator from all previous iterations"""
    try:
        run_dir = Path(run_history_dir)
        if not run_dir.exists():
            return "No iteration history for analysis"
        
        context_parts = []
        context_parts.append(f"# VALIDATOR - ITERATION {iteration} CONTEXT")
        context_parts.append(f"# Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        context_parts.append("")
        
        # Analyze all previous iterations
        for i in range(1, iteration):
            iter_dir = run_dir / f"iteration_{i}"
            if iter_dir.exists():
                context_parts.append(f"## ITERATION {i} - VALIDATOR ANALYSIS:")
                
                # Load validation result
                validation_file = iter_dir / "validation_result.json"
                if validation_file.exists():
                    try:
                        with open(validation_file, 'r', encoding='utf-8') as f:
                            validation = json.load(f)
                        
                        # Extract key information for validator
                        if 'final_verdict' in validation:
                            verdict = validation['final_verdict']
                            context_parts.append(f"### Iteration {i} verdict:")
                            context_parts.append(f"- Identified synthetic scan: {verdict.get('identified_synthetic_image_index', 'Unknown')}")
                            context_parts.append(f"- Confidence: {verdict.get('confidence_level', 'Unknown')}")
                            context_parts.append("")
                        
                        # Load detected artifacts
                        if 'synthetic_artifacts_detected' in validation:
                            artifacts = validation['synthetic_artifacts_detected']
                            context_parts.append(f"### Detected artifacts in iteration {i}:")
                            for key, value in artifacts.items():
                                if value and value.strip():
                                    context_parts.append(f"- {key}: {value}")
                            context_parts.append("")
                        
                        # Load justification
                        if 'final_verdict' in validation and 'detailed_justification_chain_of_thought' in validation['final_verdict']:
                            justification = validation['final_verdict']['detailed_justification_chain_of_thought']
                            context_parts.append(f"### Validator justification for iteration {i}:")
                            context_parts.append(justification[:300] + "..." if len(justification) > 300 else justification)
                            context_parts.append("")
                            
                    except Exception as e:
                        context_parts.append(f"Error loading validation for iteration {i}: {e}")
                
                # Load validator feedback
                feedback_file = iter_dir / "validator_feedback.txt"
                if feedback_file.exists():
                    try:
                        with open(feedback_file, 'r', encoding='utf-8') as f:
                            feedback = f.read()
                        context_parts.append(f"### Validator feedback for iteration {i}:")
                        context_parts.append(feedback[:200] + "..." if len(feedback) > 200 else feedback)
                        context_parts.append("")
                    except Exception as e:
                        context_parts.append(f"Error loading feedback for iteration {i}: {e}")
                
                context_parts.append("---")
                context_parts.append("")
        
        # Create final context
        full_context = "\n".join(context_parts)
        
        # Save validator context
        current_iter_dir = run_dir / f"iteration_{iteration}"
        current_iter_dir.mkdir(parents=True, exist_ok=True)
        
        validator_context_file = current_iter_dir / "validator_context.md"
        with open(validator_context_file, 'w', encoding='utf-8') as f:
            f.write(full_context)
        
        print(f"[Validator] Validator context created: {validator_context_file}")
        return full_context
        
    except Exception as e:
        print(f"[Validator] Error creating validator context: {e}")
        return "Context loading error"