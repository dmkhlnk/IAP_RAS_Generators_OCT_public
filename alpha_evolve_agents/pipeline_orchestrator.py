# pipeline_orchestrator.py - Alpha Evolve OCT Scan Generation Pipeline

import os
import subprocess
import sys
import glob
import shutil
import configparser
import re
import time
import matplotlib.pyplot as plt
from IPython.display import display, Image, Markdown, clear_output
import shutil
import psutil

from agent_generator import call_generator_agent
from agent_validator import run_validation_test, format_justification, detailed_quality_metrics, multi_model_validation

PYTHON_EXECUTABLE = sys.executable
REAL_SCANS_DIR = "real_scans_png"
GENERATOR_OUTPUT_DIR = "synthetic_oct_data_final" 
HISTORY_DIR = "run_history"
CONFIG_FILE_TO_MODIFY = "config_skin_regions.py"
INITIAL_CONFIG_BACKUP = "config_skin_regions.initial.bak"
GENERATOR_SCRIPT = "main_oct_generator_corrected.py" 
OCT_SCANNING_SCRIPT = "OCTPhantomVirtualScanning.py"
CONVERTER_SCRIPT = "converter.py"
CONFIG_TEMPLATE_FILE = "configuration.ini"

def run_command(command_list):
    print(f"\n[ORCHESTRATOR] Executing: {' '.join(command_list)}")
    try:
        process = subprocess.run(
            command_list, check=True, capture_output=True, text=True, encoding='utf-8', errors='replace'
        )
        if process.stderr: print(f"[ORCHESTRATOR] Warnings:\n{process.stderr}")
        print(f"[ORCHESTRATOR] Command '{os.path.basename(command_list[1])}' completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ORCHESTRATOR] CRITICAL ERROR: {' '.join(command_list)}")
        print(f"  Return code: {e.returncode}\n  Output:\n{e.stdout}\n  Errors:\n{e.stderr}")
        return False

def run_command_with_progress(command_list):
    print(f"\n[ORCHESTRATOR] Executing with progress output: {' '.join(command_list)}")
    process = subprocess.Popen(
        command_list, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
        text=True, encoding='utf-8', errors='replace', bufsize=1
    )
    while True:
        line = process.stdout.readline()
        if not line: break
        print(line, end='')
    return_code = process.wait()
    if return_code == 0:
        print(f"[ORCHESTRATOR] Command '{os.path.basename(command_list[1])}' completed successfully.")
        return True
    else:
        print(f"[ORCHESTRATOR] CRITICAL ERROR: Command '{os.path.basename(command_list[1])}' failed with code {return_code}.")
        return False

