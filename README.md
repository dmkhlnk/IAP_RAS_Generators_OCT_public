# IAP RAS Generators - OCT Synthetic Image Generation

**A scientific approach to generating synthetic Optical Coherence Tomography (OCT) skin scans using evolutionary algorithms and AI-driven optimization.**

## Project Overview

This project implements an autonomous system for generating realistic synthetic OCT images of human skin. It combines:

- **Physics-based OCT simulation** - Monte Carlo light propagation through skin tissue
- **Evolutionary optimization** - Iterative parameter refinement guided by AI feedback
- **Scientific grounding** - Integration of dermatological knowledge and optical theory
- **Advanced metrics** - Assessment of convergence and scan quality using literature-based metrics

## Key Features

### 1. **Advanced OCT Metrics** (`advanced_oct_metrics.py`)
- **MS-SSIM** (Multi-Scale Structural Similarity) for image quality assessment
- **SNR/CNR** (Signal-to-Noise & Contrast-to-Noise Ratios) for OCT-specific metrics
- Based on scientific literature (Wang 2003, Weill Cornell OCT research)

### 2. **Convergence Analysis** (`convergence_metrics.py`)
- Tracks evolution metrics across generations
- Detects parameter correlations and interdependencies
- Provides trend analysis and convergence indicators
- Generates visualization plots of convergence progress
- Produces actionable recommendations for next iterations

### 3. **Validation Framework** (`validator.py`)
- Panel-based assessment combining synthetic and real scans
- AI-powered analysis using multimodal LLM capabilities
- Focused on physics-relevant features (stratum corneum brightness, tissue contrast)
- Generates structured JSON recommendations for parameter adjustments

### 4. **Tissue Property Library** (`SkinDBLib.py`)
- Ground-truth tissue segmentation and mask generation
- Dice score calculations for segmentation quality
- Support for MATLAB-based skin database integration
- Morphological analysis of tissue structures

## Installation

### Requirements
- Python 3.8+
- Key dependencies (see `requirements.txt`):
  - numpy, scipy, matplotlib
  - Pillow, OpenCV, imageio
  - scikit-image
  - google-generativeai (for AI validation)
  - pandas, networkx

### Setup

```bash
# Clone repository
git clone https://github.com/dmkhlnk/IAP_RAS_Generators_OCT_public.git
cd IAP_RAS_Generators_OCT_public

# Install dependencies
pip install -r requirements.txt

# Set up API key for AI validation (optional)
export GEMINI_API_KEY="your-api-key-here"
```

## Usage

### Computing Image Quality Metrics

```python
from advanced_oct_metrics import AdvancedOCTMetrics
import cv2

metrics_calc = AdvancedOCTMetrics()

# Load images
generated = cv2.imread("synthetic.png", cv2.IMREAD_GRAYSCALE)
real = cv2.imread("real.png", cv2.IMREAD_GRAYSCALE)

# Calculate metrics
results = metrics_calc.calculate_all_metrics(
    generated, 
    [real],
    comparison_scan=real
)
```

### Analyzing Convergence

```python
from convergence_metrics import ConvergenceMetrics
from pathlib import Path

metrics = ConvergenceMetrics(Path("."))
report = metrics.generate_convergence_report()
plot_path = metrics.plot_convergence()
```

## Project Structure

```
IAP_RAS_Generators_OCT_public/
├── README.md                      # Documentation
├── requirements.txt               # Python dependencies
├── advanced_oct_metrics.py        # Quality metrics (MS-SSIM, SNR, MMD)
├── convergence_metrics.py         # Convergence tracking & analysis
├── validator.py                   # AI-powered validation
└── SkinDBLib.py                   # Tissue properties & segmentation
```

## Scientific Foundation

This project is grounded in peer-reviewed research:

- **Wang et al. (2003)** - Multi-scale structural similarity index
- **Gretton et al. (2012)** - Kernel two-sample testing (MMD)
- **Weill Cornell Medicine** - OCT diagnostic methodology
- **Monte Carlo light transport** - Physics-based simulation

## Key Metrics Explained

### MS-SSIM (Multi-Scale SSIM)
- Measures perceptual similarity across multiple scales
- Range: 0-1 (higher is better)
- Used for visual quality assessment

### OCT-Specific SNR
- Signal: Stratum corneum or bright tissue regions
- Noise: Background or dark regions
- Calculated in both linear and dB scales

### Convergence Score
- Composite metric from 0-1 indicating proximity to target quality
- Incorporates current score and trend
- Estimates generations needed to convergence

## License

MIT License

## Contact & Support

For questions or issues, please open an issue on GitHub.

---

**Note**: This is a research implementation. For production use in clinical applications, additional validation may be required.
