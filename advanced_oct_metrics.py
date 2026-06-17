#!/usr/bin/env python3
"""
Advanced OCT Metrics Module
Implements metrics from scientific literature for OCT scan quality assessment:
- MS-SSIM (Multi-Scale Structural Similarity)
- SNR (Signal-to-Noise Ratio) 
- MMD (Maximum Mean Discrepancy)
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
import cv2

# Optional dependencies
try:
    from skimage.metrics import structural_similarity as ssim
    SKIMAGE_AVAILABLE = True
except ImportError:
    SKIMAGE_AVAILABLE = False
    print("WARNING: skimage not available. SSIM/MS-SSIM disabled.")


class AdvancedOCTMetrics:
    """
    Advanced metrics for OCT scan quality assessment.
    Based on metrics from Weill Cornell Medicine presentation.
    """
    
    def __init__(self):
        """Initialize metrics calculator"""
        self.ssim_available = SKIMAGE_AVAILABLE
    
    def calculate_ms_ssim(self, img1: np.ndarray, img2: np.ndarray, 
                          scales: int = 5, data_range: int = 255) -> float:
        """
        Calculate Multi-Scale SSIM for OCT scans.
        
        Based on: Wang et al. (2003) "Multi-scale structural similarity for image quality assessment"
        
        Args:
            img1: First image
            img2: Second image  
            scales: Number of scales (default 5)
            data_range: Maximum value of images
            
        Returns:
            MS-SSIM score (0-1, higher is better)
        """
        if not self.ssim_available:
            print("WARNING: skimage not available, skipping MS-SSIM")
            return 0.0
        
        # Weights for each scale (from literature)
        weights = np.array([0.0448, 0.2856, 0.3001, 0.2363, 0.1333])
        
        # Trim to available scales
        scales = min(scales, len(weights))
        weights = weights[:scales]
        weights /= np.sum(weights)  # Normalize
        
        ms_ssim_score = 1.0
        current_img1 = img1.astype(np.float64)
        current_img2 = img2.astype(np.float64)
        
        for i in range(scales):
            # Check if image is too small
            if current_img1.shape[0] < 8 or current_img1.shape[1] < 8:
                break
            
            # Calculate SSIM at this scale
            try:
                ssim_val = ssim(current_img1, current_img2, data_range=data_range)
                ms_ssim_score *= (ssim_val ** weights[i])
            except Exception as e:
                print(f"WARNING: SSIM calculation failed at scale {i}: {e}")
                break
            
            # Downsample for next scale
            if i < scales - 1:
                new_height = current_img1.shape[0] // 2
                new_width = current_img1.shape[1] // 2
                if new_height >= 8 and new_width >= 8:
                    current_img1 = cv2.resize(current_img1, (new_width, new_height), 
                                            interpolation=cv2.INTER_AREA)
                    current_img2 = cv2.resize(current_img2, (new_width, new_height), 
                                            interpolation=cv2.INTER_AREA)
                else:
                    break
        
        return float(ms_ssim_score)
    
    def calculate_oct_snr(self, scan: np.ndarray, tissue_mask: Optional[np.ndarray] = None,
                         background_mask: Optional[np.ndarray] = None) -> Dict[str, float]:
        """
        Calculate OCT-specific Signal-to-Noise Ratio.
        
        Based on methodology from Weill Cornell presentation:
        - Signal: Stratum Corneum or brightest homogeneous region
        - Noise: Background or darkest homogeneous region
        
        Args:
            scan: OCT scan image
            tissue_mask: Binary mask for tissue region (if None, auto-detect)
            background_mask: Binary mask for background (if None, auto-detect)
            
        Returns:
            Dictionary with SNR metrics
        """
        scan = scan.astype(np.float64)
        
        # Auto-detect regions if masks not provided
        if tissue_mask is None or background_mask is None:
            tissue_mask, background_mask = self._auto_detect_regions(scan)
        
        # Calculate signal and noise statistics
        signal_region = scan[tissue_mask]
        noise_region = scan[background_mask]
        
        signal_mean = np.mean(signal_region)
        signal_std = np.std(signal_region)
        noise_mean = np.mean(noise_region)
        noise_std = np.std(noise_region)
        
        # SNR calculation
        snr_linear = signal_mean / (noise_std + 1e-8)
        snr_db = 20 * np.log10(snr_linear + 1e-8)
        
        # CNR (Contrast-to-Noise Ratio)
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
            'signal_to_noise_ratio': float(snr_db)  # Main metric
        }
    
    def _auto_detect_regions(self, scan: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Auto-detect tissue and background regions for SNR calculation.
        
        Strategy for OCT:
        - Tissue: Top 20% pixels (brightest region, likely stratum corneum)
        - Background: Bottom 20% pixels (darkest region, likely noise)
        """
        # Flatten image and get intensity statistics
        flat_scan = scan.flatten()
        
        # Percentile-based detection
        tissue_threshold = np.percentile(flat_scan, 80)  # Top 20%
        background_threshold = np.percentile(flat_scan, 20)  # Bottom 20%
        
        tissue_mask = (scan >= tissue_threshold)
        background_mask = (scan <= background_threshold)
        
        # Ensure we have enough pixels
        if np.sum(tissue_mask) < 100:
            # Fallback: use top 10%
            tissue_threshold = np.percentile(flat_scan, 90)
            tissue_mask = (scan >= tissue_threshold)
        
        if np.sum(background_mask) < 100:
            # Fallback: use bottom 10%
            background_threshold = np.percentile(flat_scan, 10)
            background_mask = (scan <= background_threshold)
        
        return tissue_mask, background_mask
    
    def calculate_mmd(self, features_real: np.ndarray, features_generated: np.ndarray,
                     sigma: float = 1.0, sample_size: int = 1000) -> Dict[str, float]:
        """
        Calculate Maximum Mean Discrepancy (MMD) between feature distributions.
        
        Based on: Gretton et al. (2012) "A kernel two-sample test"
        
        Args:
            features_real: Feature vectors from real images
            features_generated: Feature vectors from generated images
            sigma: Gaussian kernel bandwidth
            sample_size: Maximum number of samples to use (for efficiency)
            
        Returns:
            Dictionary with MMD metrics
        """
        # Subsample if too large
        if len(features_real) > sample_size:
            indices = np.random.choice(len(features_real), sample_size, replace=False)
            features_real = features_real[indices]
        
        if len(features_generated) > sample_size:
            indices = np.random.choice(len(features_generated), sample_size, replace=False)
            features_generated = features_generated[indices]
        
        # Ensure 2D
        if features_real.ndim == 1:
            features_real = features_real.reshape(-1, 1)
        if features_generated.ndim == 1:
            features_generated = features_generated.reshape(-1, 1)
        
        # Gaussian kernel
        def gaussian_kernel(x, y, sigma):
            diff = x - y
            dist_sq = np.sum(diff**2)
            return np.exp(-dist_sq / (2 * sigma**2))
        
        # Calculate MMD² terms
        n_real = len(features_real)
        n_generated = len(features_generated)
        
        # Term 1: E[k(x, x')] for real images
        term1 = 0.0
        for i in range(n_real):
            for j in range(i+1, n_real):
                term1 += gaussian_kernel(features_real[i], features_real[j], sigma)
        term1 = 2 * term1 / (n_real * (n_real - 1) + 1e-8)
        
        # Term 2: E[k(y, y')] for generated images
        term2 = 0.0
        for i in range(n_generated):
            for j in range(i+1, n_generated):
                term2 += gaussian_kernel(features_generated[i], features_generated[j], sigma)
        term2 = 2 * term2 / (n_generated * (n_generated - 1) + 1e-8)
        
        # Term 3: -2 * E[k(x, y)] between real and generated
        term3 = 0.0
        for i in range(n_real):
            for j in range(n_generated):
                term3 += gaussian_kernel(features_real[i], features_generated[j], sigma)
        term3 = -2 * term3 / (n_real * n_generated + 1e-8)
        
        # MMD²
        mmd_squared = term1 + term2 + term3
        mmd = np.sqrt(max(0, mmd_squared))  # Ensure non-negative
        
        return {
            'mmd': float(mmd),
            'mmd_squared': float(mmd_squared),
            'sigma': float(sigma),
            'n_real_samples': int(n_real),
            'n_generated_samples': int(n_generated)
        }
    
    def extract_features_for_mmd(self, image: np.ndarray, method: str = 'intensity') -> np.ndarray:
        """
        Extract features from OCT image for MMD calculation.
        
        Args:
            image: OCT scan image
            method: Feature extraction method
                - 'intensity': Raw intensity values
                - 'gradient': Gradient magnitude
                - 'texture': Local Binary Pattern (simplified)
                
        Returns:
            Feature matrix
        """
        if method == 'intensity':
            # Use downsampled intensity patches
            patches = []
            patch_size = 8
            stride = 4
            h, w = image.shape
            
            for i in range(0, h - patch_size, stride):
                for j in range(0, w - patch_size, stride):
                    patch = image[i:i+patch_size, j:j+patch_size]
                    patches.append(patch.flatten())
            
            return np.array(patches)
        
        elif method == 'gradient':
            # Use gradient magnitude
            grad_x = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
            
            # Extract patches
            patches = []
            patch_size = 8
            stride = 8
            h, w = gradient_magnitude.shape
            
            for i in range(0, h - patch_size, stride):
                for j in range(0, w - patch_size, stride):
                    patch = gradient_magnitude[i:i+patch_size, j:j+patch_size]
                    patches.append(patch.flatten())
            
            return np.array(patches)
        
        elif method == 'texture':
            # Simplified texture features
            features = []
            patch_size = 8
            stride = 8
            h, w = image.shape
            
            for i in range(0, h - patch_size, stride):
                for j in range(0, w - patch_size, stride):
                    patch = image[i:i+patch_size, j:j+patch_size]
                    # Simple statistics
                    features.append([
                        np.mean(patch),
                        np.std(patch),
                        np.min(patch),
                        np.max(patch)
                    ])
            
            return np.array(features)
        
        else:
            raise ValueError(f"Unknown feature extraction method: {method}")
    
    def calculate_all_metrics(self, generated_scan: np.ndarray, 
                             real_scans_pool: List[np.ndarray],
                             comparison_scan: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Calculate all advanced OCT metrics.
        
        Args:
            generated_scan: Generated OCT scan
            real_scans_pool: Pool of real OCT scans for comparison
            comparison_scan: Specific real scan for comparison (if None, random)
            
        Returns:
            Dictionary with all metrics
        """
        results = {}
        
        # Select comparison scan
        if comparison_scan is None and real_scans_pool:
            comparison_scan = real_scans_pool[np.random.randint(len(real_scans_pool))]
        
        # Ensure same size
        if comparison_scan is not None and generated_scan.shape != comparison_scan.shape:
            comparison_scan = cv2.resize(comparison_scan, 
                                       (generated_scan.shape[1], generated_scan.shape[0]),
                                       interpolation=cv2.INTER_AREA)
        
        # 1. MS-SSIM
        if comparison_scan is not None:
            results['ms_ssim'] = self.calculate_ms_ssim(generated_scan, comparison_scan)
            
            # Also calculate regular SSIM if available
            if self.ssim_available:
                results['ssim'] = ssim(generated_scan, comparison_scan, data_range=255)
        
        # 2. SNR
        results['snr'] = self.calculate_oct_snr(generated_scan)
        
        # 3. MMD (if we have comparison scans)
        if real_scans_pool:
            # Extract features
            features_real_list = []
            features_generated = self.extract_features_for_mmd(generated_scan, method='intensity')
            
            for real_scan in real_scans_pool[:5]:  # Limit to 5 for efficiency
                if real_scan.shape == generated_scan.shape:
                    features = self.extract_features_for_mmd(real_scan, method='intensity')
                    features_real_list.append(features)
            
            if features_real_list:
                # Combine features from all real scans
                features_real = np.vstack(features_real_list)
                
                # Calculate MMD
                mmd_results = self.calculate_mmd(features_real, features_generated, sigma=1.0)
                results['mmd'] = mmd_results
        
        return results


def test_metrics():
    """Test the metrics implementation"""
    print("Testing Advanced OCT Metrics...")
    
    # Create dummy images
    real_img = np.random.rand(512, 512) * 255
    generated_img = real_img.copy() + np.random.randn(512, 512) * 10
    generated_img = np.clip(generated_img, 0, 255)
    
    # Calculate metrics
    metrics_calc = AdvancedOCTMetrics()
    results = metrics_calc.calculate_all_metrics(
        generated_img, 
        [real_img],
        comparison_scan=real_img
    )
    
    print("\nMetrics results:")
    for key, value in results.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key}: {sub_value}")
        else:
            print(f"{key}: {value}")


if __name__ == "__main__":
    test_metrics()

