# main_offscreen.py
import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication, QTimer
from gui import MainWindow, CAPTURE_DIR
from logger_setup import setup_logging
from mock_camera import MockCameraManager
import time

# Create a global reference to manager to prevent garbage collection
mock_manager = None

def patch_camera_manager(window):
    """Patch the camera_manager in MainWindow to use mock cameras."""
    global mock_manager
    
    # Create the MockCameraManager with 3 simulated cameras
    mock_manager = MockCameraManager(num_cameras=3)
    mock_cameras = mock_manager.get_mock_cameras()
    
    # Log what we're doing
    logging.info(f"Patching MainWindow with {len(mock_cameras)} mock cameras")
    
    # Return the mock_manager so it can be used for format organization
    return mock_manager
    
    # Override methods in window.camera_manager to use our mock implementation
    
    # 1. Override detect_cameras
    original_detect = window.camera_manager.detect_cameras
    
    def mock_detect_cameras(status_signal=None, progress_signal=None, **kwargs):
        """Simulated camera detection using mock cameras."""
        logging.info("Running mock camera detection")
        
        if status_signal:
            status_signal.emit("Detecting mock cameras...")
            
        if progress_signal:
            progress_signal.emit(30)
            
        # Wait to simulate real detection
        time.sleep(1)
        
        # Create CameraInfo objects from our mock cameras
        from camera_manager import CameraInfo, CameraSettings
        
        # Clear existing cameras if needed
        window.camera_manager.cameras = {}
        
        for port, mock_cam in mock_cameras.items():
            # Create a new CameraInfo object
            camera_info = CameraInfo(model=mock_cam.model, port=port, status="Connected")
            
            # Set up settings
            camera_info.settings.iso = mock_cam.iso
            camera_info.settings.aperture = mock_cam.aperture
            camera_info.settings.shutter_speed = mock_cam.shutter_speed
            
            # Set up choices
            camera_info.settings.iso_choices = mock_cam.iso_choices
            camera_info.settings.aperture_choices = mock_cam.aperture_choices
            camera_info.settings.shutter_speed_choices = mock_cam.shutter_speed_choices
            
            # Add to our cameras dictionary
            window.camera_manager.cameras[port] = camera_info
            
            # Log it
            logging.info(f"Added mock camera: {mock_cam.model} at {port}")
            
        if status_signal:
            status_signal.emit(f"Found {len(mock_cameras)} mock cameras")
            
        if progress_signal:
            progress_signal.emit(100)
            
        return window.camera_manager.cameras
    
    # Replace the method
    window.camera_manager.detect_cameras = mock_detect_cameras
    
    # 2. Override capture_image
    original_capture = window.camera_manager.capture_image
    
    def mock_capture_image(port, save_dir=".", prefix="", status_signal=None, progress_signal=None, **kwargs):
        """Simulated image capture using mock cameras."""
        logging.info(f"Running mock image capture for {port}")
        
        if port not in window.camera_manager.cameras:
            logging.error(f"Capture called for unknown port: {port}")
            return None
            
        cam_info = window.camera_manager.cameras[port]
        
        # Set status to capturing
        cam_info.status = "Capturing..."
        if status_signal:
            status_signal.emit(f"Capturing on {cam_info.model}...")
            
        # Use mock capture
        success, filepath, error = mock_manager.capture_mock_image(
            port=port,
            save_path=save_dir,
            filename_prefix=prefix,
            status_signal=status_signal,
            progress_signal=progress_signal
        )
        
        if success:
            cam_info.status = "Connected"
            cam_info.last_error = None
            if status_signal:
                status_signal.emit(f"Captured image from {cam_info.model}")
            return filepath
        else:
            cam_info.status = "Error"
            cam_info.last_error = f"Capture failed: {error}"
            if status_signal:
                status_signal.emit(f"Capture FAILED on {cam_info.model}: {error}")
            return None
    
    # Replace the method
    window.camera_manager.capture_image = mock_capture_image
    
    # 3. Override capture_preview
    original_preview = window.camera_manager.capture_preview
    
    def mock_capture_preview(port, status_signal=None, **kwargs):
        """Simulated preview capture using mock cameras."""
        if port not in window.camera_manager.cameras:
            return None
            
        cam_info = window.camera_manager.cameras[port]
        if cam_info.status not in ["Connected"]:
            logging.debug(f"Skipping preview for {port}, status is {cam_info.status}")
            return None
            
        success, image_data, _ = mock_manager.get_preview_image(
            port=port,
            status_signal=status_signal
        )
        
        return image_data if success else None
    
    # Replace the method
    window.camera_manager.capture_preview = mock_capture_preview
    
    # 4. Override set_camera_setting
    original_set_setting = window.camera_manager.set_camera_setting
    
    def mock_set_camera_setting(port, setting_type, value, status_signal=None, **kwargs):
        """Simulated camera setting using mock cameras."""
        if port not in window.camera_manager.cameras:
            logging.error(f"Cannot set setting for unknown port {port}")
            return False
            
        cam_info = window.camera_manager.cameras[port]
        
        logging.info(f"Setting {setting_type} to '{value}' on {port}")
        if status_signal:
            status_signal.emit(f"Setting {setting_type} to {value} on {cam_info.model}...")
            
        cam_info.status = "Applying Settings..."
        
        success = mock_manager.set_camera_setting(
            port=port,
            setting_type=setting_type,
            value=value,
            status_signal=status_signal
        )
        
        dataclass_attr_name = "shutter_speed" if setting_type == "shutterspeed" else setting_type
        
        if success:
            logging.info(f"Successfully set {setting_type} to {value} on {port}")
            setattr(cam_info.settings, dataclass_attr_name, value)
            cam_info.status = "Connected"
            cam_info.last_error = None
            if status_signal:
                status_signal.emit(f"{setting_type} set to {value} on {cam_info.model}")
            return True
        else:
            logging.error(f"Failed to set {setting_type} to {value} on {port}")
            cam_info.status = "Error"
            cam_info.last_error = f"Failed to set {setting_type}"
            if status_signal:
                status_signal.emit(f"Error setting {setting_type} on {cam_info.model}")
            return False
    
    # Replace the method
    window.camera_manager.set_camera_setting = mock_set_camera_setting
    
    logging.info("Mock camera patching complete!")

