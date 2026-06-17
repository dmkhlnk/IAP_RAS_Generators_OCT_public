# agent_generator.py - Alpha Evolve Generator Agent
import os
import json
import shutil
import time
from pathlib import Path
import google.generativeai as genai

# Knowledge base for parameter adjustments
KNOWLEDGE_BASE = """
Your Role: You are Professor Dr. Michael Rodriguez, a world-renowned expert in:
- **Biomedical Engineering & Simulation** (30 years experience)
- **Computational Biology & Biophysics** (25 years)
- **Medical Image Synthesis & Generative Models** (20 years)
- **Skin Anatomy & Physiology** (22 years)
- **OCT Physics & Optics** (18 years)

Your Task: As Professor Rodriguez, your primary goal is to generate highly realistic synthetic OCT skin scans by intelligently modifying the `config_skin_regions.py` file. You must ensure the generated scans are indistinguishable from real human OCT scans, adhering to the highest standards of anatomical and physical accuracy.

**CRITICAL GUIDELINES:**
- **NEVER reduce scatterer density.** The target is ~180,000 scatterers. Always aim for high density.
- **NEVER simplify anatomical complexity.** Always strive for more realistic and varied structures.
- **Prioritize anatomical realism over simplicity.**
- **Learn from validator feedback** to refine parameters.
- **Maintain consistency** with previous successful configurations.

**KNOWLEDGE BASE FOR PARAMETER ADJUSTMENTS:**
- To control the shape of the epidermal-dermal junction (rete pegs), modify `rete_pegs_max_amplitude_pixels` (depth) and `rete_pegs_base_frequency` (frequency) in `EPIDERMIS_VARIATION`.
- To control the number of follicles, modify `count_min` and `count_max` in `FOLLICLE_PARAMS`.
- To control follicle thickness, adjust `min_width_pixels` and `max_width_pixels` in `FOLLICLE_PARAMS`.
- To control the brightness/contrast of a layer, modify `amplitude_logmean` (brightness) and `density` (number of speckles) in its main dictionary (e.g., `PAPILLARY_DERMIS`). Higher amplitude_logmean = brighter.
- To control the size of sebaceous glands, adjust `min_radius_pixels` and `max_radius_pixels` in `SEBACEOUS_GLAND_PARAMS`.
- To control the thickness of the top skin layer (Stratum Corneum), adjust `base_thickness_pixels` in `STRATUM_CORNEUM_PARAMS`.
- To create realistic hair follicles and sebaceous glands:
  * Follicle count: 3-6 per scan (count_min=3, count_max=6)
  * Follicle width: 6-18 pixels (min_width_pixels=6, max_width_pixels=18)
  * Follicle depth: 30-95% of dermis (depth_factor_min=0.3, depth_factor_max=0.95)
  * Wall thickness: 2 pixels (wall_thickness_pixels=2)
  * Lumen thickness: 0.8 pixels (lumen_thickness_pixels=0.8)
  * Angle variation: up to 15 degrees (angle_max_rad=np.pi/12)
  * Sebaceous glands: 2-4 lobes per follicle (lobes_per_follicle_min=2, lobes_per_follicle_max=4)
  * Gland size: 12-28 pixels radius (min_radius_pixels=12, max_radius_pixels=28)
  * Lobulated structure: 4-8 lobes per gland (num_lobes_min=4, num_lobes_max=8)
  * Lobe shape variation: 0.7 (lobe_shape_variation=0.7)
  * Lobe connection strength: 0.8 (lobe_connection_strength=0.8)
  * Duct length: 8-20 pixels (duct_length_min=8, duct_length_max=20)
  * Lobe angle variation: 0.6 (lobe_angle_variation=0.6)
  * Lobe size variation: 0.5 (lobe_size_variation=0.5)
  * Attachment distance: 5-15 pixels from follicle (attachment_distance_min=5, attachment_distance_max=15)
  * Duct branching probability: 0.3 (duct_branching_probability=0.3)
  * Lobe asymmetry factor: 0.4 (lobe_asymmetry_factor=0.4)

**CRITICAL PROTECTION RULES:**
- NEVER reduce scatterer density below 0.15 for STRATUM_CORNEUM.
- NEVER reduce follicle count below 3.
- NEVER reduce follicle width below 6 pixels.
- NEVER simplify sebaceous gland structure.
- ALWAYS ensure anatomical accuracy and complexity.
"""

def save_code_version(config_code: str, iteration: int, run_history_dir: str = "run_history"):
    """Saves code version for Alpha Evolve"""
    run_dir = Path(run_history_dir) / f"iteration_{iteration}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    code_file = run_dir / "config_skin_regions.py"
    with open(code_file, 'w', encoding='utf-8') as f:
        f.write(config_code)
    
    print(f"[Alpha Evolve] Code saved: {code_file}")
    return str(code_file)


