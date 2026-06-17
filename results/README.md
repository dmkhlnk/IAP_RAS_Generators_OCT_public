# Generation Results (Demo)

This directory contains **two demo generations** from the evolutionary pipeline, included for portfolio and reproducibility:

| Folder | Description |
|--------|-------------|
| `gen_01/` | Initial generation (baseline) |
| `gen_101/` | Final evolved generation |

## Structure per generation

```
gen_XX/
├── scatterers/              # Generated light scatterers (.dat files)
├── scans/                   # Synthetic OCT images (.png)
├── reports/                 # AI validation reports (.json) and comparison panels
├── generator_vXX.py         # Evolved generator code for this generation
└── metrics_calculator.py    # Metrics calculation code
```

## Notes

- Large binary files (`.dat`, `.png`) are stored via Git LFS.
- Full evolution history (100+ generations) is not included in the public repository to keep clone size reasonable.
- To reproduce more generations locally, run `alpha_evolve_final.py` with your own `GEMINI_API_KEY` (see `env.example`).
