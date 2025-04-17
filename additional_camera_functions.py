# additional_camera_functions.py
import logging
import time
import os
from typing import Optional, Tuple, Dict
import subprocess

def capture_image(port: str, save_path: str, filename_prefix: str = "", status_signal=None, progress_signal=None) -> Tuple[bool, Optional[str], str]:
    """
    Captures an image from a camera and saves it to disk.
    
    Args:
        port: Camera port
        save_path: Directory to save the image
        filename_prefix: Optional prefix for the filename
        status_signal: Signal to emit status updates
        progress_signal: Signal to emit progress updates
        
    Returns:
        Tuple of (success, saved_file_path, error_message)
    """
    if status_signal:
        status_signal.emit(f"Capturing from camera on {port}...")
    
    if progress_signal:
        progress_signal.emit(10)  # Starting capture
    
    # Create timestamp for filename
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    port_safe = port.replace(':', '_').replace('/', '_')
    
    # Create save directory if it doesn't exist
    os.makedirs(save_path, exist_ok=True)
    
    # Create filename with prefix if provided
    if filename_prefix:
        filename = f"{filename_prefix}_{port_safe}_{timestamp}.jpg"
    else:
        filename = f"capture_{port_safe}_{timestamp}.jpg"
    
    full_path = os.path.join(save_path, filename)
    
    if progress_signal:
        progress_signal.emit(30)  # Before capture
    
    # Construct gphoto2 command: capture image and download it with the specified filename
    command = ["gphoto2", "--port", port, "--capture-image-and-download", "--filename", full_path]
    
    logging.info(f"Running capture command: {' '.join(command)}")
    try:
        if status_signal:
            status_signal.emit(f"Executing capture on {port}...")
        
        # Execute the command
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore',
            check=False,
            timeout=45  # Camera capture can take time
        )
        
        if progress_signal:
            progress_signal.emit(70)  # After capture
        
        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        
        # Check for success
        if process.returncode == 0 and os.path.exists(full_path):
            logging.info(f"Successfully captured and saved image to {full_path}")
            if status_signal:
                status_signal.emit(f"Successfully captured from {port}")
            if progress_signal:
                progress_signal.emit(100)  # Complete
            return True, full_path, ""
        else:
            error_msg = f"Capture failed. Return code: {process.returncode}. Error: {stderr}"
            logging.error(error_msg)
            if status_signal:
                status_signal.emit(f"Capture failed on {port}: {stderr}")
            if progress_signal:
                progress_signal.emit(100)  # Complete despite error
            return False, None, error_msg
    
    except subprocess.TimeoutExpired:
        error_msg = "Capture command timed out"
        logging.error(error_msg)
        if status_signal:
            status_signal.emit(f"Capture timed out on {port}")
        if progress_signal:
            progress_signal.emit(100)  # Complete despite error
        return False, None, error_msg
    
    except Exception as e:
        error_msg = f"Exception during capture: {str(e)}"
        logging.exception(error_msg)
        if status_signal:
            status_signal.emit(f"Error capturing from {port}: {str(e)}")
        if progress_signal:
            progress_signal.emit(100)  # Complete despite error
        return False, None, error_msg

def get_preview_image(port: str, status_signal=None) -> Tuple[bool, Optional[bytes], str]:
    """
    Gets a preview image from a camera.
    
    Args:
        port: Camera port
        status_signal: Signal to emit status updates
        
    Returns:
        Tuple of (success, image_data, error_message)
    """
    if status_signal:
        status_signal.emit(f"Getting preview from {port}...")
    
    # Create temporary file for preview
    import tempfile
    tmp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()
    
    try:
        # Construct gphoto2 command for preview capture
        command = ["gphoto2", "--port", port, "--capture-preview", "--filename", tmp_path]
        
        logging.debug(f"Running preview command: {' '.join(command)}")
        
        # Execute the command
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore',
            check=False,
            timeout=10  # Preview should be faster than full capture
        )
        
        # Check if the preview was captured successfully
        if process.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            # Read the captured preview image
            with open(tmp_path, 'rb') as f:
                image_data = f.read()
            
            # Clean up temporary file
            os.unlink(tmp_path)
            
            return True, image_data, ""
        else:
            stderr = process.stderr.strip()
            error_msg = f"Preview failed. Return code: {process.returncode}. Error: {stderr}"
            logging.error(error_msg)
            
            # Clean up temporary file if it exists
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
            return False, None, error_msg
    
    except subprocess.TimeoutExpired:
        error_msg = "Preview command timed out"
        logging.error(error_msg)
        
        # Clean up temporary file if it exists
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            
        return False, None, error_msg
    
    except Exception as e:
        error_msg = f"Exception during preview: {str(e)}"
        logging.exception(error_msg)
        
        # Clean up temporary file if it exists
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            
        return False, None, error_msg

