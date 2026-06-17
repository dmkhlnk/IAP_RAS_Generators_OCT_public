# config_skin_regions.py
import numpy as np

class RegionParams:
    DEPTH_SAFETY_MARGIN_MCM = 50.0
    # (Structure Parameters are unchanged)
    # ИСХОДНЫЕ ПЛОТНОСТИ СОХРАНЕНЫ - КАЧЕСТВО OCT СКАНОВ КРИТИЧНО!
    STRATUM_CORNEUM = { "id": 1, "amplitude_logmean": np.log(3.0), "amplitude_logsigma": 0.1, "density": 0.15 }
    VIABLE_EPIDERMIS = { "id": 2, "amplitude_logmean": np.log(0.6), "amplitude_logsigma": 0.2, "density": 0.3 }
    PAPILLARY_DERMIS = { "id": 3, "amplitude_logmean": np.log(1.1), "amplitude_logsigma": 0.25, "density": 0.30 }
    RETICULAR_DERMIS = { "id": 4, "amplitude_logmean": np.log(1.25), "amplitude_logsigma": 0.25, "density": 0.35 }
    HAIR_SHAFT = { "id": 5, "amplitude_logmean": np.log(1.5), "amplitude_logsigma": 0.2, "density": 0.1 }
    FOLLICLE_WALL = { "id": 6, "amplitude_logmean": np.log(0.8), "amplitude_logsigma": 0.2, "density": 0.25 }
    SEBACEOUS_GLAND = { "id": 7, "amplitude_logmean": np.log(2.0), "amplitude_logsigma": 0.3, "density": 0.4 }
    FOLLICLE_LUMEN = { "id": 8, "amplitude_logmean": np.log(0.08), "amplitude_logsigma": 0.1, "density": 0.05 }
    FOLLICLE_TRANSITION = { "id": 9, "amplitude_logmean": np.log(1.0), "amplitude_logsigma": 0.25, "density": 0.30 }
    
    # --- Geometric & Anatomical Parameters ---
    EPIDERMIS_VARIATION = { "rete_pegs_max_amplitude_pixels": 45, "rete_pegs_num_octaves": 4, "rete_pegs_base_frequency": 2.5 }
    PAPILLARY_DERMIS_PARAMS = { "base_thickness_pixels": 35, "thickness_variation_amplitude_pixels": 10, "thickness_variation_frequency_factor": 4 }
    
    FOLLICLE_PARAMS = {
        "count_min": 2, "count_max": 4, "min_width_pixels": 12, "max_width_pixels": 22,
        "depth_factor_min": 0.4, "depth_factor_max": 0.9, "wall_thickness_pixels": 3,
        "lumen_thickness_pixels": 1, "angle_max_rad": np.pi / 20,
        "transition_thickness_pixels": 2,
        "profile_nodes": [0.0, 0.1, 0.3, 0.7, 0.9, 1.0],
        "width_multipliers": [1.2, 0.8, 0.7, 0.75, 1.0, 1.6]
    }
    
    SEBACEOUS_GLAND_PARAMS = {
        "lobes_per_follicle_min": 1, "lobes_per_follicle_max": 2,
        "min_radius_pixels": 15, "max_radius_pixels": 40,
        "attachment_depth_mean": 0.25, "attachment_depth_std": 0.05,
        "duct_thickness_pixels": 3,
        # NEW: Parameters for multi-lobular shape
        "num_lobes_min": 3, "num_lobes_max": 6, # Number of acini per gland
        "lobe_radius_variation": 0.4 # How much lobe sizes can vary
    }
    
    STRATUM_CORNEUM_PARAMS = { "base_thickness_pixels": 4, "thickness_variation_amplitude_pixels": 1, "thickness_variation_frequency_factor": 3 }
    # (Other params unchanged)
    POSTPROCESSING = { "remove_small_objects_min_size": 20 }
    MEDSAM_OUTPUT = { "synthetic_data_path": "data/npy/SyntheticSkinDB", "imgs_subdir": "imgs", "gts_subdir": "gts", "target_size": (1024, 1024) }
    INI_PARAMS = { "scan_filename": "Scan Filename", "scatterers_coords_file": "Scatterers coordinates File", "a_scan_pixel_numbers": "A-scan pixel numbers", "vertical_pixel_size_mcm": "Vertical pixel size mcm", "central_wavelength_mcm": "Central wavelength mcm", "num_a_scans_in_b_scan": "Number of A-scans in B-scan", "x_max_mcm": "Xmax mcm", "num_b_scans": "Number of B-scans", "y_max_mcm": "Ymax mcm", "beam_radius_mcm": "Beam Radius mcm", "num_scatterers_in_b_scan": "Number of scatterers in B-scan" }
    CONFIG_INI_FOR_SCANNING_FILENAME = "Configuration_for_scanning.ini"