def setup_environment():
    os.makedirs(REAL_SCANS_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    if not os.listdir(REAL_SCANS_DIR):
        print(f"Reference scans directory '{REAL_SCANS_DIR}' is empty. Starting converter...")
        if not run_command([PYTHON_EXECUTABLE, CONVERTER_SCRIPT]): sys.exit(1)
    else:
        print(f"Reference scans directory '{REAL_SCANS_DIR}' already exists.")

    if os.path.exists(CONFIG_FILE_TO_MODIFY) and not os.path.exists(INITIAL_CONFIG_BACKUP):
        shutil.copy(CONFIG_FILE_TO_MODIFY, INITIAL_CONFIG_BACKUP)
        print(f"Initial configuration '{CONFIG_FILE_TO_MODIFY}' backed up to '{INITIAL_CONFIG_BACKUP}'.")

def cleanup_environment():
    if os.path.exists(INITIAL_CONFIG_BACKUP):
        shutil.move(INITIAL_CONFIG_BACKUP, CONFIG_FILE_TO_MODIFY)
        print(f"\n[ORCHESTRATOR] Initial configuration '{CONFIG_FILE_TO_MODIFY}' restored.")

def generate_and_scan_batch(num_variations, iteration_num):
    # Create directory for current iteration
    iteration_dir = os.path.join(HISTORY_DIR, f"iteration_{iteration_num}")
    os.makedirs(iteration_dir, exist_ok=True)
    
    # Set output directory for generator
    current_output_dir = os.path.join(iteration_dir, "generation_output")
    if os.path.exists(current_output_dir): 
        shutil.rmtree(current_output_dir)
    os.makedirs(current_output_dir, exist_ok=True)
    
    # Temporarily change output directory
    global GENERATOR_OUTPUT_DIR
    original_output_dir = GENERATOR_OUTPUT_DIR
    GENERATOR_OUTPUT_DIR = current_output_dir
    os.environ["GENERATOR_OUTPUT_DIR"] = current_output_dir
    
    if not run_command([PYTHON_EXECUTABLE, GENERATOR_SCRIPT]): 
        GENERATOR_OUTPUT_DIR = original_output_dir
        return []
    
    ini_files = sorted(glob.glob(os.path.join(GENERATOR_OUTPUT_DIR, "*_Configuration_for_scanning.ini")))
    if not ini_files:
        print(f"[ORCHESTRATOR] CRITICAL ERROR: .ini files not found in '{GENERATOR_OUTPUT_DIR}'.")
        GENERATOR_OUTPUT_DIR = original_output_dir
        return []
    
    print(f"[ORCHESTRATOR] .ini files found ({len(ini_files)} files). Starting scanning process.")
    
    generated_scans = []
    for ini_file_path in ini_files:
        if not run_command_with_progress([PYTHON_EXECUTABLE, OCT_SCANNING_SCRIPT, "--config", ini_file_path]):
            continue
        
        base_name = os.path.basename(ini_file_path).replace("_Configuration_for_scanning.ini", "")
        final_png_path = os.path.join(current_output_dir, f"{base_name}_Image_gray.png")
        if os.path.exists(final_png_path):
            generated_scans.append(final_png_path)
    
    # Restore original directory
    os.environ["GENERATOR_OUTPUT_DIR"] = original_output_dir
    GENERATOR_OUTPUT_DIR = original_output_dir
    return generated_scans

def display_lineup(lineup_data):
    num_images = len(lineup_data)
    fig, axes = plt.subplots(1, num_images, figsize=(20, 5))
    if num_images == 1: axes = [axes]
    for i, (path, img_type) in enumerate(lineup_data):
        try:
            img = plt.imread(path)
            ax = axes[i]; ax.imshow(img, cmap='gray')
            title = f"Image {i+1}\n"
            if img_type == 'fake': 
                title += "(SYNTHETIC)"; ax.set_title(title, color='red', fontsize=12, fontweight='bold')
            else: 
                title += "(REAL)"; ax.set_title(title, color='green', fontsize=12)
            ax.axis('off')
        except Exception:
            axes[i].set_title(f"Image {i+1}\nNOT FOUND", color='orange'); axes[i].axis('off')
    plt.tight_layout(); plt.show()

def run_pipeline(model_name: str, max_iterations: int, num_variations: int, patient_id: str = "patient01", auto_stop_on_success: bool = False, success_threshold: str = "Low"):
    # Clear run_history for new iterations
    if os.path.exists(HISTORY_DIR):
        shutil.rmtree(HISTORY_DIR)
        print(f"[ORCHESTRATOR] run_history cleared for new iterations")
    os.makedirs(HISTORY_DIR, exist_ok=True)
    if not os.getenv('GOOGLE_API_KEY'):
        print("CRITICAL ERROR: GOOGLE_API_KEY environment variable not set.")
        return

    setup_environment()
    
    # Set environment variable for generator
    os.environ['TARGET_PATIENT_ID'] = patient_id
    print(f"[ORCHESTRATOR] Target patient set for generation: {patient_id}")
    
    feedback_for_next_gen = "Initial run. Generate a baseline scan."
    
    try:
        for i in range(1, max_iterations + 1):
            # Create full context for agents
            from agent_generator import create_agent_context_summary
            from agent_validator import load_validator_context
            create_agent_context_summary(i)
            load_validator_context(i)
            
            # Alpha Evolve: Check for system evolution opportunities
            if i > 1 and i % 3 == 0:  # Every 3 iterations
                print(f"[Alpha Evolve] Triggering system evolution at iteration {i}")
                
                # Generator evolution
                from agent_generator import evolve_system_files, apply_system_evolution
                evolution_result = evolve_system_files(i, model_name)
                
                if evolution_result["status"] == "success":
                    apply_system_evolution(evolution_result["evolution_data"], i)
                    print(f"[Alpha Evolve] System evolution applied for iteration {i}")
                else:
                    print(f"[Alpha Evolve] Evolution failed: {evolution_result.get('message', 'Unknown error')}")
                
                # Validator evolution
                from agent_validator import evolve_validator_system
                validator_evolution = evolve_validator_system(i, model_name)
                
                if validator_evolution["status"] == "success":
                    print(f"[Alpha Evolve] Validator evolution completed for iteration {i}")
                else:
                    print(f"[Alpha Evolve] Validator evolution failed: {validator_evolution.get('message', 'Unknown error')}")
            
            clear_output(wait=True)
            display(Markdown(f"# <font color='orange'>ITERATION {i}/{max_iterations}</font>"))
            display(Markdown("---"))
            display(Markdown("### Step 1: Generator Agent and Scan Generation"))

            if i > 1:
                with open(CONFIG_FILE_TO_MODIFY, 'r', encoding='utf-8') as f:
                    current_config_code = f.read()
                new_config_code = call_generator_agent(current_config_code, feedback_for_next_gen, model_name, i)
                with open(CONFIG_FILE_TO_MODIFY, 'w', encoding='utf-8') as f:
                    f.write(new_config_code)
                print(f"[ORCHESTRATOR] File '{CONFIG_FILE_TO_MODIFY}' updated by AI agent.")

            generated_scan_paths = generate_and_scan_batch(num_variations, i)
            if not generated_scan_paths:
                print("Failed to generate any scans. Pipeline terminated."); break
            
            display(Markdown(f"**Generated {len(generated_scan_paths)} scans for analysis.**"))
            display(Markdown("---"))
            display(Markdown("### Step 2: Validation of Generated Scans"))
            
            validation_results = []
            successful_scans = []
            
            for idx, scan_path in enumerate(generated_scan_paths):
                display(Markdown(f"#### Analysis of scan {idx + 1}/{len(generated_scan_paths)}: `{os.path.basename(scan_path)}`"))
                validation_result = run_validation_test(scan_path, REAL_SCANS_DIR, model_name, i)
                
                # API rate limiting pause (optimization from colleague's project)
                if idx < len(generated_scan_paths) - 1:  # Don't pause after last scan
                    print(f"  - Pausing 15 seconds for API rate limiting...")
                    time.sleep(15)
                if 'lineup' in validation_result and validation_result['lineup']:
                    display_lineup(validation_result['lineup'])
                if "error" in validation_result:
                    print(f"Validation error: {validation_result['error']}")
                    if "raw_response" in validation_result:
                        print("\n--- RAW GEMINI RESPONSE ---\n", validation_result["raw_response"], "\n---------------------------\n")
                    continue
                
                verdict = validation_result.get("final_verdict", {})
                is_success = (verdict.get("identified_synthetic_image_index") != validation_result.get("correct_index"))
                validation_results.append({
                    "path": scan_path,
                    "feedback": verdict.get("detailed_justification_chain_of_thought", ""),
                    "confidence": verdict.get("confidence_level", "Low"),
                    "success": is_success,
                    "verdict": verdict
                })
                if is_success:
                    display(Markdown(f"#### <font color='green'>SUCCESS! Validator deceived by scan {idx + 1}!</font>"))
                    successful_scans.append(scan_path)
                else:
                    display(Markdown(f"#### <font color='red'>Result: Validator correct.</font>"))

            display(Markdown("---"))
            display(Markdown("### Step 3: Iteration Summary"))

            if successful_scans:
                display(Markdown(f"# <font color='green'>SUCCESS!</font>"))
                print(f"Pipeline completed. Best scan: {os.path.basename(successful_scans[0])}")
                display(Image(filename=successful_scans[0]))
                break
            
            if not validation_results:
                display(Markdown("## <font color='red'>CRITICAL ERROR</font>"))
                print("No successful validation results obtained from Validator."); break

            best_scan_for_feedback = sorted(validation_results, key=lambda x: (['Low', 'Medium', 'High'].index(x['confidence']), len(x['feedback'])))[0]
            feedback_for_next_gen = best_scan_for_feedback['feedback']
            
            iter_history_dir = os.path.join(HISTORY_DIR, f"iteration_{i}")
            os.makedirs(iter_history_dir, exist_ok=True)
            
            best_scan_path = best_scan_for_feedback['path']
            base_name = os.path.basename(best_scan_path).replace("_Image_gray.png", "")
            
            # Files already in correct folder, just rename
            synthetic_scan_path = os.path.join(iter_history_dir, "synthetic_oct_scan.png")
            if best_scan_path != synthetic_scan_path:
                shutil.copy(best_scan_path, synthetic_scan_path)
            # Also save with iteration number for compatibility
            shutil.copy(best_scan_path, os.path.join(iter_history_dir, f"best_scan_iter_{i}.png"))
            # Update path for further use
            best_scan_path = synthetic_scan_path
            # Look for mask in current iteration generation folder
            iteration_generation_dir = os.path.join(iter_history_dir, "generation_output")
            mask_path_orig = os.path.join(iteration_generation_dir, f"{base_name}_masks_viz.png")
            if os.path.exists(mask_path_orig):
                shutil.copy(mask_path_orig, os.path.join(iter_history_dir, f"mask_iter_{i}.png"))
            
            with open(os.path.join(iter_history_dir, f"validator_feedback_iter_{i}.txt"), 'w', encoding='utf-8') as f:
                f.write(f"Verdict: {best_scan_for_feedback['verdict']}\n\n")
                f.write(f"Justification:\n{feedback_for_next_gen}")

            # Alpha Evolve: Save iteration result to run_history
            from agent_validator import save_validation_result, create_comparison_panel
            from agent_generator import save_code_version
            
            # Save best validation result
            if best_scan_for_feedback:
                save_validation_result(best_scan_for_feedback, i)
            
            # Create comparison panel
            create_comparison_panel(best_scan_path, REAL_SCANS_DIR, i)
            
            # Save current code version
            with open(CONFIG_FILE_TO_MODIFY, 'r', encoding='utf-8') as f:
                current_config_code = f.read()
            save_code_version(current_config_code, i)
            
            # Additional files for Alpha Evolve
            save_iteration_summary(iter_history_dir, i, best_scan_for_feedback, feedback_for_next_gen)
            
            # Create full context for agents
            
            print(f"[Alpha Evolve] Iteration {i} saved to run_history/iteration_{i}/")

            display(Markdown("#### Iteration Summary Report"))
            print(f"Best scan of this iteration (saved to history): {os.path.basename(best_scan_path)}")
            display(Image(filename=best_scan_path))
            display(Markdown("#### Validator Reasoning (used for next iteration)"))
            print(format_justification(feedback_for_next_gen))

            # Check auto-stop condition on success
            if auto_stop_on_success and best_scan_for_feedback and best_scan_for_feedback.get("success", False):
                confidence = best_scan_for_feedback.get('confidence', 'High')
                success_thresholds = {"Low": 0, "Medium": 1, "High": 2}
                current_threshold = success_thresholds.get(success_threshold, 0)
                confidence_levels = {"Low": 0, "Medium": 1, "High": 2}
                current_confidence = confidence_levels.get(confidence, 2)
                
                if current_confidence <= current_threshold:
                    display(Markdown("# <font color='green'>SUCCESS! Validator cannot distinguish generated scan from real scans!</font>"))
                    display(Markdown(f"# <font color='green'>Alpha Evolve achieved goal in {i} iterations!</font>"))
                    print(f"[Alpha Evolve] SUCCESS! Validator confidence: {confidence} (threshold: {success_threshold})")
                    break
            
            if i == max_iterations:
                display(Markdown("# <font color='blue'>Maximum iterations reached. Pipeline terminated.</font>"))
    finally:
        cleanup_environment()


def auto_backup_checkpoint(iteration: int):
    """Automatic backup for Alpha Evolve system"""
    try:
        backup_dir = f"backups/iteration_{iteration:02d}"
        os.makedirs("backups", exist_ok=True)
        
        print(f"[Auto-Backup] Creating backup for iteration {iteration}...")
        
        # Copy run_history
        if os.path.exists("run_history"):
            shutil.copytree("run_history", f"{backup_dir}/run_history")
            print(f"[Auto-Backup] run_history copied")
        
        # Copy current configuration
        if os.path.exists(CONFIG_FILE_TO_MODIFY):
            shutil.copy2(CONFIG_FILE_TO_MODIFY, f"{backup_dir}/config_skin_regions.py")
            print(f"[Auto-Backup] Configuration saved")
        
        # Create compressed archive
        archive_name = f"backup_{iteration:02d}.tar.gz"
        shutil.make_archive(f"backups/backup_{iteration:02d}", "gztar", backup_dir)
        print(f"[Auto-Backup] Archive created: {archive_name}")
        
        # Clean temporary folder
        shutil.rmtree(backup_dir)
        print(f"[Auto-Backup] Temporary files cleaned")
        
        return True
        
    except Exception as e:
        print(f"[Auto-Backup] Error creating backup: {e}")
        return False


def monitor_system_performance():
    """System resource monitoring for Alpha Evolve"""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('.')
        
        metrics = {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available_gb': memory.available / (1024**3),
            'disk_percent': disk.percent,
            'disk_free_gb': disk.free / (1024**3),
            'timestamp': time.time()
        }
        
        print(f"[System Monitor] CPU: {cpu_percent:.1f}%, RAM: {memory.percent:.1f}%, Disk: {disk.percent:.1f}%")
        
        # Warnings
        if cpu_percent > 90:
            print("[System Monitor] WARNING: HIGH CPU LOAD!")
        if memory.percent > 90:
            print("[System Monitor] WARNING: HIGH RAM USAGE!")
        if disk.percent > 90:
            print("[System Monitor] WARNING: LOW DISK SPACE!")
        
        return metrics
        
    except Exception as e:
        print(f"[System Monitor] Monitoring error: {e}")
        return None


def robust_error_recovery(error: Exception, iteration: int):
    """Intelligent error recovery for Alpha Evolve"""
    error_str = str(error).lower()
    
    print(f"[Error Recovery] Processing error: {error}")
    
    if "memory" in error_str or "out of memory" in error_str:
        print("[Error Recovery] Memory issue - reducing batch size")
        # Here we can add logic to reduce batch size
        return "reduce_batch_size"
    
    elif "api" in error_str or "rate limit" in error_str:
        print("[Error Recovery] API issue - increasing delays")
        time.sleep(30)  # Increase delay
        return "increase_delays"
    
    elif "file" in error_str or "not found" in error_str:
        print("[Error Recovery] File issue - checking paths")
        return "check_file_paths"
    
    elif "numba" in error_str or "compilation" in error_str:
        print("[Error Recovery] Numba issue - restarting compilation")
        return "restart_numba"
    
    else:
        print("[Error Recovery] Unknown error - using general recovery")
        return "general_recovery"


def save_iteration_summary(iter_dir: str, iteration: int, best_result: dict, feedback: str):
    """Saves complete iteration summary for Alpha Evolve"""
    try:
        import json
        from datetime import datetime
        
        # Create iteration summary
        summary = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "best_scan_result": {
                "verdict": best_result.get('verdict', 'Unknown'),
                "confidence": best_result.get('confidence', 'Unknown'),
                "path": best_result.get('path', ''),
                "feedback": feedback
            },
            "alpha_evolve_status": {
                "config_updated": True,
                "validation_completed": True,
                "comparison_panel_created": True,
                "code_version_saved": True
            },
            "files_in_iteration": [
                "synthetic_oct_scan.png",  # Generated scan
                "comparison_panel.png",    # Comparison panel
                "config_skin_regions.py",  # Configuration
                "validation_result.json",  # Validation result
                "iteration_summary.json",  # This summary
                "validator_feedback.txt"   # Text feedback
            ]
        }
        
        # Save summary
        summary_file = os.path.join(iter_dir, "iteration_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"[Alpha Evolve] Iteration {iteration} summary saved: {summary_file}")
        
        # Create README for iteration folder
        readme_content = f"""# Alpha Evolve - Iteration {iteration}

## 📁 Folder Contents:

### 🖼️ Images:
- `synthetic_oct_scan.png` - Best generated scan of this iteration
- `comparison_panel.png` - Comparison panel (synthetic vs real)
- `mask_iter_{iteration}.png` - Mask visualization (if available)

### ⚙️ Configuration:
- `config_skin_regions.py` - Configuration version for this iteration
- `validation_result.json` - Detailed validation result

### 📊 Analytics:
- `iteration_summary.json` - Complete iteration summary
- `validator_feedback.txt` - Text feedback from validator

## 🎯 Iteration Result:
- **Verdict**: {best_result.get('verdict', 'Unknown')}
- **Confidence**: {best_result.get('confidence', 'Unknown')}
- **Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 🔄 Alpha Evolve:
This iteration is saved for agent analysis in subsequent iterations.
Configuration and results are used to improve generation.
"""
        
        readme_file = os.path.join(iter_dir, "README.md")
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"[Alpha Evolve] README created: {readme_file}")
        
    except Exception as e:
        print(f"[Alpha Evolve] Error saving summary: {e}")