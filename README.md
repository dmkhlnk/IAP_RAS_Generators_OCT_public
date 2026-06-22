# OCT Generators - Synthetic Optical Coherence Tomography Scan Generation System

## Overview

This repository contains a complete system for generating high-quality synthetic Optical Coherence Tomography (OCT) scans of human skin using Monte Carlo light transport simulation, morphological tissue modeling, and AI-driven validation. The system implements an evolutionary multi-agent architecture that autonomously improves synthetic data quality through iterative refinement.

## System Architecture

### Core Components

1. **Generator Module** (`Generator_v1.py`): Creates synthetic tissue structures with anatomically accurate parameters
2. **Virtual Scanner** (`virtual_scanner.py`): Simulates OCT physics to convert scatterers into realistic OCT images
3. **AI Validator** (`enhanced_validator.py`): Evaluates scan realism using Gemini AI vision analysis
4. **Evolution Engine** (`alpha_evolve_final.py`): Orchestrates autonomous improvement cycles with rollback protection
5. **Scientific Knowledge Processor** (`scientific_knowledge_processor.py`): Integrates knowledge from research literature
6. **Multi-Agent System** (`alpha_evolve_agents/`): Implements generator and validator agents with self-evolution capabilities

### Key Features

- **Evolutionary Algorithm**: Autonomous improvement across generations with automatic rollback
- **AI Validation**: Expert-level analysis powered by Google Gemini API
- **Scientific Grounding**: Based on Monte Carlo light transport and OCT morphology research
- **High Performance**: Generates 170,000+ scatterers in 30 seconds
- **Comprehensive Metrics**: SSIM, MS-SSIM, SNR, CNR, and MMD quality metrics
- **Multi-Agent Architecture**: Self-improving agents that can modify their own prompts and parameters

## System Requirements

### Software Requirements

- Python 3.9 or higher
- pip package manager
- Git (for repository cloning)

### Hardware Requirements

- Minimum 8 GB RAM (16 GB recommended)
- Multi-core CPU (parallel processing supported)
- 10 GB free disk space for generation results
- GPU optional (CPU processing works fine)

### API Requirements

- Google Gemini API key (required for AI validation)
  - Get your API key from: https://aistudio.google.com/app/apikey

## Installation

### Step 1: Clone Repository

```bash
git clone git@github.com:dmkhlnk/OCT_Generators_IAP_RAS.git
cd OCT_Generators_IAP_RAS
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure API Key

You have three options to configure your API key:

**Option 1: Using setup script (Recommended)**

```bash
./setup_api_key.sh
```

**Option 2: Manual .env file creation**

```bash
cp env.example .env
# Edit .env and add your API key: GEMINI_API_KEY=your_key_here
```

**Option 3: Environment variable**

```bash
export GEMINI_API_KEY='your_api_key_here'
```

The .env file is automatically ignored by git and will not be committed to the repository.

### Step 4: Verify Installation

Test your API key configuration:

```bash
python3 load_api_key.py
```

## Quick Start

### Basic Usage - Single Generation

Run a single generation cycle:

```bash
python3 alpha_evolve_final.py --generation 1
```

### Multi-Agent Pipeline

For the full multi-agent system with interactive evolution:

```bash
cd alpha_evolve_agents
jupyter notebook pipeline_notebook.ipynb
```

Or run directly:

```bash
cd alpha_evolve_agents
python3 pipeline_orchestrator.py
```

## Project Structure

```
OCT_Generators_IAP_RAS/
├── Generator_v1.py                    # Main tissue generator
├── virtual_scanner.py                  # OCT simulation engine
├── enhanced_validator.py               # AI validation system
├── alpha_evolve_final.py               # Evolutionary engine
├── scientific_knowledge_processor.py   # Scientific knowledge integration
├── convergence_metrics.py              # Performance tracking
├── advanced_oct_metrics.py             # Quality metrics calculator
├── load_api_key.py                     # API key management utility
├── setup_api_key.sh                    # API key setup script
├── SkinDBLib.py                        # Skin database library
├── Configuration.ini                    # Scanner configuration
├── requirements.txt                    # Python dependencies
├── env.example                         # Environment variables template
├── agent_configs/                      # Agent prompt configurations
│   ├── validator_prompt_config.json
│   └── configurator_prompt_config.json
└── alpha_evolve_agents/                # Multi-agent system
    ├── pipeline_orchestrator.py        # Main orchestrator
    ├── agent_generator.py              # Generator agent
    ├── agent_validator.py              # Validator agent
    ├── config_skin_regions.py          # Anatomical parameters
    ├── main_oct_generator_corrected.py # OCT generator
    ├── OCTPhantomVirtualScanning.py    # Virtual scanner
    └── pipeline_notebook.ipynb         # Interactive interface