if __name__ == "__main__":
    # --- Setup Logging ---
    setup_logging(log_level=logging.DEBUG)

    # --- Ensure Capture Directory Exists ---
    capture_directory = CAPTURE_DIR
    try:
        abs_capture_dir = os.path.abspath(capture_directory)
        os.makedirs(abs_capture_dir, exist_ok=True)
        logging.info(f"Capture directory set to: {abs_capture_dir}")
    except Exception as e:
        logging.error(f"Could not create capture directory '{capture_directory}': {e}")

    # --- Create and Run Application ---
    # Force the offscreen platform for headless environments
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    # Set up QApplication with platform plugin
    app = QApplication(sys.argv)

    # Optional: Apply a style for better look & feel
    app.setStyle('Fusion')

    # Create the main window instance
    try:
        window = MainWindow()
        # Patch it with our mock camera implementation
        patch_camera_manager(window)
        
        # Simulate clicking the detect button after a short delay
        QTimer.singleShot(1000, lambda: window._on_detect_clicked())
        
        # Schedule "Capture All" operation to happen 5 seconds after startup
        # This gives time for the detection to complete first
        QTimer.singleShot(5000, lambda: window._on_capture_all_clicked())
        
        # Schedule turning on previews 2 seconds after startup
        QTimer.singleShot(3000, lambda: window.toggle_preview_button.setChecked(True))
        
        # In offscreen mode, we don't call show()
        # But we still need to create the window for the application logic to work
    except Exception as e:
        logging.exception("Unhandled exception during MainWindow initialization!")
        sys.exit(1)

    logging.info("Application started in offscreen mode with mock cameras.")
    # Start the Qt event loop
    sys.exit(app.exec())