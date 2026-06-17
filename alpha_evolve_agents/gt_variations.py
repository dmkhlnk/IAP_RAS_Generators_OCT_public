# gt_variations.py
import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.morphology import disk as morphology_disk, binary_erosion, binary_dilation
from skimage.draw import disk as draw_disk, ellipse, line as draw_line
from SkinDBLib import generate_gt_masks as skindb_generate_gt_masks
from config_skin_regions import RegionParams

def _get_boundary_line(mask, boundary_type='upper'):
    H, W = mask.shape; line_y = np.zeros(W, dtype=int)
    if not mask.any(): return np.full(W, H-1 if boundary_type == 'lower' else 0, dtype=int)
    for x_col in range(W):
        col_pixels_y = np.where(mask[:, x_col])[0]
        if len(col_pixels_y) > 0: line_y[x_col] = np.min(col_pixels_y) if boundary_type == 'upper' else np.max(col_pixels_y)
        else:
            if x_col > 0: line_y[x_col] = line_y[x_col-1]
            else:
                all_y = np.where(mask)[0]
                if len(all_y) > 0: line_y[x_col] = np.min(all_y) if boundary_type == 'upper' else np.max(all_y)
                else: line_y[x_col] = 0 if boundary_type == 'upper' else H - 1
    return line_y

def _create_mask_from_lines(upper_line_y, lower_line_y, W, H):
    y_coords, _ = np.ogrid[:H, :W]; return (y_coords > upper_line_y) & (y_coords <= lower_line_y)

def _generate_multi_frequency_noise(num_points, max_amplitude, num_octaves=4, base_frequency=2.0, persistence=0.5):
    total_noise = np.zeros(num_points); x = np.linspace(0, 1, num_points)
    current_max_amp = 0
    for i in range(num_octaves):
        frequency = base_frequency * (2**i)
        amplitude = max_amplitude * (persistence**i)
        current_max_amp += amplitude
        phase = np.random.uniform(0, 2 * np.pi)
        total_noise += amplitude * np.sin(2 * np.pi * frequency * x + phase)
    if current_max_amp > 0: total_noise = (total_noise / current_max_amp) * max_amplitude
    return total_noise

def _generate_gland_lobules(center_x, center_y, base_radius, H, W, params):
    num_lobes = np.random.randint(params["num_lobes_min"], params["num_lobes_max"] + 1)
    gland_mask = np.zeros((H, W), dtype=bool)
    for _ in range(num_lobes):
        lobe_radius = base_radius * np.random.uniform(1.0 - params["lobe_radius_variation"], 1.0 + params["lobe_radius_variation"])
        offset_angle = np.random.uniform(0, 2 * np.pi)
        offset_dist = np.random.uniform(0, base_radius * 0.5)
        lobe_center_x = int(center_x + offset_dist * np.cos(offset_angle))
        lobe_center_y = int(center_y + offset_dist * np.sin(offset_angle))
        ry = lobe_radius * np.random.uniform(0.7, 1.3)
        rx = lobe_radius * np.random.uniform(0.7, 1.3)
        rotation = np.random.uniform(0, np.pi)
        rr, cc = ellipse(int(lobe_center_y), int(lobe_center_x), r_radius=int(ry), c_radius=int(rx), shape=(H,W), rotation=rotation)
        gland_mask[rr, cc] = True
    return gland_mask

def _generate_sebaceous_glands(follicles, available_dermis, H, W, config_params: RegionParams):
    params = config_params.SEBACEOUS_GLAND_PARAMS
    glands_mask = np.zeros_like(available_dermis)
    for follicle in follicles:
        if not follicle['is_anagen']: continue
        num_lobes = np.random.randint(params["lobes_per_follicle_min"], params["lobes_per_follicle_max"] + 1)
        if num_lobes == 0: continue
        
        attachment_depth = np.random.normal(params["attachment_depth_mean"], params["attachment_depth_std"])
        attachment_idx = int(np.clip(attachment_depth, 0.15, 0.35) * len(follicle['path']))
        attach_x, attach_y = follicle['path'][attachment_idx]
        
        side_angle = follicle['angle'] + (np.pi/2 if np.random.rand() > 0.5 else -np.pi/2)
        
        base_radius = follicle['width'] * np.random.uniform(1.2, 2.0)
        base_radius = np.clip(base_radius, params["min_radius_pixels"], params["max_radius_pixels"])
        
        offset = base_radius * 0.6 + follicle['width_profile'][attachment_idx]
        center_x = attach_x + offset * np.cos(side_angle)
        center_y = attach_y + offset * np.sin(side_angle)
        
        gland_body = _generate_gland_lobules(center_x, center_y, base_radius, H, W, params)
        glands_mask |= gland_body
        
        rr_duct, cc_duct = draw_line(int(center_y), int(center_x), int(attach_y), int(attach_x))
        
        # --- ИСПРАВЛЕНО: Обрезаем координаты, чтобы они не выходили за границы ---
        rr_duct = np.clip(rr_duct, 0, H - 1)
        cc_duct = np.clip(cc_duct, 0, W - 1)
        # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

        duct_mask = np.zeros_like(glands_mask)
        duct_mask[rr_duct, cc_duct] = True
        duct_mask = binary_dilation(duct_mask, footprint=morphology_disk(params["duct_thickness_pixels"]))
        glands_mask |= duct_mask

    return glands_mask & available_dermis

