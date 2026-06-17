# main_oct_generator_corrected.py (ГИБРИДНАЯ ВЕРСИЯ)

import os
import numpy as np
import matplotlib.pyplot as plt
import configparser
import matplotlib.patches as mpatches

# Импортируем новые, качественные модули
try: from SkinDBLib import load_skin_db
except ImportError: print("Warning: SkinDBLib.py not found.")
try: from gt_variations import generate_varied_gt
except ImportError: raise ImportError("ERROR: gt_variations.py not found.")
try: from config_skin_regions import RegionParams
except ImportError: raise ImportError("ERROR: config_skin_regions.py not found.")

class GeneratorConfig:
    # Эти параметры теперь в основном для обратной совместимости,
    # т.к. реальные значения берутся из config_skin_regions или передаются оркестратором
    MAT_FILE_PATH_SKINDB = 'skin_db.mat'
    OUTPUT_DIR = os.getenv("GENERATOR_OUTPUT_DIR", "synthetic_oct_data_final") # Имя папки соответствует новому генератору
    NUM_SLICES_TO_PROCESS_PER_PATIENT = 1
    NUM_SYNTHETIC_VARIATIONS_PER_GT_SLICE = 1 # Это значение будет меняться оркестратором
    Y_DEPTH_CONST_MCM, X_MAX_MCM, VERTICAL_PIXEL_SIZE_MCM = 0.0, 3000.0, 2.2
    IMG_HEIGHT_PIXELS, IMG_WIDTH_PIXELS = 601, 975

def generate_points_in_mask(mask, num_points):
    if num_points == 0: return np.array([])
    valid_coords_row_col = np.argwhere(mask)
    if len(valid_coords_row_col) == 0: return np.array([])
    replace = num_points > len(valid_coords_row_col)
    selected_indices = np.random.choice(len(valid_coords_row_col), num_points, replace=replace)
    points_col_row = valid_coords_row_col[selected_indices][:, ::-1].astype(np.float32)
    points_col_row += np.random.uniform(0, 1, size=points_col_row.shape)
    return points_col_row

def process_oct_slice(patient_key, slice_idx, variation_idx, patient_data_entry, gen_config: GeneratorConfig, region_params: RegionParams):
    print(f"Processing: Patient '{patient_key}', DB slice #{slice_idx}, Synthetic variation #{variation_idx}")
    image_shape_pixels = (gen_config.IMG_HEIGHT_PIXELS, gen_config.IMG_WIDTH_PIXELS)
    H, W = image_shape_pixels
    try: original_gt_contours = patient_data_entry.gt[slice_idx]
    except (IndexError, TypeError, AttributeError): original_gt_contours = None
    
    # Используем новый, качественный gt_variations.py
    final_masks, label_map = generate_varied_gt(original_gt_contours, image_shape_pixels, region_params)
    print("  Anatomical masks generated.")
    
    # Эта карта теперь соответствует новому config_skin_regions.py
    mask_to_params_map = {
        "stratum_corneum": region_params.STRATUM_CORNEUM,
        "viable_epidermis": region_params.VIABLE_EPIDERMIS,
        "papillary_dermis": region_params.PAPILLARY_DERMIS,
        "reticular_dermis": region_params.RETICULAR_DERMIS,
        "hair_shaft": region_params.HAIR_SHAFT,
        "follecle_wall": region_params.FOLLICLE_WALL,
        "follecle_lumen": region_params.FOLLICLE_LUMEN,
        "follecle_transition": region_params.FOLLICLE_TRANSITION,
        "sebaceous_gland": region_params.SEBACEOUS_GLAND,
    }

    all_scatterers_list = []
    lateral_pixel_size_mcm = (2 * gen_config.X_MAX_MCM) / (W - 1) if W > 1 else 0
    
    for mask_name, params in mask_to_params_map.items():
        current_mask = final_masks.get(mask_name)
        if current_mask is None or not current_mask.any(): continue
        num_scatterers = int(params["density"] * np.sum(current_mask))
        if num_scatterers == 0: continue
        pts_px_col_row = generate_points_in_mask(current_mask, num_scatterers)
        if pts_px_col_row.shape[0] == 0: continue
        
        amplitudes = np.random.lognormal(mean=params["amplitude_logmean"], sigma=params["amplitude_logsigma"], size=pts_px_col_row.shape[0])
        final_amplitudes = np.clip(amplitudes, 0.001, 10.0)
        
        for i in range(pts_px_col_row.shape[0]):
            col_px, row_px = pts_px_col_row[i, 0], pts_px_col_row[i, 1]
            x_micron = (col_px * lateral_pixel_size_mcm) - gen_config.X_MAX_MCM
            z_micron = row_px * gen_config.VERTICAL_PIXEL_SIZE_MCM
            all_scatterers_list.append([x_micron, gen_config.Y_DEPTH_CONST_MCM, z_micron, final_amplitudes[i]])
            
    print(f"  Generated {len(all_scatterers_list)} scatterers.")
    base_filename = f"{patient_key}_slice{slice_idx}_var{variation_idx}"
    all_scatterers_np = np.array(all_scatterers_list)
    dat_filename = os.path.join(gen_config.OUTPUT_DIR, f"{base_filename}_scatterers.dat")
    if all_scatterers_np.shape[0] > 0: np.savetxt(dat_filename, all_scatterers_np, fmt="%.7e")
    
    # Создаем .ini файл
    config_scan = configparser.ConfigParser()
    config_scan.optionxform = str
    config_scan['Parameters'] = {
        "Scan Filename": f"{base_filename}.dat",
        "Scatterers coordinates File": os.path.basename(dat_filename),
        "A-scan pixel numbers": str(gen_config.IMG_HEIGHT_PIXELS),
        "Vertical pixel size mcm": str(gen_config.VERTICAL_PIXEL_SIZE_MCM),
        "Central wavelength mcm": "1.3",
        "Number of A-scans in B-scan": str(gen_config.IMG_WIDTH_PIXELS),
        "Xmax mcm": str(gen_config.X_MAX_MCM),
        "Number of B-scans": "1",
        "Ymax mcm": "0",
        "Beam Radius mcm": "6",
        "Number of scatterers in B-scan": str(all_scatterers_np.shape[0])
    }
    with open(os.path.join(gen_config.OUTPUT_DIR, f"{base_filename}_Configuration_for_scanning.ini"), 'w') as f:
        config_scan.write(f)
    
    # Создаем и сохраняем визуализацию масок
    mask_png_path = os.path.join(gen_config.OUTPUT_DIR, f"{base_filename}_masks_viz.png")
    color_map_ref = {
        0:[0,0,0], 1:[255,0,0], 2:[0,255,0], 3:[170,170,170], 4:[85,85,85],
        5:[255,255,0], 6:[128,0,0], 7:[255,182,193], 8:[10,10,10], 9:[210,180,140]
    }
    legend_labels = {
        1:"ID 1: Stratum Corneum", 2:"ID 2: Viable Epidermis", 3:"ID 3: Papillary Dermis",
        4:"ID 4: Reticular Dermis", 5:"ID 5: Hair Shaft", 6:"ID 6: Follicle Wall",
        7:"ID 7: Sebaceous Gland", 8:"ID 8: Follicle Lumen", 9:"ID 9: Follicle Transition"
    }
    viz_image_rgb = np.zeros((H, W, 3), dtype=np.uint8)
    for class_id, color in color_map_ref.items():
        if class_id in legend_labels: viz_image_rgb[label_map == class_id] = color
    plt.figure(figsize=(12, 8), dpi=100)
    plt.imshow(viz_image_rgb, interpolation='none')
    plt.title(f"Generated Masks: {base_filename}")
    plt.axis('off')
    sorted_keys = sorted(legend_labels.keys())
    patches = [mpatches.Patch(color=np.array(color_map_ref[k])/255.0, label=legend_labels[k]) for k in sorted_keys]
    plt.legend(handles=patches, loc='lower center', bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize='small')
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(mask_png_path)
    plt.close()
    print("  All output files saved.")