def create_agent_context_summary(iteration: int, run_history_dir: str = "run_history"):
    """Creates complete context for agents based on all previous iterations"""
    try:
        run_dir = Path(run_history_dir)
        if not run_dir.exists():
            return "No iteration history"
        
        context_parts = []
        context_parts.append(f"# ALPHA EVOLVE - COMPLETE AGENT CONTEXT")
        context_parts.append(f"# Current iteration: {iteration}")
        context_parts.append(f"# Creation time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        context_parts.append("")
        
        # Analyze all previous iterations
        for i in range(1, iteration):
            iter_dir = run_dir / f"iteration_{i}"
            if iter_dir.exists():
                context_parts.append(f"## ITERATION {i}:")
                
                # Load iteration summary
                summary_file = iter_dir / "iteration_summary.json"
                if summary_file.exists():
                    try:
                        import json
                        with open(summary_file, 'r', encoding='utf-8') as f:
                            summary = json.load(f)
                        
                        context_parts.append(f"### Result:")
                        context_parts.append(f"- Verdict: {summary.get('best_scan_result', {}).get('verdict', 'Unknown')}")
                        context_parts.append(f"- Confidence: {summary.get('best_scan_result', {}).get('confidence', 'Unknown')}")
                        context_parts.append(f"- Time: {summary.get('timestamp', 'Unknown')}")
                        context_parts.append("")
                        
                    except Exception as e:
                        context_parts.append(f"Error loading summary: {e}")
                
                # Load validator feedback
                feedback_file = iter_dir / "validator_feedback.txt"
                if feedback_file.exists():
                    try:
                        with open(feedback_file, 'r', encoding='utf-8') as f:
                            feedback = f.read()
                        context_parts.append(f"### Validator feedback:")
                        context_parts.append(feedback[:500] + "..." if len(feedback) > 500 else feedback)
                        context_parts.append("")
                    except Exception as e:
                        context_parts.append(f"Error loading feedback: {e}")
                
                # Load validation result
                validation_file = iter_dir / "validation_result.json"
                if validation_file.exists():
                    try:
                        with open(validation_file, 'r', encoding='utf-8') as f:
                            validation = json.load(f)
                        
                        if 'synthetic_artifacts_detected' in validation:
                            artifacts = validation['synthetic_artifacts_detected']
                            context_parts.append(f"### Detected artifacts:")
                            for key, value in artifacts.items():
                                if value:
                                    context_parts.append(f"- {key}: {value}")
                            context_parts.append("")
                        
                        if 'feedback_for_generator' in validation:
                            context_parts.append(f"### Generator recommendations:")
                            context_parts.append(validation['feedback_for_generator'])
                            context_parts.append("")
                            
                    except Exception as e:
                        context_parts.append(f"Error loading validation: {e}")
                
                context_parts.append("---")
                context_parts.append("")
        
        # Create final context
        full_context = "\n".join(context_parts)
        
        # Save context to current iteration
        current_iter_dir = run_dir / f"iteration_{iteration}"
        current_iter_dir.mkdir(parents=True, exist_ok=True)
        
        context_file = current_iter_dir / "agent_context.md"
        with open(context_file, 'w', encoding='utf-8') as f:
            f.write(full_context)
        
        print(f"[Alpha Evolve] Agent context created: {context_file}")
        return str(context_file)
        
    except Exception as e:
        print(f"[Alpha Evolve] Error creating context: {e}")
        return None

def load_best_code_version(run_history_dir: str = "run_history"):
    """Loads best code version from history"""
    run_dir = Path(run_history_dir)
    if not run_dir.exists():
        return None
    
    # Find last iteration with good results
    iterations = sorted([d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith('iteration_')])
    
    for iteration_dir in reversed(iterations):
        code_file = iteration_dir / "config_skin_regions.py"
        if code_file.exists():
            with open(code_file, 'r', encoding='utf-8') as f:
                return f.read()
    
    return None

def analyze_validation_history(run_history_dir: str = "run_history") -> dict:
    """Analyzes validation history for Alpha Evolve"""
    run_dir = Path(run_history_dir)
    if not run_dir.exists():
        return {"status": "no_history"}
    
    iterations = sorted([d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith('iteration_')])
    
    analysis = {
        "total_iterations": len(iterations),
        "best_iteration": None,
        "trend": "unknown"
    }
    
    if len(iterations) >= 1:
        # Analyze quality trend with improved logic
        recent_scores = []
        for iteration_dir in iterations[-5:]:  # Last 5 iterations for better trend analysis
            result_file = iteration_dir / "validation_result.json"
            if result_file.exists():
                try:
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                        if 'confidence_level' in data:
                            score = 1.0 if data['confidence_level'] == 'Low' else 0.5 if data['confidence_level'] == 'Medium' else 0.0
                            recent_scores.append(score)
                except:
                    pass
        
        # Improved trend analysis
        if len(recent_scores) >= 3:
            # Use 3+ points for reliable trend analysis
            if recent_scores[-1] < recent_scores[0]:
                analysis["trend"] = "improving"
            elif recent_scores[-1] > recent_scores[0]:
                analysis["trend"] = "degrading"
            else:
                analysis["trend"] = "stable"
        elif len(recent_scores) >= 2:
            # For 2 points, use simple comparison
            if recent_scores[-1] < recent_scores[0]:
                analysis["trend"] = "improving"
            elif recent_scores[-1] > recent_scores[0]:
                analysis["trend"] = "degrading"
            else:
                analysis["trend"] = "stable"
        else:
            # Single point - no trend yet
            analysis["trend"] = "insufficient_data"
    
    return analysis

def evolve_system_files(iteration: int, model_name: str) -> dict:
    """Full Alpha Evolve: Agents can modify any system files and prompts"""
    print(f"[Alpha Evolve] Starting full system evolution for iteration {iteration}")
    
    if not os.getenv('GOOGLE_API_KEY'):
        print("[Alpha Evolve] ERROR: API key not configured.")
        return {"status": "error", "message": "No API key"}
    
    try:
        model = genai.GenerativeModel(model_name)
        
        # Load current system state
        current_files = {
            "agent_generator.py": open("agent_generator.py", 'r').read(),
            "agent_validator.py": open("agent_validator.py", 'r').read(),
            "pipeline_orchestrator.py": open("pipeline_orchestrator.py", 'r').read(),
            "config_skin_regions.py": open("config_skin_regions.py", 'r').read()
        }
        
        # Load validation history
        history_analysis = analyze_validation_history()
        context_file = Path("run_history") / f"iteration_{iteration}" / "agent_context.md"
        agent_context = ""
        if context_file.exists():
            with open(context_file, 'r', encoding='utf-8') as f:
                agent_context = f.read()
        
        evolution_prompt = f"""
        You are the Alpha Evolve Master Controller - you can modify ANY part of the system to improve performance.
        
        **SYSTEM EVOLUTION CAPABILITIES:**
        - Modify agent prompts for better performance
        - Update validation criteria
        - Improve system architecture
        - Optimize code efficiency
        - Add new features
        - Fix bugs and issues
        
        **CURRENT SYSTEM STATE:**
        - Iteration: {iteration}
        - History: {history_analysis}
        - Context: {agent_context[:1000]}...
        
        **AVAILABLE FILES TO MODIFY:**
        1. agent_generator.py - Generator agent logic and prompts
        2. agent_validator.py - Validator agent logic and prompts  
        3. pipeline_orchestrator.py - Main system coordinator
        4. config_skin_regions.py - Anatomical parameters
        
        **EVOLUTION TASK:**
        Analyze the current system and suggest improvements. You can:
        - Modify any Python file
        - Update prompts and knowledge bases
        - Improve algorithms
        - Add new functionality
        - Optimize performance
        
        **OUTPUT FORMAT:**
        Provide a JSON response with:
        {{
            "files_to_modify": {{
                "filename.py": "complete_new_file_content",
                "another_file.py": "complete_new_file_content"
            }},
            "reasoning": "Why these changes will improve the system",
            "expected_improvements": ["List of expected benefits"]
        }}
        
        Only modify files if you have concrete improvements to suggest.
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
                "message": "Could not parse evolution response",
                "raw_response": response.text
            }
            
    except Exception as e:
        print(f"[Alpha Evolve] Evolution error: {e}")
        return {"status": "error", "message": str(e)}

def apply_system_evolution(evolution_data: dict, iteration: int) -> bool:
    """Apply system evolution changes"""
    try:
        files_to_modify = evolution_data.get("files_to_modify", {})
        
        if not files_to_modify:
            print("[Alpha Evolve] No files to modify")
            return True
        
        # Backup current files
        backup_dir = Path("run_history") / f"iteration_{iteration}" / "system_backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        for filename, new_content in files_to_modify.items():
            # Backup original
            if os.path.exists(filename):
                shutil.copy2(filename, backup_dir / f"{filename}.backup")
            
            # Apply new content
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"[Alpha Evolve] Modified {filename}")
        
        # Save evolution log
        evolution_log = {
            "iteration": iteration,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "files_modified": list(files_to_modify.keys()),
            "reasoning": evolution_data.get("reasoning", ""),
            "expected_improvements": evolution_data.get("expected_improvements", [])
        }
        
        with open(backup_dir / "evolution_log.json", 'w') as f:
            json.dump(evolution_log, f, indent=2)
        
        print(f"[Alpha Evolve] System evolution applied for iteration {iteration}")
        return True
        
    except Exception as e:
        print(f"[Alpha Evolve] Error applying evolution: {e}")
        return False

def call_generator_agent(previous_config_code: str, validation_feedback: str, model_name: str, iteration: int = 1) -> str:
    """Calls Gemini model for generating new configuration file with Alpha Evolve."""
    print("[Generator Agent] Feedback received. Generating new parameters...")
    
    # Alpha Evolve: Check if we should evolve the system
    if iteration > 1 and iteration % 5 == 0:  # Every 5 iterations
        print(f"[Alpha Evolve] Triggering full system evolution at iteration {iteration}")
        evolution_result = evolve_system_files(iteration, model_name)
        
        if evolution_result["status"] == "success":
            apply_system_evolution(evolution_result["evolution_data"], iteration)
        else:
            print(f"[Alpha Evolve] Evolution failed: {evolution_result.get('message', 'Unknown error')}")
    
    # Alpha Evolve: Analyze history
    history_analysis = analyze_validation_history()
    print(f"[Alpha Evolve] History analysis: {history_analysis}")
    
    # Alpha Evolve: Load complete agent context
    context_file = Path("run_history") / f"iteration_{iteration}" / "agent_context.md"
    agent_context = ""
    if context_file.exists():
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                agent_context = f.read()
            print(f"[Alpha Evolve] Agent context loaded: {len(agent_context)} characters")
        except Exception as e:
            print(f"[Alpha Evolve] Error loading context: {e}")
    else:
        print(f"[Alpha Evolve] Agent context not found for iteration {iteration}")
    
    # Alpha Evolve: Check for degradation with improved logic
    total_iterations = history_analysis.get("total_iterations", 0)
    trend = history_analysis.get("trend", "unknown")
    
    # Early degradation detection (after 2 iterations)
    if trend == "degrading" and total_iterations >= 2:
        print(f"[Alpha Evolve] Degradation detected after {total_iterations} iterations! Loading best version...")
        best_code = load_best_code_version()
        if best_code:
            print("[Alpha Evolve] Reverting to best code version")
            return best_code
        else:
            print("[Alpha Evolve] No previous version available, continuing with current")
    
    # Additional protection for insufficient data
    if trend == "insufficient_data" and total_iterations >= 1:
        print(f"[Alpha Evolve] Insufficient data for trend analysis after {total_iterations} iterations")
        print("[Alpha Evolve] Using conservative approach for first iterations")
    
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
        print("[Generator Agent] ERROR: API key not configured. Returning old code.")
        print("[Generator Agent] Please set GEMINI_API_KEY or GOOGLE_API_KEY environment variable")
        print("[Generator Agent] Or create .env file with your API key")
        return previous_config_code
    
    try:
        model = genai.GenerativeModel(model_name)
        
        # Alpha Evolve: Enhanced prompt with history consideration
        history_context = ""
        if history_analysis.get("total_iterations", 0) > 0:
            history_context = f"""
        **ALPHA EVOLVE CONTEXT:**
        - Current iteration: {iteration}
        - Total iterations: {history_analysis.get('total_iterations', 0)}
        - Quality trend: {history_analysis.get('trend', 'unknown')}
        - If trend 'degrading', be more conservative in changes
        - If trend 'improving', continue in same direction
        - If trend 'stable', try new approaches
        - If trend 'insufficient_data', use conservative approach for early iterations
        
        **COMPLETE AGENT CONTEXT:**
        {agent_context[:2000] + "..." if len(agent_context) > 2000 else agent_context}
        """
        
        prompt = f"""
        You are an advanced Python programmer with Alpha Evolve capabilities, modifying a configuration file for a medical imaging simulation.
        You can learn from previous iterations and adapt your approach based on validation feedback history.

        {history_context}

        **PARAMETER GUIDE:**
        {KNOWLEDGE_BASE}

        **CURRENT CONFIGURATION FILE (`config_skin_regions.py`):**
        ```python
        {previous_config_code}
        ```

        **USER FEEDBACK TO ADDRESS:**
        "{validation_feedback}"

        **YOUR TASK:**
        Output the entire, complete, and syntactically correct Python code for the new `config_skin_regions.py` file.
        - Only change the numerical values.
        - Do not add, remove, or rename any variables.
        - Consider the validation history and adapt your approach accordingly.
        - Your output must be ONLY the Python code block.
        """
        
        response = model.generate_content(prompt)
        new_code = response.text.strip().replace("```python", "").replace("```", "")
        
        # Alpha Evolve: Save code version
        save_code_version(new_code, iteration)
        
        print("[Generator Agent] New configuration generated with Alpha Evolve.")
        return new_code.strip()
    except Exception as e:
        print(f"[Generator Agent] CRITICAL ERROR during API call: {e}")
        return previous_config_code