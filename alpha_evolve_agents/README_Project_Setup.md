# AI OCT Alpha Evolve Project Setup

## Quick Start Guide

### 1. Installation
```bash
# Install Python dependencies
pip install -r requirements.txt

# Set up Google API key
export GOOGLE_API_KEY="your_api_key_here"
```

### 2. Automatic Data Generation
**Real scans are generated automatically!** No need to download large files.

The system will:
- Run `converter.py` to generate reference scans
- Create `real_scans_png/` folder automatically
- Use these scans for validation

### 3. Run Alpha Evolve
```bash
# Option 1: Jupyter Notebook (Recommended)
jupyter notebook pipeline_notebook.ipynb

# Option 2: Direct execution
python pipeline_orchestrator.py
```

### 4. What Gets Created Automatically
- `real_scans_png/` - Reference scans (auto-generated)
- `run_history/` - Iteration results and evolution data
- `synthetic_oct_data_final/` - Generated scans (temporary)

### 5. Key Files
- `pipeline_orchestrator.py` - Main system coordinator
- `agent_generator.py` - Generator AI agent
- `agent_validator.py` - Validator AI agent
- `config_skin_regions.py` - Anatomical parameters
- `Alpha_Evolve_System_Description.md` - Scientific documentation

### 6. System Requirements
- Python 3.9+
- Google Gemini API key
- 8GB+ RAM recommended
- GPU optional (CPU works fine)

### 7. Expected Behavior
1. System generates reference scans automatically
2. Alpha Evolve starts iterative improvement
3. Agents learn and evolve over iterations
4. Quality improves with each cycle
5. Results saved in `run_history/`

**No manual data download needed - everything is automated!**