if __name__ == '__main__':
    gen_config = GeneratorConfig()
    region_params_instance = RegionParams()
    os.makedirs(gen_config.OUTPUT_DIR, exist_ok=True)
    
    try:
        patients_db = load_skin_db(gen_config.MAT_FILE_PATH_SKINDB)
    except Exception:
        patients_db = None
        
    if not patients_db:
        print(f"Could not load patient DB. Generating a dummy patient.")
        patients_db = {'dummy_patient': type('Patient', (), {'gt': [None]})}
    
    # --- ИЗМЕНЕНО: Генерируем только для одного пациента ---
    # Получаем ID пациента из переменной окружения или используем patient01 по умолчанию
    target_patient_id = os.getenv('TARGET_PATIENT_ID', 'patient01')
    print(f"[ГЕНЕРАТОР] Генерация только для пациента: {target_patient_id}")
    
    # Ищем нужного пациента в базе данных
    target_patient_data = None
    for patient_key, patient_data in patients_db.items():
        if patient_key == target_patient_id:
            target_patient_data = patient_data
            break
    
    if target_patient_data is None:
        print(f"[ГЕНЕРАТОР] Пациент {target_patient_id} не найден в базе данных!")
        print(f"[ГЕНЕРАТОР] Доступные пациенты: {list(patients_db.keys())}")
        # Используем первого доступного пациента
        target_patient_id = list(patients_db.keys())[0]
        target_patient_data = patients_db[target_patient_id]
        print(f"[ГЕНЕРАТОР] Используем первого доступного: {target_patient_id}")
    
    try:
        num_slices = len(target_patient_data.gt) if hasattr(target_patient_data, 'gt') and target_patient_data.gt is not None else 1
        slices_to_process = min(num_slices, gen_config.NUM_SLICES_TO_PROCESS_PER_PATIENT)
        
        for i in range(slices_to_process):
            # Оркестратор будет управлять этим параметром, чтобы создать нужное кол-во вариаций
            for var_idx in range(gen_config.NUM_SYNTHETIC_VARIATIONS_PER_GT_SLICE):
                process_oct_slice(target_patient_id, i, var_idx, target_patient_data, gen_config, region_params_instance)
    except Exception as e:
        import traceback
        print(f"CRITICAL ERROR processing {target_patient_id}: {e}")
        traceback.print_exc()
            
    print("Процесс генерации завершен.")