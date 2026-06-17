#!/usr/bin/env python3
"""
Advanced OCT Metrics Module
Metrics from scientific literature for OCT scan quality assessment
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import cv2

try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False


class AdvancedOCTMetrics:
    """Advanced metrics for OCT scan quality assessment."""
    
    def __init__(self):
        self.ssim_available = SKIMAGE_AVAILABLE
    
    def calculate_ms_ssim(self, img1: np.ndarray, img2: np.ndarray, 
                          scales: int = 5, data_range: int = 255) -> float:
        """
        Calculate Multi-Scale SSIM for OCT scans.
        Based on: Wang et al. (2003)
        """
        if not self.ssim_available:
            return 0.0
        
        weights = np.array([0.0448, 0.2856, 0.3001, 0.2363, 0.1333])
        scales = min(scales, len(weights))
        weights = weights[:scales]
        weights /= np.sum(weights)
        
        ms_ssim_score = 1.0
        current_img1 = img1.astype(np.float64)
        current_img2 = img2.astype(np.float64)
        
        for i in range(scales):
            if current_img1.shape[0] < 8 or current_img1.shape[1] < 8:
                break
            
            try:
                ssim_val = ssim(current_img1, current_img2, data_range=data_range)
                ms_ssim_score *= (ssim_val ** weights[i])
            except Exception:
                break
            
            if i < scales - 1:
                new_height = current_img1.shape[0] // 2
                new_width = current_img1.shape[1] // 2
                if new_height >= 8 and new_width >= 8:
                    current_img1 = cv2.resize(current_img1, (new_width, new_height))
                    current_img2 = cv2.resize(current_img2, (new_width, new_height))
                else:
                    break
        
        return float(ms_ssim_score)
    
    def calculate_oct_snr(self, scan: np.ndarray) -> Dict[str, float]:
        """
        Calculate OCT-specific Signal-to-Noise Ratio.
        Based on Weill Cornell presentation methodology.
        """
        scan = scan.astype(np.float64)
        flat_scan = scan.flatten()
        
        tissue_threshold = np.percentile(flat_scan, 80)
        background_threshold = np.percentile(flat_scan, 20)
        
        tissue_mask = (scan >= tissue_threshold)
        background_mask = (scan <= background_threshold)
        
        signal_region = scan[tissue_mask]
        noise_region = scan[background_mask]
        
        signal_mean = np.mean(signal_region)
        signal_std = np.std(signal_region)
        noise_mean = np.mean(noise_region)
        noise_std = np.std(noise_region)
        
        snr_linear = signal_mean / (noise_std + 1e-8)
        snr_db = 20 * np.log10(snr_linear + 1e-8)
        cnr_linear = abs(signal_mean - noise_mean) / (noise_std + 1e-8)
        cnr_db = 20 * np.log10(cnr_linear + 1e-8)
        
        return {
            'snr_linear': float(snr_linear),
            'snr_db': float(snr_db),
            'cnr_linear': float(cnr_linear),
            'cnr_db': float(cnr_db),
            'signal_mean': float(signal_mean),
            'signal_std': float(signal_std),
            'noise_mean': float(noise_mean),
            'noise_std': float(noise_std),
            'signal_to_noise_ratio': float(snr_db)
        }
