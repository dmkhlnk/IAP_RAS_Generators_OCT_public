#!/usr/bin/env python3
"""
Skin Database Library - Tissue properties and segmentation utilities
"""

import os
import numpy as np
import scipy.io
from typing import Dict, Optional


def load_skin_db(mat_file='skin_db.mat') -> Optional[Dict]:
    """Load skin database from MATLAB file."""
    try:
        if not os.path.exists(mat_file):
            raise FileNotFoundError(f"MAT file not found: {mat_file}")
        data = scipy.io.loadmat(mat_file, squeeze_me=True, struct_as_record=False)
        skindb = data['skin_db']
        patients = {}
        for attr in dir(skindb):
            if attr.startswith('patient'):
                patients[attr] = getattr(skindb, attr)
        if not patients:
            print(f"No patient data found in {mat_file}")
            return None
        return patients
    except Exception as e:
        print(f"Error loading MAT file: {e}")
        return None


def calculate_dice_score(mask_pred: np.ndarray, mask_gt: np.ndarray) -> float:
    """Calculate Dice score between predicted and ground truth masks."""
    if not np.any(mask_gt) and not np.any(mask_pred):
        return 1.0
    if not np.any(mask_gt) or not np.any(mask_pred):
        return 0.0
    intersection = np.logical_and(mask_pred, mask_gt).sum()
    denominator = mask_pred.sum() + mask_gt.sum()
    return 2.0 * intersection / denominator if denominator > 0 else 0.0
