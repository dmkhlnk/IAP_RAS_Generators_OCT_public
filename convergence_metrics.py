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
    """Tracks convergence metrics across generations."""
    
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
        
        sorted_memory = sorted(memory, key=lambda x: x.get('generation', 0))
        generations = [m.get('generation', 0) for m in sorted_memory]
        scores = [m.get('difference_score', 100) for m in sorted_memory]
        
        if len(generations) < 2:
            return {"trend": "insufficient_data", "slope": 0.0}
        
        x = np.array(generations)
        y = np.array(scores)
        slope = np.polyfit(x, y, 1)[0]
        
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
        
        best_score = min(scores)
        worst_score = max(scores)
        avg_score = np.mean(scores)
        recent_avg = np.mean(scores[-3:]) if len(scores) >= 3 else avg_score
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
    
    def calculate_convergence_indicator(self, memory: List[Dict[str, Any]], 
                                       target_score: float = 10.0) -> Dict[str, Any]:
        """Calculate overall convergence indicator."""
        if not memory:
            return {"convergence_score": 0.0, "status": "no_data"}
        
        sorted_memory = sorted(memory, key=lambda x: x.get('generation', 0))
        recent_scores = [m.get('difference_score', 100) for m in sorted_memory[-5:]]
        
        if not recent_scores:
            return {"convergence_score": 0.0, "status": "no_data"}
        
        current_score = recent_scores[-1]
        convergence_score = 1.0 - (current_score / 100.0)
        
        if len(recent_scores) >= 3:
            recent_trend = np.mean(recent_scores[-3:]) - np.mean(recent_scores[-6:-3] if len(recent_scores) >= 6 else recent_scores)
            if recent_trend < 0:
                convergence_score += 0.1
            elif recent_trend > 0:
                convergence_score -= 0.1
        
        convergence_score = max(0.0, min(1.0, convergence_score))
        
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
        
        trend_metrics = self.calculate_trend_metrics(memory)
        convergence = self.calculate_convergence_indicator(memory)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_generations": len(memory),
            "trend_analysis": trend_metrics,
            "convergence_indicator": convergence
        }
        
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def plot_convergence(self, output_path: Optional[Path] = None) -> Path:
        """Generate convergence visualization plot."""
        if not MATPLOTLIB_AVAILABLE:
            raise ImportError("matplotlib is required for plotting")
        
        memory = self.load_memory()
        if not memory:
            raise ValueError("No memory data to plot")
        
        sorted_memory = sorted(memory, key=lambda x: x.get('generation', 0))
        generations = [m.get('generation', 0) for m in sorted_memory]
        scores = [m.get('difference_score', 100) for m in sorted_memory]
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        
        ax1.plot(generations, scores, 'b-o', label='Difference Score')
        ax1.axhline(y=10, color='g', linestyle='--', label='Target (10)')
        ax1.axhline(y=30, color='y', linestyle='--', label='Good (30)')
        ax1.set_xlabel('Generation')
        ax1.set_ylabel('Difference Score')
        ax1.set_title('Convergence Progress: Difference Score Over Generations')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        if len(scores) >= 3:
            window = min(5, len(scores))
            if PANDAS_AVAILABLE:
                moving_avg = pd.Series(scores).rolling(window=window).mean()
            else:
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