def _generate_follicles(dej_line, H, W, config_params: RegionParams):
    params = config_params.FOLLICLE_PARAMS
    num_follicles = np.random.randint(params["count_min"], params["count_max"] + 1)
    masks = {"wall": np.zeros((H,W), bool), "lumen": np.zeros((H,W), bool), "shaft": np.zeros((H,W), bool), "transition": np.zeros((H,W), bool)}
    placed_follicles = []
    
    possible_x = np.arange(W); np.random.shuffle(possible_x)
    for x_start in possible_x:
        if len(placed_follicles) >= num_follicles: break
        
        is_anagen = np.random.rand() < 0.8
        depth_multiplier = np.random.uniform(0.8, 1.0) if is_anagen else np.random.uniform(0.3, 0.6)
        bulb_multiplier = 1.0 if is_anagen else 0.6

        y_start = dej_line[x_start]
        width = np.random.uniform(params["min_width_pixels"], params["max_width_pixels"])
        max_depth = (H - y_start - 1) * params["depth_factor_max"]
        depth = max_depth * depth_multiplier
        if depth < width * 3: continue

        angle = np.random.uniform(-params["angle_max_rad"], params["angle_max_rad"])
        path_len = int(depth)
        path_x = np.linspace(x_start, x_start + depth * np.sin(angle), path_len)
        path_y = np.linspace(y_start, y_start + depth * np.cos(angle), path_len)
        
        profile_nodes = np.array(params["profile_nodes"]); width_multipliers = np.array(params["width_multipliers"])
        path_progress = np.linspace(1, 0, path_len); width_profile = np.interp(path_progress, profile_nodes, width_multipliers) * (width / 2)

        temp_mask_outer = np.zeros((H,W), bool)
        for i in range(path_len):
            rr, cc = draw_disk((int(path_y[i]), int(path_x[i])), radius=int(width_profile[i]), shape=(H,W))
            temp_mask_outer[rr, cc] = True
        
        bx, by = path_x[-1], path_y[-1]; bulb_radius = width_profile[-1] * 1.2 * bulb_multiplier
        bulb_mask = np.zeros_like(temp_mask_outer); rr, cc = draw_disk((int(by), int(bx)), radius=int(bulb_radius), shape=(H,W)); bulb_mask[rr, cc] = True
        papilla_indent_radius = bulb_radius * 0.5; papilla_center_y = by + papilla_indent_radius * 0.8
        rr, cc = draw_disk((int(papilla_center_y), int(bx)), radius=int(papilla_indent_radius), shape=(H,W)); bulb_mask[rr, cc] = False
        temp_mask_outer |= bulb_mask
        
        se_transition = morphology_disk(params["transition_thickness_pixels"]); dilated_outer = binary_dilation(temp_mask_outer, footprint=se_transition); transition = dilated_outer & ~temp_mask_outer
        se_wall = morphology_disk(params["wall_thickness_pixels"]); lumen_shaft = binary_erosion(temp_mask_outer, footprint=se_wall)
        se_lumen = morphology_disk(params["lumen_thickness_pixels"]); shaft = binary_erosion(lumen_shaft, footprint=se_lumen)
        wall = temp_mask_outer & ~lumen_shaft; lumen = lumen_shaft & ~shaft

        if np.any(masks["wall"] & wall): continue

        masks["wall"] |= wall; masks["lumen"] |= lumen; masks["shaft"] |= shaft; masks["transition"] |= transition
        placed_follicles.append({'path': np.vstack([path_x, path_y]).T, 'angle': angle, 'is_anagen': is_anagen, 'width_profile': width_profile, 'width': width})
            
    return masks, placed_follicles

