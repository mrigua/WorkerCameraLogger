#!/usr/bin/env python3
# demo_profile_capture.py
import os
import sys
import logging
import argparse
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThreadPool

from camera_manager import CameraManager
from camera_profiles import profile_manager, CameraProfile, CameraProfileSettings
from profile_capture import ProfileCaptureManager
from mock_camera import MockCameraManager, MockCameraInfo
from format_organizer import FormatOrganizer, FormatPreference

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('profile_capture_demo.log')
    ]
)

def ensure_demo_profile():
    """Create a demo profile if it doesn't exist."""
    profile_name = "Demo Profile"
    
    # Check if profile already exists
    if profile_name in profile_manager.get_profile_names():
        logging.info(f"Using existing profile: {profile_name}")
        return profile_name
    
    # Create a new profile
    profile = CameraProfile(
        name=profile_name,
        description="Demo profile created for testing",
        settings=CameraProfileSettings(
            iso="800",
            aperture="f/2.8",
            shutter_speed="1/500"
        )
    )
    
    # Save the profile
    if profile_manager.save_profile(profile):
        logging.info(f"Created new profile: {profile_name}")
        return profile_name
    else:
        logging.error("Failed to create demo profile")
        return None

def main():
    parser = argparse.ArgumentParser(description="Demonstrate profile capture functionality")
    parser.add_argument("--organize-by-format", action="store_true", 
                      help="Organize captures by format type")
    parser.add_argument("--format-preference", choices=["keep_all", "prefer_raw", "prefer_jpeg"],
                      default="keep_all", help="Format preference for capture")
    args = parser.parse_args()
    
    # Initialize camera manager with mock cameras (for demo)
    camera_manager = CameraManager()
    mock_manager = MockCameraManager(num_cameras=3)
    mock_cameras = mock_manager.get_mock_cameras()
    
    # Set up a format organizer if requested
    format_organizer = FormatOrganizer()
    if args.organize_by_format:
        format_organizer.set_organize_by_format(True)
        logging.info("Format organization enabled")
    
    # Set format preference
    if args.format_preference == "prefer_raw":
        format_organizer.set_format_preference(FormatPreference.PREFER_RAW)
    elif args.format_preference == "prefer_jpeg":
        format_organizer.set_format_preference(FormatPreference.PREFER_JPEG)
    logging.info(f"Format preference set to: {args.format_preference}")
    
    # Create a base save directory with date
    today = datetime.now().strftime("%Y-%m-%d")
    save_dir = os.path.join("captures", today)
    os.makedirs(save_dir, exist_ok=True)
    
    # Make sure we have a profile to use
    profile_name = ensure_demo_profile()
    if not profile_name:
        sys.exit(1)
    
    # Get list of camera ports (from mock cameras for demo)
    camera_ports = list(mock_cameras.keys())
    logging.info(f"Found {len(camera_ports)} cameras: {camera_ports}")
    
    # Load the profile
    profile = profile_manager.get_profile(profile_name)
    if not profile:
        logging.error(f"Could not load profile: {profile_name}")
        sys.exit(1)

    # Create a custom direct approach using mock cameras since the CameraManager
    # version requires gphoto2 capabilities
    logging.info(f"Starting profile capture with profile '{profile_name}'")
    results = {}
    
    for port, mock_cam in mock_cameras.items():
        # Apply settings from profile to mock camera directly
        logging.info(f"Applying profile settings to {mock_cam.model} at {port}")
        
        # Update each setting if specified in the profile
        if profile.settings.iso:
            mock_cam.iso = profile.settings.iso
            logging.info(f"Set ISO to {profile.settings.iso}")
            
        if profile.settings.aperture:
            mock_cam.aperture = profile.settings.aperture
            logging.info(f"Set aperture to {profile.settings.aperture}")
            
        if profile.settings.shutter_speed:
            mock_cam.shutter_speed = profile.settings.shutter_speed
            logging.info(f"Set shutter speed to {profile.settings.shutter_speed}")
        
        # Do the capture with mock manager
        logging.info(f"Capturing image from {mock_cam.model}")
        success, filepath, error = mock_manager.capture_mock_image(
            port, 
            save_path=save_dir,
            filename_prefix=f"demo_profile-{profile_name.replace(' ', '_')}"
        )
        
        results[port] = (success, filepath)
    
    # Report results
    success_count = sum(1 for success, _ in results.values() if success)
    logging.info(f"Capture complete: {success_count}/{len(camera_ports)} successful")
    
    for port, (success, filepath) in results.items():
        if success and filepath:
            logging.info(f"Camera {port}: Captured {os.path.basename(filepath)}")
        else:
            logging.error(f"Camera {port}: Capture failed")
    
    # Summarize results
    print(f"\nProfile Capture Results:")
    print(f"  Profile: {profile_name}")
    print(f"  Cameras: {len(camera_ports)}")
    print(f"  Successful: {success_count}")
    print(f"  Save directory: {save_dir}")
    
    if success_count > 0:
        print("\nCapture files:")
        for port, (success, filepath) in results.items():
            if success:
                print(f"  - {os.path.basename(filepath)}")

if __name__ == "__main__":
    # Need a QApplication instance for signals to work
    # Set up for offscreen/headless mode
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)
    main()
    sys.exit(0)  # Exit without starting event loop