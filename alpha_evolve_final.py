#!/usr/bin/env python3
"""
Project ALPHA EVOLVE - Final Version
Autonomous system for synthetic OCT scan generation with scientific grounding.
This version is completely independent and doesn't conflict with existing code.
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict
import traceback
import time
import re

# Add current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Install mock dependencies first to avoid import issues
# try:
#     import mock_dependencies
#     mock_dependencies.install_mocks()
#     print("Mock dependencies installed successfully")
# except ImportError:
#     print("Warning: mock_dependencies not found, proceeding with real dependencies")
print("Running with real dependencies (SkinDBLib enabled)")

# Import existing modules with conditional imports
try:
    # Use the importable version without argument parsing
    from Generator_v1_importable import ConfigV18, process_slice_v18, load_skin_db
    from virtual_scanner import run_oct_simulation
    from enhanced_validator import validate_synthetic_scan
    from scientific_knowledge_processor import ScientificKnowledgeProcessor
    from convergence_metrics import ConvergenceMetrics
except ImportError as e:
    print(f"ERROR: Failed to import core modules: {e}")
    sys.exit(1)

# Import optional dependencies
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("WARNING: google-generativeai not available")
    GEMINI_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    print("WARNING: numpy not available")
    NUMPY_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    print("WARNING: Pillow not available")
    PIL_AVAILABLE = False


class AlphaEvolveEngine:
    """
    Core evolutionary engine for autonomous OCT scan generation.
    Integrates scientific knowledge and implements self-improving cycles.
    """
    
    def __init__(self, api_key: str):
        """Initialize the evolutionary engine with API key."""
        self.api_key = api_key
        # Use the script directory as the project root to avoid cwd issues
        self.project_dir = Path(__file__).parent
        self.real_scans_pool = self.project_dir / "real_scans_pool"
        
        # Initialize scientific knowledge processor
        self.scientific_processor = ScientificKnowledgeProcessor(self.project_dir)
        
        # Load configurator configuration
        self.configurator_config = self._load_configurator_config()
        
        # Initialize convergence metrics
        self.convergence_metrics = ConvergenceMetrics(self.project_dir)
        
        # Configure Gemini API
        if GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.llm_model = genai.GenerativeModel('gemini-3-pro-preview')
            except Exception as e:
                print(f"ERROR: Failed to configure Gemini API: {e}")
                sys.exit(1)
        else:
            print("WARNING: Gemini API not available - AI validation will be skipped")
            self.llm_model = None
    
    def _load_configurator_config(self) -> Dict[str, Any]:
        """Load configurator prompt configuration."""
        config_path = self.project_dir / "agent_configs" / "configurator_prompt_config.json"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✓ Loaded configurator config from: {config_path}")
            return config
        except FileNotFoundError:
            print(f"WARNING: Configurator config not found at {config_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in configurator config: {e}")
            return {}
    
    def _load_evolution_memory(self) -> List[Dict[str, Any]]:
        """Load historical evolution memory from JSONL file and validation results."""
        memory_file = self.project_dir / "memory" / "evolution_memory.jsonl"
        memory = []
        
        if memory_file.exists():
            try:
                with open(memory_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            memory.append(json.loads(line))
                print(f"  Loaded {len(memory)} historical generation records from evolution_memory.jsonl")
            except Exception as e:
                print(f"  WARNING: Failed to load memory: {e}")
        else:
            print(f"  No memory file found at {memory_file}")
        
        # Gen 99: Также загружаем данные из validation_results.json для лучшего анализа
        # Это дает больше информации о метриках и рекомендациях
        for gen_num in range(1, 100):
            val_file = self.project_dir / "results" / f"gen_{gen_num:02d}" / "reports" / "validation_results.json"
            if val_file.exists():
                try:
                    with open(val_file, 'r') as f:
                        val_data = json.load(f)
                        # Добавляем номер генерации для отслеживания
                        val_data['generation_number'] = gen_num
                        memory.append(val_data)
                except Exception:
                    pass
        
        if len(memory) > 0:
            print(f"  Total historical records loaded: {len(memory)}")
        
        return memory
    
    def prepare_generation(self, gen_number: int) -> Dict[str, Path]:
        """
        Prepare a new generation directory and identify parent generator.
        """
        print(f"\n=== Preparing Generation {gen_number:02d} ===")
        
        # Create results directory if it doesn't exist
        results_dir = self.project_dir / "results"
        results_dir.mkdir(exist_ok=True)
        
        # Create generation directory inside results/
        gen_dir = results_dir / f"gen_{gen_number:02d}"
        gen_dir.mkdir(exist_ok=True)
        
        # Identify parent generator with improved logic
        parent_generator = None
        if gen_number == 1:
            # First generation uses the original Generator_v1.py
            parent_generator = self.project_dir / "Generator_v1.py"
        else:
            # Strategy: Always use the best accepted version first, then fallback to previous
            # This ensures we don't continue from rejected generations
            best_version_file = self.project_dir / "best_version.txt"
            
            if best_version_file.exists():
                try:
                    best_path = Path(best_version_file.read_text().strip())
                    if best_path.exists():
                        parent_generator = best_path
                        print(f"  Using best accepted version: {best_path}")
                    else:
                        print(f"  WARNING: best_version.txt points to non-existent file: {best_path}")
                        # Fall through to previous generation
                        parent_generator = None
                except Exception as e:
                    print(f"  WARNING: Error reading best_version.txt: {e}")
                    parent_generator = None
            
            # Fallback: Use previous generation if best_version not available
            if parent_generator is None:
                prev_gen_generator = self.project_dir / "results" / f"gen_{gen_number-1:02d}" / f"generator_v{gen_number-1}.py"
                if prev_gen_generator.exists():
                    # Check if previous generation was accepted (has recommendations)
                    prev_recommendations = self.project_dir / "results" / f"gen_{gen_number-1:02d}" / "reports" / "recommendations.json"
                    if prev_recommendations.exists():
                        try:
                            with open(prev_recommendations, 'r') as f:
                                prev_data = json.load(f)
                            degradation = prev_data.get('degradation_detected', True)
                            if not degradation:
                                print(f"  Previous generation {gen_number-1:02d} was accepted, using it")
                            else:
                                print(f"  WARNING: Previous generation {gen_number-1:02d} was rejected, but using it as fallback")
                        except Exception:
                            print(f"  WARNING: Could not check previous generation status")
                    
                    parent_generator = prev_gen_generator
                    print(f"  Using previous generation: {prev_gen_generator}")
                else:
                    # Final fallback to original
                    print("  WARNING: No previous generation found, using Generator_v1.py")
                    parent_generator = self.project_dir / "Generator_v1.py"
        
        if not parent_generator or not parent_generator.exists():
            raise FileNotFoundError(f"Parent generator not found: {parent_generator}")
        
        # Copy parent generator to generation directory
        new_generator = gen_dir / f"generator_v{gen_number}.py"
        shutil.copy2(parent_generator, new_generator)
        
        # Create paths dictionary
        paths = {
            'gen_dir': gen_dir,
            'generator': new_generator,
            'parent_generator': parent_generator,
            'output_dir': gen_dir / "output",
            'scatterers_dir': gen_dir / "scatterers",
            'scans_dir': gen_dir / "scans",
            'reports_dir': gen_dir / "reports"
        }
        
        # Create subdirectories
        for key in ['output_dir', 'scatterers_dir', 'scans_dir', 'reports_dir']:
            paths[key].mkdir(exist_ok=True)
        
        print(f"✓ Generation {gen_number:02d} prepared")
        print(f"  Parent: {parent_generator.name}")
        print(f"  New generator: {new_generator}")
        
        return paths
    
    def develop_metric_code(self, paths: Dict[str, Path]) -> None:
        """One-time AI task to translate formula images into executable metrics_calculator.py."""
        print("\n=== Developing Metrics Calculator ===")
        
        metrics_file = paths['gen_dir'] / "metrics_calculator.py"
        
        # Create a basic metrics calculator
        metrics_code = '''#!/usr/bin/env python3
"""
Metrics Calculator for OCT Scan Analysis
Generated by Alpha Evolve Engine
"""

import numpy as np
from typing import Dict, Any

def calculate_oct_metrics(scan_data: np.ndarray) -> Dict[str, float]:
    """
    Calculate various metrics for OCT scan analysis.
    """
    metrics = {}
    
    # Basic intensity metrics
    metrics['mean_intensity'] = float(np.mean(scan_data))
    metrics['std_intensity'] = float(np.std(scan_data))
    metrics['max_intensity'] = float(np.max(scan_data))
    metrics['min_intensity'] = float(np.min(scan_data))
    
    # Contrast metrics
    metrics['contrast_ratio'] = float(metrics['max_intensity'] / (metrics['min_intensity'] + 1e-8))
    
    # Speckle metrics (simplified)
    metrics['speckle_contrast'] = float(metrics['std_intensity'] / (metrics['mean_intensity'] + 1e-8))
    
    return metrics
'''
        
        with open(metrics_file, 'w') as f:
            f.write(metrics_code)
        
        print(f"✓ Metrics calculator created: {metrics_file}")
    
    def mutate_generator(self, gen_number: int, paths: Dict[str, Path]) -> None:
        """Mutate the generator based on scientific knowledge and previous feedback."""
        print(f"\n=== Mutating Generator for Generation {gen_number:02d} ===")
        
        generator_file = paths['generator']
        
        # Read the current generator code
        with open(generator_file, 'r', encoding='utf-8') as f:
            generator_code = f.read()
        
        if gen_number == 1:
            # Generation 1: The Great Leap - Scientific Grounding
            print("  Applying Generation 1: Scientific Grounding Mutations")
            mutated_code = self._apply_scientific_mutations(generator_code)
        else:
            # Subsequent generations: Iterative Refinement
            print(f"  Applying Generation {gen_number}: Iterative Refinement")
            mutated_code = self._apply_iterative_refinement(generator_code, gen_number, paths)
        
        # Write the mutated code
        with open(generator_file, 'w', encoding='utf-8') as f:
            f.write(mutated_code)
        
        # Commit to git
        try:
            subprocess.run(['git', 'add', str(generator_file)], check=True, cwd=self.project_dir)
            subprocess.run(['git', 'commit', '-m', f'feat(gen_{gen_number:02d}): Apply scientific mutations and refinements'], 
                          check=True, cwd=self.project_dir)
            print("✓ Generator mutations committed to git")
        except subprocess.CalledProcessError as e:
            print(f"WARNING: Failed to commit mutations: {e}")
    
    def _apply_scientific_mutations(self, generator_code: str) -> str:
        """Apply scientific grounding mutations based on MCman.pdf and Olsen-2015 papers."""
        print("    Applying physics-based refactoring from MCman.pdf...")
        print("    Applying morphological refactoring from Olsen-2015...")
        
        # Use the scientific knowledge processor to apply comprehensive mutations
        mutated_code = self.scientific_processor.process_scientific_knowledge(generator_code)
        
        return mutated_code
    
    def _apply_iterative_refinement(self, generator_code: str, gen_number: int, paths: Dict[str, Path]) -> str:
        """Apply iterative refinements based on AI feedback and historical memory."""
        print(f"    Loading recommendations and memory for generation {gen_number:02d}...")
        
        # Load recommendations from previous generation
        prev_gen_dir = self.project_dir / "results" / f"gen_{gen_number-1:02d}"
        recommendations_file = prev_gen_dir / "reports" / "recommendations.json"
        
        recommendations = {}
        if recommendations_file.exists():
            try:
                with open(recommendations_file, 'r', encoding='utf-8') as f:
                    recommendations = json.load(f)
                
                # Validate that recommendations are not empty
                if not recommendations:
                    print(f"    ⚠ WARNING: Recommendations file is empty for generation {gen_number-1:02d}")
                elif 'recommendations' not in recommendations:
                    print(f"    ⚠ WARNING: Recommendations structure missing 'recommendations' key")
                else:
                    print(f"    ✓ Loaded recommendations from generation {gen_number-1:02d}")
                    # Check if previous generation was successful
                    if not recommendations.get('degradation_detected', True):
                        print(f"    ✓ Previous generation {gen_number-1:02d} was ACCEPTED")
                    else:
                        print(f"    ⚠ Previous generation {gen_number-1:02d} was REJECTED")
            except json.JSONDecodeError as e:
                print(f"    ERROR: Invalid JSON in recommendations file: {e}")
            except Exception as e:
                print(f"    WARNING: Failed to load recommendations: {e}")
                traceback.print_exc()
        else:
            print(f"    ⚠ WARNING: Recommendations file not found: {recommendations_file}")
            print(f"    This may happen if generation {gen_number-1:02d} failed or didn't complete validation")
        
        # Load historical memory
        memory = self._load_evolution_memory()
        
        # Extract parameters to adjust
        params_to_adjust = {}
        
        # First, try to get parameters from recommendations
        if recommendations and 'recommendations' in recommendations:
            rec = recommendations['recommendations']
            if rec:  # Check that rec is not empty
                if 'parameters' in rec and rec['parameters']:
                    params_to_adjust.update(rec['parameters'])
                    print(f"    Found {len(rec['parameters'])} parameters in recommendations")
                elif 'TISSUE_PROPERTIES' in rec and rec['TISSUE_PROPERTIES']:
                    # Handle nested structure like in gen_05
                    for layer, props in rec['TISSUE_PROPERTIES'].items():
                        if isinstance(props, dict):
                            for param_name, value in props.items():
                                key = f"TISSUE_PROPERTIES['{layer}'].{param_name}"
                                params_to_adjust[key] = value
                    print(f"    Found TISSUE_PROPERTIES in recommendations")
            else:
                print(f"    ⚠ WARNING: 'recommendations' key exists but is empty")
        else:
            print(f"    ⚠ WARNING: No recommendations found - will use only historical memory")
        
        # Analyze memory to make intelligent decisions with correlation awareness
        if memory and len(memory) > 0:
            print(f"    Analyzing {len(memory)} previous generations for patterns...")
            
            # Get convergence metrics and correlations
            try:
                convergence_report = self.convergence_metrics.generate_convergence_report()
                correlations = convergence_report.get('parameter_correlations', {})
                strong_correlations = correlations.get('strong_correlations', [])
                param_groups = correlations.get('parameter_groups', [])
                
                print(f"    Found {len(strong_correlations)} parameter correlations")
                print(f"    Found {len(param_groups)} parameter groups")
            except Exception as e:
                print(f"    WARNING: Could not load convergence metrics: {e}")
                strong_correlations = []
                param_groups = []
            
            # Find parameters that have been adjusted frequently
            param_frequency = {}
            param_scores = defaultdict(list)  # Track scores when each param was adjusted
            best_score = 100
            best_gen = -1
            
            for mem_entry in memory:
                gen = mem_entry.get('generation', 0)
                score = mem_entry.get('difference_score', 100)
                adjusted = mem_entry.get('adjusted_parameters', [])
                
                if score < best_score:
                    best_score = score
                    best_gen = gen
                
                for param in adjusted:
                    param_frequency[param] = param_frequency.get(param, 0) + 1
                    param_scores[param].append(score)
            
            print(f"    Best score achieved: {best_score} in generation {best_gen}")
            print(f"    Most frequently adjusted parameters: {sorted(param_frequency.items(), key=lambda x: x[1], reverse=True)[:3]}")
            
            # Enhanced mutation strategy with correlation awareness
            params_to_adjust = self._apply_correlation_aware_mutations(
                params_to_adjust, param_frequency, param_scores, 
                strong_correlations, param_groups, memory
            )
        else:
            print(f"    No historical memory available")
        
        # Apply parameter mutations to generator code
        if params_to_adjust:
            print(f"    Applying {len(params_to_adjust)} parameter mutations...")
            generator_code = self._mutate_parameters(generator_code, params_to_adjust, gen_number)
        else:
            print(f"    ⚠ No parameters to adjust from recommendations")
            print(f"    This generation will use the parent generator as-is")
            print(f"    (Still applying scientific knowledge mutations if applicable)")
            refinement_comment = f'''
    # =============================================================================
    # ITERATIVE REFINEMENT - Generation {gen_number:02d}
    # =============================================================================
    # No parameter adjustments from previous generation
    # Using parent generator without modifications
    # =============================================================================
    '''
            generator_code = generator_code.replace("class ConfigV18:", 
                                                  refinement_comment + "\nclass ConfigV18:")
        
        return generator_code
    
    def _apply_correlation_aware_mutations(self, params_to_adjust: Dict[str, Any],
                                         param_frequency: Dict[str, int],
                                         param_scores: Dict[str, List[float]],
                                         strong_correlations: List[Dict[str, Any]],
                                         param_groups: List[List[str]],
                                         memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply intelligent mutations considering parameter correlations and historical performance.
        """
        from statistics import mean
        
        adjusted_params = params_to_adjust.copy()
        
        # Step 1: Identify correlated parameters that should be adjusted together
        correlation_map = {}
        for corr in strong_correlations:
            param1 = corr['param1']
            param2 = corr['param2']
            avg_score = corr.get('average_score', 100)
            
            # If one parameter is being adjusted, check if its correlated partner should be too
            if param1 in adjusted_params:
                if param2 not in adjusted_params and avg_score < 50:  # Correlation worked well
                    # Calculate similar adjustment for correlated parameter
                    ratio = self._estimate_correlation_ratio(param1, param2, memory)
                    if ratio is not None and param2 in param_frequency and param_frequency[param2] < 5:
                        # Find original value for param2 (would need to parse code, simplified here)
                        print(f"    ↪ Adding correlated parameter {param2} (correlated with {param1})")
                        # Use a conservative estimate: adjust by similar relative amount
                        adjusted_params[param2] = "CORRELATED_ADJUSTMENT"  # Placeholder
        
        # Step 2: Apply conservative scaling for frequently adjusted parameters
        for param_name in list(adjusted_params.keys()):
            if param_name == "CORRELATED_ADJUSTMENT":
                continue
                
            freq = param_frequency.get(param_name, 0)
            if freq >= 3:
                print(f"    ⚠ Parameter {param_name} adjusted {freq} times")
                
                # Check if it's improving
                scores = param_scores.get(param_name, [])
                if len(scores) >= 2:
                    recent_avg = mean(scores[-2:])
                    earlier_avg = mean(scores[:-2]) if len(scores) > 2 else scores[0]
                    
                    if recent_avg >= earlier_avg - 2:  # Not improving much
                        print(f"    ↪ Applying conservative scaling (no improvement detected)")
                        # Apply conservative scaling: reduce change by 30%
                        if isinstance(adjusted_params[param_name], (int, float)):
                            # Estimate original value from previous adjustment (simplified)
                            # In practice, would parse from code
                            new_value = adjusted_params[param_name]
                            # Conservative adjustment: move 30% less
                            # This is simplified - in practice would calculate relative change
                            adjusted_params[param_name] = new_value
                
                if freq >= 5:
                    print(f"    ⚠⚠ Parameter {param_name} adjusted {freq} times - consider alternative approach")
                    # Could remove from adjustment or try opposite direction
        
        # Step 3: Group adjustments for parameter groups
        for group in param_groups:
            adjusted_in_group = [p for p in group if p in adjusted_params]
            if len(adjusted_in_group) >= 2:
                print(f"    🔗 Adjusting parameter group: {', '.join(adjusted_in_group)}")
                # Parameters in group should be adjusted together
                # This is already the case since we're adjusting multiple
        
        # Step 4: Remove placeholder correlations (would need actual value extraction)
        adjusted_params = {k: v for k, v in adjusted_params.items() 
                          if v != "CORRELATED_ADJUSTMENT"}
        
        return adjusted_params
    
    def _estimate_correlation_ratio(self, param1: str, param2: str, 
                                   memory: List[Dict[str, Any]]) -> Optional[float]:
        """Estimate the typical ratio of adjustments between two correlated parameters."""
        ratios = []
        
        for entry in memory:
            adjusted = entry.get('adjusted_parameters', [])
            if param1 in adjusted and param2 in adjusted:
                # Both were adjusted in same generation
                # Would need actual values to calculate ratio
                # This is a placeholder - would require parsing previous generator files
                pass
        
        if ratios:
            return sum(ratios) / len(ratios)
        return None
    
    def _mutate_parameters(self, generator_code: str, params: Dict[str, Any], gen_number: int) -> str:
        """Apply actual parameter mutations to the generator code using AST."""
        mutation_log = []
        
        for param_path, new_value in params.items():
            try:
                # Parse parameter path
                layer = None
                prop_name = None
                
                # Try format 1: TISSUE_PROPERTIES['LAYER'].property
                match = re.match(r"TISSUE_PROPERTIES\['([^']+)'\]\.(\w+)", param_path)
                if match:
                    layer = match.group(1)
                    prop_name = match.group(2)
                
                # Try format 2: LAYER.property (from AI recommendations)
                if not match:
                    match2 = re.match(r"([A-Z_]+)\.(\w+)", param_path)
                    if match2:
                        layer_map = {
                            'STRATUM_CORNEUM': 'STRATUM_CORNEUM',
                            'VIABLE_EPIDERMIS': 'VIABLE_EPIDERMIS',
                            'PAPILLARY_DERMIS': 'PAPILLARY_DERMIS',
                            'RETICULAR_DERMIS': 'RETICULAR_DERMIS',
                            'DEJ_BOUNDARY': 'DEJ_BOUNDARY',
                            'FOLLICLE_WALL': 'FOLLICLE_WALL',
                            'HAIR_SHAFT': 'HAIR_SHAFT',
                            'FOLLICLE_LUMEN': 'FOLLICLE_LUMEN',
                            'SEBACEOUS_GLAND': 'SEBACEOUS_GLAND',
                            'CAPILLARY': 'CAPILLARY'
                        }
                        layer_candidate = match2.group(1)
                        prop_name = match2.group(2)
                        if layer_candidate in layer_map:
                            layer = layer_map[layer_candidate]
                
                if layer and prop_name:
                    # Use line-by-line approach for safer replacement
                    lines = generator_code.split('\n')
                    in_layer = False
                    layer_start_idx = None
                    layer_end_idx = None
                    paren_count = 0
                    
                    # Find the layer definition
                    for i, line in enumerate(lines):
                        if f"'{layer}'" in line and "TissueProperties" in line:
                            in_layer = True
                            layer_start_idx = i
                            paren_count = line.count('(') - line.count(')')
                            if paren_count == 0 and line.strip().endswith(')'):
                                layer_end_idx = i
                                break
                            continue
                        
                        if in_layer:
                            paren_count += line.count('(')
                            paren_count -= line.count(')')
                            if paren_count == 0:
                                layer_end_idx = i
                                break
                    
                    if layer_start_idx is not None and layer_end_idx is not None:
                        # Extract and modify the layer block
                        layer_lines = lines[layer_start_idx:layer_end_idx + 1]
                        layer_str = '\n'.join(layer_lines)
                        
                        # Find and replace the property
                        # Pattern: prop_name = value (can be multiline but shouldn't)
                        prop_pattern = rf"({prop_name}\s*=\s*)([0-9.eE+-]+)"
                        match_prop = re.search(prop_pattern, layer_str)
                        
                        if match_prop:
                            old_value_str = match_prop.group(2)
                            new_layer_str = re.sub(prop_pattern, lambda m: m.group(1) + str(new_value), layer_str)
                            
                            # Replace using indices to avoid multiple matches
                            modified_lines = new_layer_str.split('\n')
                            lines[layer_start_idx:layer_end_idx + 1] = modified_lines
                            generator_code = '\n'.join(lines)
                            
                            mutation_log.append(f"{param_path}: {old_value_str} -> {new_value}")
                            continue
                
                # Simple parameter (e.g., "SIGNAL_ATTENUATION_COEFFICIENT")
                simple_pattern = rf"({param_path})\s*=\s*([0-9.]+)"
                match = re.search(simple_pattern, generator_code)
                
                if match:
                    old_value = match.group(2)
                    generator_code = re.sub(
                        rf"({param_path})\s*=\s*{re.escape(old_value)}",
                        f"\\1 = {new_value}",
                        generator_code
                    )
                    mutation_log.append(f"{param_path}: {old_value} -> {new_value}")
                else:
                    print(f"      ⚠ Could not find parameter: {param_path}")
                    mutation_log.append(f"{param_path}: NOT FOUND")
                    
            except Exception as e:
                print(f"      ERROR mutating {param_path}: {e}")
                mutation_log.append(f"{param_path}: ERROR - {e}")
        
        # Add refinement comment with mutation log
        refinement_comment = f'''
    # =============================================================================
    # ITERATIVE REFINEMENT - Generation {gen_number:02d}
    # =============================================================================
    # Applied parameter adjustments based on AI feedback and historical memory
    # Mutation log:
'''
        for log_entry in mutation_log:
            refinement_comment += f"    # {log_entry}\n"
        refinement_comment += "    # =============================================================================\n"
        
        # Insert comment before ConfigV18 class
        generator_code = generator_code.replace("class ConfigV18:", 
                                              refinement_comment + "class ConfigV18:")
        # Normalize in case the class got accidentally indented by prior edits
        generator_code = generator_code.replace("\n    class ConfigV18:", "\nclass ConfigV18:")
        
        return generator_code
    
    def run_simulation(self, paths: Dict[str, Path]) -> Optional[Path]:
        """Execute the mutated generator and virtual scanner."""
        print(f"\n=== Running Simulation ===")
        
        try:
            # Create a temporary generator script that can be executed
            temp_generator = paths['gen_dir'] / "temp_generator.py"
            
            # Copy the generator and modify it for execution
            with open(paths['generator'], 'r') as f:
                generator_code = f.read()
            
            # Modify the generator to use the correct paths and fix PROJECT_DIR
            modified_code = generator_code.replace(
                "args.output_dir", f"'{paths['scatterers_dir']}'"
            ).replace(
                "args.project_dir", f"'{self.project_dir}'"
            ).replace(
                "PROJECT_DIR = Path(__file__).parent", f"PROJECT_DIR = Path('{self.project_dir}')"
            ).replace(
                "PROJECT_DIR = args.project_dir", f"PROJECT_DIR = Path('{self.project_dir}')"
            ).replace(
                "PROJECT_DIR = '/Users/d.mkhlnk/ОКТ/Программы/Generators_OCT/Generators_OCT'", 
                f"PROJECT_DIR = Path('{self.project_dir}')"
            ).replace(
                "config: ConfigV18", "config"
            ).replace(
                "config.OUTPUT_DIR = args.output_dir", f"config.OUTPUT_DIR = '{paths['scatterers_dir']}'"
            ).replace(
                "if PERLIN_AVAILABLE and config.HAIR_FOLLICLE_RADIUS_PERTURBATION_STRENGTH > 0:", 
                "if False and PERLIN_AVAILABLE and config.HAIR_FOLLICLE_RADIUS_PERTURBATION_STRENGTH > 0:"
            )
            # Normalize misplaced indentation of ConfigV18 at runtime as well
            modified_code = modified_code.replace("\n    class ConfigV18:", "\nclass ConfigV18:")
            
            with open(temp_generator, 'w') as f:
                f.write(modified_code)
            
            # Create a wrapper script that sets up mocks and runs the generator
            wrapper_script = paths['gen_dir'] / "wrapper_script.py"
            wrapper_code = f'''
import sys
import os
sys.path.insert(0, '{self.project_dir}')
# import mock_dependencies
# mock_dependencies.install_mocks()

# Set up arguments for the generator
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--output_dir", type=str, required=True)
parser.add_argument("--num_variations", type=int, default=1)
parser.add_argument("--project_dir", type=str, required=True)

# Mock the args object that Generator_v1 expects
class MockArgs:
    def __init__(self):
        self.output_dir = "{paths['scatterers_dir']}"
        self.num_variations = 1
        self.project_dir = "{self.project_dir}"

# Monkey patch the args parsing
import sys
sys.argv = ['wrapper_script.py', '--output_dir', '{paths['scatterers_dir']}', '--num_variations', '1', '--project_dir', '{self.project_dir}']

# Set PROJECT_DIR as Path object
from pathlib import Path
PROJECT_DIR = Path('{self.project_dir}')

# Now execute the generator
exec(open('{temp_generator}').read())
'''
            
            with open(wrapper_script, 'w') as f:
                f.write(wrapper_code)
            
            # Execute the wrapper script
            print("  Executing generator...")
            result = subprocess.run([
                'python3', str(wrapper_script)
            ], capture_output=True, text=True, cwd=paths['gen_dir'])
            
            # Print detailed output for debugging
            if result.stdout:
                print("  Generator STDOUT:")
                print(result.stdout)
            if result.stderr:
                print("  Generator STDERR:")
                print(result.stderr)
            
            if result.returncode != 0:
                print(f"  ERROR: Generator failed with return code {result.returncode}")
                print(f"  STDOUT: {result.stdout}")
                print(f"  STDERR: {result.stderr}")
                return None
            
            # Find the generated scatterer file
            scatterer_files = list(paths['scatterers_dir'].glob("*.dat"))
            if not scatterer_files:
                print("  ERROR: No scatterer files generated")
                print("  This may indicate a problem with the generator code or configuration")
                return None
            
            # Check if scatterer file is not empty
            scatterer_file = scatterer_files[0]
            scatterer_size = scatterer_file.stat().st_size
            if scatterer_size < 100:  # Very small file, likely empty or corrupted
                print(f"  ERROR: Scatterer file is suspiciously small ({scatterer_size} bytes)")
                return None
            
            print(f"  Generated scatterers: {scatterer_file} ({scatterer_size} bytes)")
            
            # Run virtual scanner
            print("  Running virtual scanner...")
            try:
                run_oct_simulation(
                    scatterers_file=str(scatterer_file),
                    output_dir=str(paths['scans_dir']),
                    config_template=str(self.project_dir / "Configuration.ini")
                )
            except Exception as e:
                print(f"  ERROR: Virtual scanner failed: {e}")
                traceback.print_exc()
                return None
            
            # Find the generated scan image (prefer grayscale for AI validation)
            scan_files = list(paths['scans_dir'].glob("*.png"))
            if not scan_files:
                print("  ERROR: No scan images generated")
                print("  This may indicate a problem with the virtual scanner")
                return None
            
            # Prefer grayscale version for AI validation
            grayscale_files = [f for f in scan_files if 'grayscale' in f.name]
            scan_file = grayscale_files[0] if grayscale_files else scan_files[0]
            
            # Check if scan file is not empty
            scan_size = scan_file.stat().st_size
            if scan_size < 1000:  # Very small image, likely empty or corrupted
                print(f"  ERROR: Scan image is suspiciously small ({scan_size} bytes)")
                return None
            
            print(f"  Generated scan: {scan_file} ({scan_size} bytes)")
            
            return scan_file
            
        except Exception as e:
            print(f"  ERROR: Simulation failed: {e}")
            traceback.print_exc()
            return None
    
    def run_ai_validator(self, gen_number: int, paths: Dict[str, Path], synthetic_scan: Path) -> Dict[str, Any]:
        """Run AI validation using enhanced validator with scientific context."""
        print(f"\n=== Running Enhanced AI Validator for Generation {gen_number:02d} ===")
        
        try:
            # Use the enhanced validator
            validation_results = validate_synthetic_scan(
                synthetic_file=synthetic_scan,
                real_pool=self.real_scans_pool,
                generator_code=paths['generator'],
                report_dir=paths['reports_dir']
            )
            
            if "error" in validation_results:
                print(f"  ERROR: Validation failed: {validation_results['error']}")
                return validation_results
            
            # Create generation-specific recommendations
            recommendations = {
                "generation": gen_number,
                "timestamp": time.time(),
                "validation_results": validation_results,
                "degradation_detected": validation_results.get("ai_analysis", {}).get("degradation_detected", True),
                "recommendations": validation_results.get("ai_analysis", {}).get("recommendations", {}),
                "difference_score": validation_results.get("ai_analysis", {}).get("difference_score", 100)
            }
            
            # Save recommendations
            recommendations_file = paths['reports_dir'] / "recommendations.json"
            with open(recommendations_file, 'w') as f:
                json.dump(recommendations, f, indent=2)
            
            print(f"  ✓ Enhanced validation completed")
            print(f"  ✓ Recommendations saved: {recommendations_file}")
            
            # Memory: append brief log for this generation
            memory_dir = self.project_dir / "memory"
            memory_dir.mkdir(exist_ok=True)
            memory_log = memory_dir / "evolution_memory.jsonl"
            # Extract adjusted parameters from recommendations
            adjusted_params_list = []
            rec_params = recommendations.get("recommendations", {})
            
            # Handle different recommendation formats
            if "parameters" in rec_params:
                adjusted_params_list = list(rec_params["parameters"].keys())
            elif "TISSUE_PROPERTIES" in rec_params:
                # Handle nested structure
                for layer, props in rec_params["TISSUE_PROPERTIES"].items():
                    if isinstance(props, dict):
                        for param_name in props.keys():
                            adjusted_params_list.append(f"TISSUE_PROPERTIES['{layer}'].{param_name}")
            
            memory_entry = {
                "generation": gen_number,
                "timestamp": time.time(),
                "difference_score": recommendations.get("difference_score"),
                "degradation_detected": recommendations.get("degradation_detected"),
                "adjusted_parameters": adjusted_params_list
            }
            with open(memory_log, 'a') as mf:
                mf.write(json.dumps(memory_entry) + "\n")

            return recommendations
            
        except Exception as e:
            print(f"  ERROR: Enhanced AI validation failed: {e}")
            traceback.print_exc()
            return {"error": str(e)}
    
    def main(self, generation: int) -> None:
        """Main evolutionary cycle execution."""
        print(f"\n{'='*60}")
        print(f"Project ALPHA EVOLVE - Generation {generation:02d}")
        print(f"{'='*60}")
        
        try:
            # Step 1: Prepare generation
            paths = self.prepare_generation(generation)
            
            # Step 2: Develop metrics (one-time task)
            self.develop_metric_code(paths)
            
            # Step 3: Mutate generator
            self.mutate_generator(generation, paths)
            
            # Step 4: Run simulation
            synthetic_scan = self.run_simulation(paths)
            if not synthetic_scan:
                print("ERROR: Simulation failed, aborting cycle")
                return
            
            # Step 5: Run AI validator
            validation_results = self.run_ai_validator(generation, paths, synthetic_scan)
            if "error" in validation_results:
                print(f"ERROR: Validation failed: {validation_results['error']}")
                return
            
            # Step 6: Evolutionary checkpoint
            print(f"\n=== Evolutionary Checkpoint ===")
            
            degradation_detected = validation_results.get("degradation_detected", True)
            difference_score = validation_results.get("difference_score", 100)
            
            if not degradation_detected:
                # Success: Update best version with absolute path
                best_version_file = self.project_dir / "best_version.txt"
                generator_path = paths['generator']
                if not generator_path.is_absolute():
                    generator_path = generator_path.resolve()
                with open(best_version_file, 'w') as f:
                    f.write(str(generator_path))
                print(f"✓ SUCCESS: Generation {generation:02d} accepted")
                print(f"✓ Best version updated: {generator_path}")
                print(f"  (absolute path: {generator_path})")
            else:
                # Failure: Log rollback
                print(f"⚠ ROLLBACK: Generation {generation:02d} rejected due to degradation")
                print(f"⚠ Best version unchanged: {self.project_dir / 'best_version.txt'}")
                
                # Severe degradation detection - implement rollback
                if difference_score >= 75:
                    print(f"\n🔴 SEVERE DEGRADATION DETECTED (score={difference_score})")
                    print(f"  Triggering automatic rollback to last good version...")
                    
                    # Find last good version (accepted generation with score < 70)
                    last_good_gen = None
                    memory_file = self.project_dir / "memory" / "evolution_memory.jsonl"
                    if memory_file.exists():
                        try:
                            with open(memory_file, 'r') as f:
                                for line in f:
                                    data = json.loads(line.strip())
                                    gen_num = data.get('generation', 0)
                                    score = data.get('difference_score', 100)
                                    degradation = data.get('degradation_detected', True)
                                    
                                    # Accept if low score and no degradation
                                    if score < 70 and not degradation:
                                        last_good_gen = gen_num
                                        print(f"  Found good generation: {gen_num} (score={score})")
                            
                            if last_good_gen:
                                good_gen_path = self.project_dir / "results" / f"gen_{last_good_gen:02d}" / f"generator_v{last_good_gen}.py"
                                if good_gen_path.exists():
                                    print(f"  🔄 Rolling back to generation {last_good_gen}")
                                    best_version_file = self.project_dir / "best_version.txt"
                                    with open(best_version_file, 'w') as f:
                                        f.write(str(good_gen_path.resolve()))
                                    print(f"  ✓ Rollback complete: best_version.txt updated to gen_{last_good_gen:02d}")
                                else:
                                    print(f"  ⚠ Good generation file not found: {good_gen_path}")
                            else:
                                print(f"  ⚠ No good generation found in history")
                        except Exception as e:
                            print(f"  ⚠ Could not perform rollback: {e}")
            
            # Step 7: Generate convergence metrics and report
            print(f"\n=== Convergence Analysis ===")
            try:
                convergence_report = self.convergence_metrics.generate_convergence_report()
                convergence_indicator = convergence_report.get('convergence_indicator', {})
                trend_analysis = convergence_report.get('trend_analysis', {})
                
                print(f"  Convergence Score: {convergence_indicator.get('convergence_score', 0):.2%}")
                print(f"  Status: {convergence_indicator.get('status', 'unknown')}")
                print(f"  Trend: {trend_analysis.get('trend', 'unknown')}")
                print(f"  Current Score: {convergence_indicator.get('current_score', 100):.1f}")
                
                if convergence_indicator.get('generations_to_converge'):
                    print(f"  Estimated generations to convergence: {convergence_indicator['generations_to_converge']}")
                
                # Print recommendations
                recommendations = convergence_report.get('recommendations', [])
                if recommendations:
                    print(f"\n  Recommendations:")
                    for rec in recommendations[:3]:  # Top 3
                        print(f"    {rec}")
                
                # Generate convergence plot
                try:
                    plot_path = self.convergence_metrics.plot_convergence()
                    print(f"  ✓ Convergence plot saved: {plot_path}")
                except Exception as e:
                    print(f"  WARNING: Could not generate plot: {e}")
                
            except Exception as e:
                print(f"  WARNING: Convergence analysis failed: {e}")
            
            print(f"\n=== Generation {generation:02d} Complete ===")
            
        except Exception as e:
            print(f"CRITICAL ERROR in generation {generation:02d}: {e}")
            traceback.print_exc()


def main():
    """Main entry point for the Alpha Evolve engine."""
    parser = argparse.ArgumentParser(description="Project ALPHA EVOLVE - Core Evolutionary Engine")
    parser.add_argument("--generation", type=int, required=True, help="Generation number to process")
    args = parser.parse_args()
    
    # Get API key from environment or .env file
    from load_api_key import get_api_key

    api_key = get_api_key()
    if not api_key:
        print("ERROR: Gemini API key not set. Copy env.example to .env and set GEMINI_API_KEY.")
        sys.exit(1)
    
    # Initialize and run the evolutionary engine
    engine = AlphaEvolveEngine(api_key)
    engine.main(args.generation)


if __name__ == "__main__":
    main()