```

## Usage Examples

### Running Evolution Cycle

```bash
# Run generation 1
python3 alpha_evolve_final.py --generation 1

# Run generation 2 (uses generation 1 as parent)
python3 alpha_evolve_final.py --generation 2
```

### Output Structure

All generation results are saved in the `results/` directory. Each generation creates a subdirectory with the following structure:

```
results/
└── gen_XX/
    ├── scatterers/              # Generated light scatterers (.dat files)
    ├── scans/                   # Synthetic OCT images (.png files)
    ├── reports/                 # AI validation reports (.json files)
    │   ├── validation_results.json
    │   ├── recommendations.json
    │   └── comparison_panel_labeled_*.png
    └── generator_vXX.py         # Evolved generator code
```

The `results/` directory is automatically ignored by git (.gitignore) to keep the repository clean.

## Scientific Foundation

### Research Integration

The system integrates knowledge from:

- **Monte Carlo Light Transport**: Principles for accurate photon simulation
- **OCT Morphology Research**: Tissue optical properties and structures
- **Real OCT Database**: Reference scans for validation

### AI Analysis Capabilities

- Synthetic scan identification with confidence levels
- Quality scoring on 0-100 difference scale
- Degradation detection with automatic rollback
- Parameter optimization recommendations
- Multi-model validation for robustness

## Performance Metrics

### Execution Times (typical)

- Full generation cycle: 3-5 minutes
- Scatterer generation: 10-30 seconds
- Virtual OCT scanning: 45-60 seconds (975 A-scans)
- AI validation: 15-30 seconds

### Resource Usage

- Memory: 2-4 GB RAM per generation
- CPU: Multi-core parallel processing
- Storage: 50-100 MB per generation

## Configuration

### Environment Variables

The system supports the following environment variables (set in .env file):

- `GEMINI_API_KEY`: Required. Your Google Gemini API key
- `GOOGLE_API_KEY`: Alternative name for API key (for compatibility)

### Generator Parameters

Anatomical parameters are configured in:
- `alpha_evolve_agents/config_skin_regions.py` (for multi-agent system)
- Generator code files (for evolutionary system)

## Troubleshooting

### API Key Issues

If you encounter API key errors:

1. Verify your API key is set: `python3 load_api_key.py`
2. Check .env file exists and contains valid key
3. Ensure API key has proper permissions in Google AI Studio

### Import Errors

If you see import errors:

1. Verify all dependencies are installed: `pip install -r requirements.txt`
2. Check Python version: `python3 --version` (should be 3.9+)
3. Ensure you're in the correct directory

### Performance Issues

For slow generation:

1. Reduce number of scatterers in generator configuration
2. Use fewer parallel processes
3. Check available system memory

## Limitations and Known Issues

### Current Limitations

1. System operates in HITL (Human-In-The-Loop) mode and depends on initial parameter configuration
2. After approximately 10-12 iterations, agents may cycle through parameter values without improvement, requiring human intervention
3. Quality depends on starting configuration parameters
4. Requires manual intervention to break out of parameter cycling loops

### Planned Improvements

Future development will focus on:
- Meta-learning approaches to reduce dependency on initial parameters
- Evolutionary algorithms to prevent parameter cycling
- Enhanced orchestration for increased autonomy
- Automatic detection and recovery from cycling states


## Citation

If you use this system in your research, please cite:

- Monte Carlo light transport principles
- OCT morphology research papers
- This repository

## License

See LICENSE file for details.

## Authors

**IAP RAS** (Institute of Applied Physics, Russian Academy of Sciences)

### Developers

- Daniil S. Mikhailenko<sup>a,b</sup>
- Alexander L. Matveyev<sup>a</sup>
- Lev A. Matveev<sup>a</sup>
- Denis A. Nikoshin<sup>a,b</sup>
- Alexander A. Sovetsky<sup>a</sup>
- Vladimir Y. Zaitsev<sup>a</sup>

<sup>a</sup> Institute of Applied Physics, Russian Academy of Sciences  
<sup>b</sup> Higher School of Economics
## Acknowledgments 

Funding
This project realised and published with the support of the Russian Science Foundation (RSF):
RSF Grant № 25-12-20032: "New Approaches to the Development of Algorithms for Analyzing OCT Scans: Modification and Optimization of Large Models Based on Physical Principles and Conditions of OCT Signal Formation" (https://rscf.ru/en/project/25-12-20032/)
## Support

For issues and questions:

1. Check troubleshooting section above
2. Review documentation in project files
3. Verify API key configuration
4. Check system requirements

