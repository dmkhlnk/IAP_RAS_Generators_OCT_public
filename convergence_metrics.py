#!/usr/bin/env python3
"""
Convergence Metrics Module for Alpha Evolve
Tracks and analyzes convergence metrics to monitor evolutionary progress.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime

# Optional dependencies
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class ConvergenceMetrics:
    """
    Tracks convergence metrics across generations to monitor evolutionary progress.
    """
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.memory_file = project_dir / "memory" / "evolution_memory.jsonl"
        self.metrics_file = project_dir / "memory" / "convergence_metrics.json"
        
    def load_memory(self) -> List[Dict[str, Any]]:
        """Load all historical memory entries."""
        memory = []
        if self.memory_file.exists():
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            memory.append(json.loads(line))
            except Exception as e:
                print(f"WARNING: Failed to load memory: {e}")
        return memory
    
    def calculate_trend_metrics(self, memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate trend metrics for difference_score over generations."""
        if len(memory) < 2:
            return {"trend": "insufficient_data", "slope": 0.0}
        
        # Sort by generation number
        sorted_memory = sorted(memory, key=lambda x: x.get('generation', 0))
        generations = [m.get('generation', 0) for m in sorted_memory]
        scores = [m.get('difference_score', 100) for m in sorted_memory]
        
        if len(generations) < 2:
            return {"trend": "insufficient_data", "slope": 0.0}
        
        # Calculate linear regression slope
        x = np.array(generations)
        y = np.array(scores)
        slope = np.polyfit(x, y, 1)[0]
        
        # Determine trend
        if slope < -2.0:
            trend = "strongly_improving"
        elif slope < -0.5:
            trend = "improving"
        elif slope < 0.5:
            trend = "stable"
        elif slope < 2.0:
            trend = "worsening"
        else:
            trend = "strongly_worsening"
        
        # Calculate other metrics
        best_score = min(scores)
        worst_score = max(scores)
        avg_score = np.mean(scores)
        recent_avg = np.mean(scores[-3:]) if len(scores) >= 3 else avg_score
        
        # Improvement rate (negative slope = improvement)
        improvement_rate = -slope
        
        return {
            "trend": trend,
            "slope": float(slope),
            "improvement_rate": float(improvement_rate),
            "best_score": float(best_score),
            "worst_score": float(worst_score),
            "average_score": float(avg_score),
            "recent_average": float(recent_avg),
            "total_generations": len(generations),
            "generations": generations,
            "scores": [float(s) for s in scores]
        }
    
    def analyze_parameter_frequency(self, memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze which parameters are adjusted most frequently."""
        param_frequency = defaultdict(int)
        param_scores = defaultdict(list)  # Track scores when each param was adjusted
        
        for entry in memory:
            adjusted_params = entry.get('adjusted_parameters', [])
            score = entry.get('difference_score', 100)
            
            for param in adjusted_params:
                param_frequency[param] += 1
                param_scores[param].append(score)
        
        # Calculate average score for each parameter
        param_avg_scores = {}
        for param, scores_list in param_scores.items():
            if scores_list:
                param_avg_scores[param] = float(np.mean(scores_list))
        
        # Sort by frequency
        sorted_params = sorted(param_frequency.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "parameter_frequency": dict(param_frequency),
            "parameter_average_scores": param_avg_scores,
            "most_frequent": [p[0] for p in sorted_params[:10]],
            "total_adjustments": sum(param_frequency.values())
        }
    
    def detect_parameter_correlations(self, memory: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect correlations between parameter adjustments.
        Identifies which parameters are often adjusted together.
        """
        # Build co-occurrence matrix
        param_cooccurrence = defaultdict(lambda: defaultdict(int))
        param_pairs = []
        
        for entry in memory:
            adjusted_params = entry.get('adjusted_parameters', [])
            score = entry.get('difference_score', 100)
            
            # Track all pairs of parameters adjusted together
            for i, param1 in enumerate(adjusted_params):
                for param2 in adjusted_params[i+1:]:
                    param_cooccurrence[param1][param2] += 1
                    param_cooccurrence[param2][param1] += 1
                    param_pairs.append((param1, param2, score))
        
        # Find strongest correlations (parameters often adjusted together)
        strong_correlations = []
        for param1, related in param_cooccurrence.items():
            for param2, count in related.items():
                if count >= 2:  # Adjusted together at least 2 times
                    # Calculate average score when these params are adjusted together
                    pair_scores = [s for p1, p2, s in param_pairs 
                                  if (p1 == param1 and p2 == param2) or (p1 == param2 and p2 == param1)]
                    avg_score = np.mean(pair_scores) if pair_scores else 100
                    
                    strong_correlations.append({
                        "param1": param1,
                        "param2": param2,
                        "cooccurrence_count": count,
                        "average_score": float(avg_score)
                    })
        
        # Sort by co-occurrence count
        strong_correlations.sort(key=lambda x: x['cooccurrence_count'], reverse=True)
        
        # Find parameter groups (clusters of related parameters)
        param_groups = self._cluster_parameters(param_cooccurrence)
        
        return {
            "strong_correlations": strong_correlations[:20],  # Top 20
            "parameter_groups": param_groups,
            "total_correlations": len(strong_correlations)
        }
    
    def _cluster_parameters(self, cooccurrence: Dict[str, Dict[str, int]]) -> List[List[str]]:
        """Cluster parameters that are often adjusted together."""
        # Simple clustering: parameters that co-occur with each other frequently
        groups = []
        processed = set()
        
        for param1 in cooccurrence:
            if param1 in processed:
                continue
            
            group = [param1]
            processed.add(param1)
            
            # Find all parameters that co-occur with param1
            for param2, count in cooccurrence[param1].items():
                if count >= 2 and param2 not in processed:
                    group.append(param2)
                    processed.add(param2)
            
            if len(group) > 1:
                groups.append(group)
        
        return groups
    
    def calculate_convergence_indicator(self, memory: List[Dict[str, Any]], 
                                       target_score: float = 10.0) -> Dict[str, Any]:
        """
        Calculate overall convergence indicator.
        Returns a score from 0-1 indicating how close we are to convergence.
        """
        if not memory:
            return {"convergence_score": 0.0, "status": "no_data"}
        
        # Sort by generation
        sorted_memory = sorted(memory, key=lambda x: x.get('generation', 0))
        recent_scores = [m.get('difference_score', 100) for m in sorted_memory[-5:]]
        
        if not recent_scores:
            return {"convergence_score": 0.0, "status": "no_data"}
        
        # Current score
        current_score = recent_scores[-1]
        
        # Convergence score: 1.0 = perfect (score = 0), 0.0 = terrible (score = 100)
        convergence_score = 1.0 - (current_score / 100.0)
        
        # Trend factor: if improving, boost score
        if len(recent_scores) >= 3:
            recent_trend = np.mean(recent_scores[-3:]) - np.mean(recent_scores[-6:-3] if len(recent_scores) >= 6 else recent_scores)
            if recent_trend < 0:  # Improving
                convergence_score += 0.1
            elif recent_trend > 0:  # Worsening
                convergence_score -= 0.1
        
        convergence_score = max(0.0, min(1.0, convergence_score))
        
        # Status
        if current_score <= target_score:
            status = "converged"
        elif current_score <= 30:
            status = "near_convergence"
        elif convergence_score > 0.7:
            status = "good_progress"
        elif convergence_score > 0.4:
            status = "moderate_progress"
        else:
            status = "needs_improvement"
        
        # Generations to convergence estimate (based on trend)
        trend_metrics = self.calculate_trend_metrics(memory)
        slope = trend_metrics.get('slope', 0)
        
        if slope < 0 and current_score > target_score:
            generations_to_converge = int((current_score - target_score) / abs(slope))
        else:
            generations_to_converge = None
        
        return {
            "convergence_score": float(convergence_score),
            "current_score": float(current_score),
            "target_score": float(target_score),
            "status": status,
            "generations_to_converge": generations_to_converge,
            "recent_average": float(np.mean(recent_scores))
        }
    
    def generate_convergence_report(self) -> Dict[str, Any]:
        """Generate a comprehensive convergence report."""
        memory = self.load_memory()
        
        if not memory:
            return {"error": "No memory data available"}
        
        # Calculate all metrics
        trend_metrics = self.calculate_trend_metrics(memory)
        param_frequency = self.analyze_parameter_frequency(memory)
        correlations = self.detect_parameter_correlations(memory)
        convergence = self.calculate_convergence_indicator(memory)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_generations": len(memory),
            "trend_analysis": trend_metrics,
            "parameter_analysis": param_frequency,
            "parameter_correlations": correlations,
            "convergence_indicator": convergence,
            "recommendations": self._generate_recommendations(
                trend_metrics, param_frequency, correlations, convergence
            )
        }
        
        # Save report
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def _generate_recommendations(self, trend: Dict, params: Dict, 
                                 correlations: Dict, convergence: Dict) -> List[str]:
        """Generate actionable recommendations based on metrics."""
        recommendations = []
        
        # Trend-based recommendations
        if trend.get('trend') == 'strongly_worsening':
            recommendations.append(
                "⚠️ CRITICAL: Strong worsening trend detected. Consider reverting to previous successful generation."
            )
        elif trend.get('trend') == 'worsening':
            recommendations.append(
                "⚠️ WARNING: Worsening trend. Review recent parameter adjustments."
            )
        
        # Parameter frequency recommendations
        most_frequent = params.get('most_frequent', [])[:3]
        if most_frequent:
            recommendations.append(
                f"📊 Most frequently adjusted parameters: {', '.join(most_frequent)}. "
                "Consider if these need fundamental restructuring rather than fine-tuning."
            )
        
        # Correlation recommendations
        strong_corr = correlations.get('strong_correlations', [])[:5]
        if strong_corr:
            corr_pairs = [f"{c['param1']}-{c['param2']}" for c in strong_corr[:3]]
            recommendations.append(
                f"🔗 Strong parameter correlations detected: {', '.join(corr_pairs)}. "
                "Consider adjusting these parameters together as a group."
            )
        
        # Convergence recommendations
        status = convergence.get('status', '')
        if status == 'needs_improvement':
            recommendations.append(
                "🎯 Convergence is slow. Consider exploring new parameter spaces or adjusting mutation strategy."
            )
        elif convergence.get('generations_to_converge'):
            est_gen = convergence['generations_to_converge']
            recommendations.append(
                f"📈 Estimated {est_gen} generations to convergence based on current trend."
            )
        
        return recommendations
    
    def plot_convergence(self, output_path: Optional[Path] = None) -> Path:
        """Generate convergence visualization plot."""
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib is required for plotting. Install with: pip install matplotlib")
        
        memory = self.load_memory()
        if not memory:
            raise ValueError("No memory data to plot")
        
        sorted_memory = sorted(memory, key=lambda x: x.get('generation', 0))
        generations = [m.get('generation', 0) for m in sorted_memory]
        scores = [m.get('difference_score', 100) for m in sorted_memory]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        
        # Plot 1: Score over generations
        ax1.plot(generations, scores, 'b-o', label='Difference Score')
        ax1.axhline(y=10, color='g', linestyle='--', label='Target (10)')
        ax1.axhline(y=30, color='y', linestyle='--', label='Good (30)')
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Difference Score')
        ax1.set_title('Convergence Progress: Difference Score Over Generations')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Moving average
        if len(scores) >= 3:
            window = min(5, len(scores))
            if PANDAS_AVAILABLE:
                moving_avg = pd.Series(scores).rolling(window=window).mean()
            else:
                # Manual moving average calculation
                moving_avg = []
                for i in range(len(scores)):
                    start = max(0, i - window + 1)
                    moving_avg.append(np.mean(scores[start:i+1]))
            
            ax2.plot(generations, scores, 'b-o', alpha=0.3, label='Raw Score')
            ax2.plot(generations, moving_avg, 'r-', linewidth=2, label=f'{window}-Gen Moving Average')
            ax2.axhline(y=10, color='g', linestyle='--', label='Target (10)')
            ax2.set_xlabel('Generation')
            ax2.set_ylabel('Difference Score')
            ax2.set_title('Trend Analysis: Moving Average')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path is None:
            output_path = self.project_dir / "memory" / "convergence_plot.png"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150)
        plt.close()
        
        return output_path


if __name__ == "__main__":
    # Example usage
    project_dir = Path(__file__).parent
    metrics = ConvergenceMetrics(project_dir)
    report = metrics.generate_convergence_report()
    print(json.dumps(report, indent=2))
    
    try:
        plot_path = metrics.plot_convergence()
        print(f"\nConvergence plot saved to: {plot_path}")
    except Exception as e:
        print(f"Could not generate plot: {e}")

