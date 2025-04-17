# profile_capture.py
import os
import logging
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from camera_profiles import CameraProfile, profile_manager
from format_organizer import FormatPreference

class ProfileCaptureManager:
    """
    Manages the process of applying a profile to cameras and capturing images.
    This class provides functionality to:
    1. Load a profile onto selected cameras
    2. Trigger captures with those settings
    3. Organize the resulting images by format
    """
    
    def __init__(self, camera_manager, format_organizer=None):
        """Initialize the profile capture manager.
        
        Args:
            camera_manager: Reference to the camera manager instance
            format_organizer: Optional reference to a format organizer instance
        """
        self.camera_manager = camera_manager
        self.format_organizer = format_organizer
        
    def apply_profile_to_cameras(self, profile_name: str, camera_ports: List[str], 
                                status_signal=None) -> Dict[str, bool]:
        """Apply a profile to multiple cameras.
        
        Args:
            profile_name: Name of the profile to apply
            camera_ports: List of camera ports to apply the profile to
            status_signal: Optional signal for status updates
            
        Returns:
            Dictionary mapping camera ports to success status
        """
        results = {}
        
        # Get the profile
        profile = profile_manager.get_profile(profile_name)
        if not profile:
            logging.error(f"Profile '{profile_name}' not found")
            if status_signal:
                status_signal.emit(f"Profile '{profile_name}' not found")
            return {port: False for port in camera_ports}
        
        logging.info(f"Applying profile '{profile_name}' to {len(camera_ports)} cameras")
        if status_signal:
            status_signal.emit(f"Applying profile '{profile_name}' to {len(camera_ports)} cameras")
        
        # Apply settings from the profile to each camera
        for port in camera_ports:
            success = True
            
            # Apply ISO if specified in profile
            if profile.settings.iso:
                iso_success = self.camera_manager.set_camera_setting(
                    port, "iso", profile.settings.iso, status_signal)
                success = success and iso_success
            
            # Apply aperture if specified in profile
            if profile.settings.aperture:
                aperture_success = self.camera_manager.set_camera_setting(
                    port, "aperture", profile.settings.aperture, status_signal)
                success = success and aperture_success
            
            # Apply shutter speed if specified in profile
            if profile.settings.shutter_speed:
                shutter_success = self.camera_manager.set_camera_setting(
                    port, "shutterspeed", profile.settings.shutter_speed, status_signal)
                success = success and shutter_success
            
            results[port] = success
            
            if status_signal:
                if success:
                    status_signal.emit(f"Applied profile to {port}")
                else:
                    status_signal.emit(f"Failed to apply profile to {port}")
        
        return results
    
    def capture_with_profile(self, profile_name: str, camera_ports: List[str],
                            save_dir: str = None, prefix: str = "",
                            status_signal=None, progress_signal=None) -> Dict[str, Tuple[bool, Optional[str]]]:
        """Apply a profile to cameras and then capture images.
        
        Args:
            profile_name: Name of the profile to apply
            camera_ports: List of camera ports to use
            save_dir: Directory to save images (default: uses format organizer or 'captures')
            prefix: Optional filename prefix
            status_signal: Optional signal for status updates
            progress_signal: Optional signal for progress updates
            
        Returns:
            Dictionary mapping camera ports to tuples of (success, filepath)
        """
        # Apply the profile first
        profile_results = self.apply_profile_to_cameras(profile_name, camera_ports, status_signal)
        
        # Filter to only cameras that successfully applied the profile
        successful_ports = [port for port, success in profile_results.items() if success]
        
        if not successful_ports:
            logging.error("No cameras successfully applied the profile")
            if status_signal:
                status_signal.emit("No cameras successfully applied the profile")
            return {port: (False, None) for port in camera_ports}
        
        # Determine save directory
        if save_dir is None:
            if self.format_organizer:
                # Use format organizer's current save path
                # Note: format is determined individually for each camera
                save_dir = "captures"  # This will be overridden per camera based on format
            else:
                # Default to captures directory with date
                today = datetime.now().strftime("%Y-%m-%d")
                save_dir = os.path.join("captures", today)
                os.makedirs(save_dir, exist_ok=True)
        else:
            # Make sure the directory exists
            os.makedirs(save_dir, exist_ok=True)
        
        # Capture from each camera
        results = {}
        for port in camera_ports:
            # Skip cameras that failed to apply the profile
            if port not in successful_ports:
                results[port] = (False, None)
                continue
                
            # Determine the specific save directory for this camera (may vary by format)
            camera_save_dir = save_dir
            
            # Add a brief delay to prevent camera conflicts
            time.sleep(0.25)
            
            if status_signal:
                status_signal.emit(f"Capturing from {port}")
            
            # Calculate the capture prefix including profile name
            capture_prefix = f"{prefix}_profile-{profile_name.replace(' ', '_')}" if prefix else f"profile-{profile_name.replace(' ', '_')}"
            
            # Do the capture
            filepath = self.camera_manager.capture_image(
                port, camera_save_dir, capture_prefix, 
                status_signal, progress_signal
            )
            
            results[port] = (filepath is not None, filepath)
            
            if status_signal:
                if filepath:
                    status_signal.emit(f"Captured image from {port}: {os.path.basename(filepath)}")
                else:
                    status_signal.emit(f"Failed to capture from {port}")
        
        # Summarize the results
        success_count = sum(1 for success, _ in results.values() if success)
        if status_signal:
            status_signal.emit(f"Capture complete: {success_count}/{len(camera_ports)} successful")
        
        return results