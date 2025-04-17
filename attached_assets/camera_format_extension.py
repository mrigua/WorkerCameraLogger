# camera_format_extension.py - Format support for camera manager

from typing import Optional, Dict, List, Tuple
import os
import logging
import time

def apply_format_to_camera(port: str, format_value: str, camera_manager) -> bool:
    """
    Apply a format setting to a camera.
    
    Args:
        port: Camera port
        format_value: Format value to set (e.g., "JPEG (Standard)", "RAW", etc.)
        camera_manager: Reference to the camera manager instance
        
    Returns:
        Boolean indicating success
    """
    # First, update the camera's internal format setting
    if port in camera_manager.cameras:
        camera_manager.cameras[port].settings.format = format_value
        logging.info(f"Set image format for {port} to {format_value}")
        return True
    return False

def get_format_extension(format_value: str) -> str:
    """
    Get the file extension for a given format.
    
    Args:
        format_value: Format value (e.g., "JPEG (Standard)", "RAW", etc.)
        
    Returns:
        File extension (e.g., ".jpg", ".raw", etc.)
    """
    format_value = format_value.lower()
    if "raw" in format_value and "jpeg" in format_value:
        return ".arw"  # Sony RAW+JPEG format
    elif "raw" in format_value:
        return ".arw"  # Sony RAW format
    elif "tiff" in format_value:
        return ".tiff"
    elif "jpeg" in format_value or "jpg" in format_value:
        return ".jpg"
    else:
        return ".jpg"  # Default to JPEG

def format_capture_filename(base_filename: str, format_value: str) -> str:
    """
    Format a filename based on the selected format.
    
    Args:
        base_filename: Base filename (without extension)
        format_value: Format value
        
    Returns:
        Formatted filename with extension
    """
    # Strip any existing extension
    base_without_ext = os.path.splitext(base_filename)[0]
    
    # Add the appropriate extension based on format
    extension = get_format_extension(format_value)
    return f"{base_without_ext}{extension}"