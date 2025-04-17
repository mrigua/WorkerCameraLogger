# format_organizer.py - Handle format-based file organization
import os
import logging
import time
import re
import shutil
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

class FormatPreference(Enum):
    """Format preference modes for image capture."""
    KEEP_ALL = "keep_all"  # Download all formats produced by the camera (default)
    PREFER_RAW = "prefer_raw"  # Prioritize RAW formats when available
    PREFER_JPEG = "prefer_jpeg"  # Prioritize JPEG formats when available

class FormatOrganizer:
    """
    Handles format-based file organization, including:
    - Organizing captures by format type
    - Implementing format preferences
    - Directory structure management
    """
    
    def __init__(self, base_capture_dir: str = "captures"):
        """
        Initialize the format organizer.
        
        Args:
            base_capture_dir: Base directory for all captures
        """
        self.base_capture_dir = base_capture_dir
        self.organize_by_format = False
        self.format_preference = FormatPreference.KEEP_ALL
        
        # Make sure base directory exists
        os.makedirs(self.base_capture_dir, exist_ok=True)
        
    def get_save_path(self, format_value: str) -> str:
        """
        Get the appropriate save path based on current organization settings.
        
        Args:
            format_value: The format of the image (e.g., "JPEG (Standard)", "RAW", etc.)
            
        Returns:
            Path where the file should be saved
        """
        # Get current date for folder structure
        current_date = time.strftime("%Y-%m-%d")
        date_dir = os.path.join(self.base_capture_dir, current_date)
        
        # Create date directory if it doesn't exist
        os.makedirs(date_dir, exist_ok=True)
        
        # If not organizing by format, just return the date directory
        if not self.organize_by_format:
            return date_dir
            
        # Determine format category
        format_dir = self._get_format_dir(format_value)
        
        # Create format directory under the date directory
        format_path = os.path.join(date_dir, format_dir)
        os.makedirs(format_path, exist_ok=True)
        
        return format_path
        
    def _get_format_dir(self, format_value: str) -> str:
        """
        Get the format directory name based on the format value.
        
        Args:
            format_value: The format of the image
            
        Returns:
            Directory name for the format
        """
        format_value = format_value.lower()
        
        # Determine the format category
        if "raw" in format_value:
            return "RAW"
        elif "jpeg" in format_value or "jpg" in format_value:
            return "JPEG"
        elif "tiff" in format_value:
            return "TIFF"
        else:
            return "OTHER"
            
    def should_download_format(self, format_value: str) -> bool:
        """
        Determine whether a file in the given format should be downloaded
        based on current format preferences.
        
        Args:
            format_value: The format of the image
            
        Returns:
            True if the file should be downloaded, False otherwise
        """
        # Default behavior is to download all formats
        if self.format_preference == FormatPreference.KEEP_ALL:
            return True
            
        # Handle format preferences
        format_value = format_value.lower()
        if self.format_preference == FormatPreference.PREFER_RAW:
            # If we prefer RAW, only download RAW formats
            return "raw" in format_value
        elif self.format_preference == FormatPreference.PREFER_JPEG:
            # If we prefer JPEG, only download JPEG formats
            return "jpeg" in format_value or "jpg" in format_value
            
        # Fallback - should never reach here
        return True
        
    def set_format_preference(self, preference: FormatPreference):
        """
        Set the format preference mode.
        
        Args:
            preference: Format preference mode
        """
        self.format_preference = preference
        logging.info(f"Format preference set to: {preference.value}")
        
    def set_organize_by_format(self, enabled: bool):
        """
        Enable or disable organizing captures by format.
        
        Args:
            enabled: Whether to organize by format
        """
        self.organize_by_format = enabled
        logging.info(f"Organize by format: {'enabled' if enabled else 'disabled'}")
        
    def get_format_info(self, filepath: str) -> Dict:
        """
        Get format information from a captured image file.
        
        Args:
            filepath: Path to the captured image file
            
        Returns:
            Dictionary with format information
        """
        # Extract file extension
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        
        format_info = {
            "success": True,
            "file": filepath,
            "format": "UNKNOWN",
            "format_name": "Unknown Format",
            "error": None
        }
        
        # Determine format based on extension
        if ext in [".arw", ".cr2", ".cr3", ".nef", ".raw"]:
            format_info["format"] = "RAW"
            # Set more specific format name based on extension
            if ext == ".arw":
                format_info["format_name"] = "Sony RAW (ARW)"
            elif ext == ".cr2" or ext == ".cr3":
                format_info["format_name"] = "Canon RAW (CR2/CR3)"
            elif ext == ".nef":
                format_info["format_name"] = "Nikon RAW (NEF)"
            else:
                format_info["format_name"] = "Generic RAW"
        elif ext in [".jpg", ".jpeg"]:
            format_info["format"] = "JPEG"
            format_info["format_name"] = "JPEG"
        elif ext in [".tif", ".tiff"]:
            format_info["format"] = "TIFF"
            format_info["format_name"] = "TIFF"
            
        return format_info