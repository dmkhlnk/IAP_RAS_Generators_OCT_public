#!/usr/bin/env python3
"""
OCT Scan Validator - AI-powered analysis of synthetic vs real scans
"""

import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import sys


def create_horizontal_panel(items: list, output_path: Path) -> Path:
    """Create a horizontal panel combining multiple images."""
    images_to_close = []
    TARGET_SIZE = (1024, 1024)
    
    print(f"Normalizing all images to target size: {TARGET_SIZE}")
    
    normalized_images = []
    try:
        for item_path, item_type in items:
            img = Image.open(item_path).convert("RGB")
            images_to_close.append(img)
            normalized_img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
            normalized_images.append(normalized_img)
    except FileNotFoundError as e:
        print(f"ERROR: Could not open image file: {e}", file=sys.stderr)
        for img in images_to_close:
            img.close()
        return None
    
    target_height_display = 300
    display_size = (target_height_display, target_height_display)
    
    total_width = display_size[0] * len(normalized_images)
    panel = Image.new('RGB', (total_width, display_size[1]), 'white')
    draw = ImageDraw.Draw(panel)
    
    try:
        font = ImageFont.truetype("arial.ttf", size=24)
    except IOError:
        font = ImageFont.load_default()
    
    labels = "ABCDE"
    x_offset = 0
    for i, img in enumerate(normalized_images):
        display_img = img.resize(display_size, Image.Resampling.LANCZOS)
        panel.paste(display_img, (x_offset, 0))
        text_pos = (x_offset + 10, 10)
        label = labels[i]
        draw.text((text_pos[0]-1, text_pos[1]), label, font=font, fill="black")
        draw.text((text_pos[0]+1, text_pos[1]), label, font=font, fill="black")
        draw.text((text_pos[0], text_pos[1]-1), label, font=font, fill="black")
        draw.text((text_pos[0], text_pos[1]+1), label, font=font, fill="black")
        draw.text(text_pos, label, fill="yellow", font=font)
        x_offset += display_size[0]
    
    panel.save(output_path)
    
    for img in images_to_close:
        img.close()
    
    return output_path