def generate_varied_gt(original_gt_contours, image_shape, config_params: RegionParams):
    H, W = image_shape
    try: initial_masks = skindb_generate_gt_masks(original_gt_contours, image_shape)
    except: initial_masks = None
    if initial_masks is None or not initial_masks.get('Epidermis', np.array([])).any():
        surface_line_y_orig = np.full(W, H // 5, dtype=int); dej_line_y_orig = np.full(W, H // 4, dtype=int)
    else:
        surface_line_y_orig = _get_boundary_line(initial_masks['Epidermis'], 'upper'); dej_line_y_orig = _get_boundary_line(initial_masks['Epidermis'], 'lower')
    
    epi_params = config_params.EPIDERMIS_VARIATION; base_dej_wave = _generate_multi_frequency_noise(W, epi_params["rete_pegs_max_amplitude_pixels"], epi_params["rete_pegs_num_octaves"], epi_params["rete_pegs_base_frequency"]); dej_line_y_base = dej_line_y_orig + base_dej_wave; dej_line_y_varied = gaussian_filter(dej_line_y_base, sigma=3); surface_line_y_varied = gaussian_filter(surface_line_y_orig.astype(float), sigma=2); s1_params = config_params.STRATUM_CORNEUM_PARAMS; s1_thickness = s1_params["base_thickness_pixels"] + _generate_multi_frequency_noise(W, s1_params["thickness_variation_amplitude_pixels"], 3, s1_params["thickness_variation_frequency_factor"]); s1_bottom_line_y = np.clip(surface_line_y_varied + s1_thickness, 0, H - 1).astype(int); dej_line_y_varied = np.maximum(dej_line_y_varied, s1_bottom_line_y + 10).astype(int)
    mask_sc = _create_mask_from_lines(surface_line_y_varied - 1, s1_bottom_line_y, W, H); mask_ve = _create_mask_from_lines(s1_bottom_line_y, dej_line_y_varied, W, H)
    
    follicle_masks, follicles = _generate_follicles(dej_line_y_varied, H, W, config_params)
    all_follicle_mask = follicle_masks["wall"] | follicle_masks["lumen"] | follicle_masks["shaft"] | follicle_masks["transition"]

    mask_glands = _generate_sebaceous_glands(follicles, np.ones((H,W), bool), H, W, config_params)
    occupied_space = all_follicle_mask | mask_glands

    pd_params = config_params.PAPILLARY_DERMIS_PARAMS; pd_thickness = pd_params["base_thickness_pixels"] + _generate_multi_frequency_noise(W, pd_params["thickness_variation_amplitude_pixels"], 3, pd_params["thickness_variation_frequency_factor"]); pd_bottom_line_y = np.clip(dej_line_y_varied + pd_thickness, 0, H-1).astype(int);
    mask_papillary_dermis = _create_mask_from_lines(dej_line_y_varied, pd_bottom_line_y, W, H) & ~occupied_space
    mask_reticular_dermis = _create_mask_from_lines(pd_bottom_line_y, np.full(W, H), W, H) & ~occupied_space
    
    final_masks = {
        "stratum_corneum": mask_sc, "viable_epidermis": mask_ve,
        "papillary_dermis": mask_papillary_dermis, "reticular_dermis": mask_reticular_dermis,
        "follicle_wall": follicle_masks["wall"], "hair_shaft": follicle_masks["shaft"],
        "follicle_lumen": follicle_masks["lumen"], "follicle_transition": follicle_masks["transition"],
        "sebaceous_gland": mask_glands
    }

    label_map = np.zeros((H, W), dtype=np.uint8)
    label_map[final_masks["reticular_dermis"]] = config_params.RETICULAR_DERMIS["id"]
    label_map[final_masks["papillary_dermis"]] = config_params.PAPILLARY_DERMIS["id"]
    label_map[final_masks["sebaceous_gland"]] = config_params.SEBACEOUS_GLAND["id"]
    label_map[final_masks["follicle_transition"]] = config_params.FOLLICLE_TRANSITION["id"]
    label_map[final_masks["follicle_wall"]] = config_params.FOLLICLE_WALL["id"]
    label_map[final_masks["follicle_lumen"]] = config_params.FOLLICLE_LUMEN["id"]
    label_map[final_masks["hair_shaft"]] = config_params.HAIR_SHAFT["id"]
    label_map[final_masks["viable_epidermis"]] = config_params.VIABLE_EPIDERMIS["id"]
    label_map[final_masks["stratum_corneum"]] = config_params.STRATUM_CORNEUM["id"]
    
    return final_masks, label_map