def apply_camera_setting(port: str, setting_type: str, value: str, status_signal=None) -> Tuple[bool, str]:
    """
    Applies a specific setting to a camera.
    
    Args:
        port: Camera port
        setting_type: Setting type (iso, aperture, shutterspeed)
        value: Value to set
        status_signal: Signal to emit status updates
        
    Returns:
        Tuple of (success, error_message)
    """
    if status_signal:
        status_signal.emit(f"Applying {setting_type}={value} to camera on {port}...")
    
    # Convert generic setting names to gphoto2 config keys if needed
    setting_mappings = {
        "iso": ["iso", "iso speed", "iso sensitivity"],
        "aperture": ["aperture", "f-number", "fnumber"],
        "shutterspeed": ["shutterspeed", "shutter speed", "exptime"]
    }
    
    # First, try to get current config to find the exact setting name
    try:
        # List all config options to find the exact name
        list_cmd = ["gphoto2", "--port", port, "--list-config"]
        list_process = subprocess.run(
            list_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore',
            check=False,
            timeout=10
        )
        
        if list_process.returncode != 0:
            return False, f"Failed to list camera config: {list_process.stderr.strip()}"
        
        config_output = list_process.stdout.strip()
        found_setting = None
        
        # Find matching config setting
        for line in config_output.split('\n'):
            line = line.strip().lower()
            
            # Check if this line contains our setting type
            potential_matches = setting_mappings.get(setting_type.lower(), [setting_type.lower()])
            for match in potential_matches:
                if match in line:
                    found_setting = line
                    break
            
            if found_setting:
                break
        
        if not found_setting:
            return False, f"Could not find matching camera setting for {setting_type}"
        
        # Set the config value
        set_cmd = ["gphoto2", "--port", port, "--set-config", f"{found_setting}={value}"]
        set_process = subprocess.run(
            set_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors='ignore',
            check=False,
            timeout=10
        )
        
        if set_process.returncode == 0:
            logging.info(f"Successfully set {setting_type} to {value} on camera {port}")
            if status_signal:
                status_signal.emit(f"Successfully set {setting_type}={value} on {port}")
            return True, ""
        else:
            error_msg = f"Failed to set {setting_type} to {value}: {set_process.stderr.strip()}"
            logging.error(error_msg)
            return False, error_msg
    
    except subprocess.TimeoutExpired:
        return False, f"Command timed out while setting {setting_type}={value}"
    
    except Exception as e:
        error_msg = f"Exception while setting {setting_type}={value}: {str(e)}"
        logging.exception(error_msg)
        return False, error_msg

def create_placeholder_image() -> bool:
    """
    Creates a simple placeholder image for camera previews.
    
    Returns:
        Boolean indicating success
    """
    try:
        # Check if placeholder already exists
        if os.path.exists("placeholder.png"):
            return True
            
        # Use PIL to create a simple placeholder
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a dark gray image
            img = Image.new('RGB', (320, 240), color=(60, 60, 60))
            draw = ImageDraw.Draw(img)
            
            # Draw text
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
                
            draw.text((160, 100), "No Preview", fill=(200, 200, 200), font=font, anchor="mm")
            draw.text((160, 140), "Available", fill=(200, 200, 200), font=font, anchor="mm")
            
            # Save the image
            img.save("placeholder.png")
            logging.info("Created placeholder image")
            return True
            
        except ImportError:
            # If PIL is not available, create a file with SVG content
            with open("placeholder.png", "w") as f:
                f.write("""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
                <svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240">
                  <rect width="320" height="240" fill="#3c3c3c"/>
                  <text x="160" y="120" font-family="Arial" font-size="20" text-anchor="middle" fill="#c8c8c8">No Preview</text>
                  <text x="160" y="150" font-family="Arial" font-size="20" text-anchor="middle" fill="#c8c8c8">Available</text>
                </svg>""")
            logging.info("Created placeholder SVG")
            return True
            
    except Exception as e:
        logging.error(f"Failed to create placeholder image: {e}")
        return False
