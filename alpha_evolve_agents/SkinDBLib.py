# # SkinDBLib.py

import os
import sys
import numpy as np
import cv2 # Используется для VideoWriter
import torch
import scipy.io
import scipy.ndimage as ndimage
from skimage.measure import label, regionprops
from skimage.morphology import binary_dilation, disk, remove_small_objects
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap
import networkx as nx
import time
import warnings
import traceback # Для детальной отладки ошибок
from collections import defaultdict
from scipy.cluster import hierarchy # Для дендрограммы
from scipy.spatial.distance import pdist # Для матрицы расстояний
from scipy.interpolate import interp1d # Для интерполяции границ
from matplotlib.gridspec import GridSpec # Для heatmap с дендрограммой и новой визуализации
import imageio # Для создания видео (используется в fig_to_rgb_array)
import pandas as pd # Для сохранения метрик в CSV
import io # Для работы с изображениями в памяти для видео

def load_skin_db(mat_file='skin_db.mat'):
    try:
        if not os.path.exists(mat_file):
             raise FileNotFoundError(f"MAT file not found in current directory: {mat_file}")
        data = scipy.io.loadmat(mat_file, squeeze_me=True, struct_as_record=False)
        skindb = data['skin_db']
        patients = {}
        for attr in dir(skindb):
            if attr.startswith('patient'):
                patients[attr] = getattr(skindb, attr)
        if not patients:
            print(f"Error: No patient data ('patient*') found in {mat_file}")
            return None
        return patients
    except FileNotFoundError as e: print(f"Error: {e}"); return None
    except Exception as e: print(f"Error loading MAT file '{mat_file}': {e}"); return None

def generate_gt_masks(gt_contours, shape):
    rows, cols = shape
    gt_masks = {'Noise': np.zeros(shape, dtype=bool), 'Epidermis': np.zeros(shape, dtype=bool),
                'Dermis': np.zeros(shape, dtype=bool), 'Tissue': np.zeros(shape, dtype=bool)}
    cols_indices = np.arange(cols)
    try:
        gt_line1 = gt_contours[0]; gt_line2 = gt_contours[1]
    except (IndexError, TypeError, AttributeError):
        if isinstance(gt_contours, (list, tuple, np.ndarray)) and len(gt_contours) > 0:
             gt_line1 = gt_contours[0]; gt_line2 = None
        elif hasattr(gt_contours, 'x') and hasattr(gt_contours, 'y'): # Single contour object
             gt_line1 = gt_contours; gt_line2 = None
        else: return gt_masks # No valid contours
    def interpolate_contour(contour):
        if contour is None or not hasattr(contour, 'x') or not hasattr(contour, 'y'): return None
        try:
            x_vals = np.array(contour.x).flatten(); y_vals = np.array(contour.y).flatten()
            if x_vals.size == 0 or y_vals.size == 0 or x_vals.size != y_vals.size: return None
            # Ensure x_vals are unique for interpolation after sorting
            order = np.argsort(x_vals)
            x_sorted, indices = np.unique(x_vals[order], return_index=True)
            y_sorted = y_vals[order][indices]

            if x_sorted.size < 2 : # Need at least two unique points to interpolate
                if x_sorted.size == 1: # Fill with constant value if only one point
                    return np.full(cols_indices.shape, y_sorted[0]-1, dtype=int)
                return None

            x_sorted_py = x_sorted - 1; y_sorted_py = y_sorted - 1 # MATLAB is 1-indexed
            interp_y = np.interp(cols_indices, x_sorted_py, y_sorted_py, left=y_sorted_py[0], right=y_sorted_py[-1])
            return interp_y.round().astype(int)
        except Exception as e:
            print(f"Warning: Interpolation failed for a contour: {e}")
            return None
    interp_y1 = interpolate_contour(gt_line1)
    interp_y2 = interpolate_contour(gt_line2)
    if interp_y1 is None: return gt_masks
    for col in range(cols):
        y1_val = np.clip(interp_y1[col], 0, rows - 1)
        gt_masks['Noise'][0 : y1_val + 1, col] = True
        if interp_y2 is not None:
            y2_val = np.clip(interp_y2[col], 0, rows - 1)
            # Ensure y1_val is truly above y2_val for Epidermis definition
            epi_start_y = y1_val + 1
            epi_end_y = y2_val + 1
            if epi_start_y < epi_end_y: # y1 is above y2
                gt_masks['Epidermis'][epi_start_y : epi_end_y, col] = True
                gt_masks['Dermis'][epi_end_y : rows, col] = True
            elif epi_start_y >= epi_end_y :
                 gt_masks['Dermis'][epi_start_y : rows, col] = True
        else: # Only one line provided (surface)
             gt_masks['Dermis'][y1_val + 1 : rows, col] = True # All tissue is Dermis
    # Refine masks to be mutually exclusive
    gt_masks['Epidermis'] = np.logical_and(gt_masks['Epidermis'], np.logical_not(gt_masks['Noise']))
    gt_masks['Dermis'] = np.logical_and(gt_masks['Dermis'], np.logical_not(gt_masks['Noise']))
    gt_masks['Dermis'] = np.logical_and(gt_masks['Dermis'], np.logical_not(gt_masks['Epidermis']))
    gt_masks['Tissue'] = np.logical_or(gt_masks['Epidermis'], gt_masks['Dermis'])
    return gt_masks

def calculate_dice_score(mask_pred, mask_gt):
    if not np.any(mask_gt) and not np.any(mask_pred): return 1.0 # Both empty, perfect match
    if not np.any(mask_gt) or not np.any(mask_pred): return 0.0 # One empty, other not, no overlap
    intersection = np.logical_and(mask_pred, mask_gt).sum()
    denominator = mask_pred.sum() + mask_gt.sum()
    return 2. * intersection / denominator if denominator > 0 else 0.0


