# mock_camera.py
import logging
import time
import os
import random
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass, field
from enum import Enum

from PIL import Image, ImageDraw, ImageFont
import io
import tempfile

# Import format organizer
from format_organizer import FormatOrganizer, FormatPreference

@dataclass
class MockCameraInfo:
    """Represents a mock camera for testing/demo without real hardware."""
    model: str
    port: str
    iso: str = "100"
    aperture: str = "f/5.6"
    shutter_speed: str = "1/125"
    format: str = "JPEG (Standard)"
    iso_choices: List[str] = field(default_factory=lambda: ["100", "200", "400", "800", "1600", "3200"])
    aperture_choices: List[str] = field(default_factory=lambda: ["f/1.8", "f/2.8", "f/4", "f/5.6", "f/8", "f/11", "f/16"])
    shutter_speed_choices: List[str] = field(default_factory=lambda: ["1/4000", "1/2000", "1/1000", "1/500", "1/250", "1/125", "1/60", "1/30", "1/15", "1/8"])
    format_choices: List[str] = field(default_factory=lambda: ["JPEG (Standard)", "JPEG Fine", "JPEG Extra Fine", "RAW", "RAW + JPEG", "TIFF"])
    
class MockCameraManager:
    """Manages mock cameras for testing when real cameras aren't available."""
    
    def __init__(self, num_cameras=3):
        """Initialize with a specified number of simulated cameras."""
        self.mock_cameras: Dict[str, MockCameraInfo] = {}
        self._create_mock_cameras(num_cameras)
        
        # Initialize format organizer
        self.format_organizer = None
        try:
            self.format_organizer = FormatOrganizer("captures")
            logging.info("Format organizer initialized")
        except Exception as e:
            logging.error(f"Failed to initialize format organizer: {e}")
            self.format_organizer = None
        
    def _create_mock_cameras(self, count: int):
        """Create mock cameras with unique attributes."""
        makes = ["Canon", "Nikon", "Sony", "Fujifilm", "Olympus"]
        models = ["5D", "Z6", "A7", "X-T4", "E-M1"]
        versions = ["Mark II", "Mark III", "Mark IV", "", "Pro"]
        
        for i in range(count):
            make = random.choice(makes)
            model = random.choice(models)
            version = random.choice(versions)
            model_name = f"{make} {model} {version}".strip()
            port = f"usb:mock{i+1:02d}"
            
            self.mock_cameras[port] = MockCameraInfo(
                model=model_name,
                port=port
            )
            logging.info(f"Created mock camera: {model_name} at {port}")
    
    def get_mock_cameras(self) -> Dict[str, MockCameraInfo]:
        """Return the currently available mock cameras."""
        return self.mock_cameras
        
    def capture_mock_image(self, port: str, save_path: str, filename_prefix: str = "", status_signal=None, progress_signal=None, format_value: Optional[str] = None) -> Tuple[bool, Optional[str], str]:
        """Simulate capturing an image from a mock camera."""
        if port not in self.mock_cameras:
            return False, None, "Camera not found"
            
        camera = self.mock_cameras[port]
        
        # Get the format to use (provided format, camera's format, or default)
        img_format = format_value if format_value else camera.format
        
        if status_signal:
            status_signal.emit(f"Capturing from mock camera on {port} in {img_format} format...")
        
        if progress_signal:
            progress_signal.emit(10)
            
        # Simulate a delay for realistic capture
        time.sleep(random.uniform(0.5, 1.5))
        
        # Check format preferences if format organizer is available
        if self.format_organizer:
            # Check if we should download this format based on preference
            if not self.format_organizer.should_download_format(img_format):
                if status_signal:
                    status_signal.emit(f"Skipping capture in {img_format} format based on format preferences")
                return False, None, f"Format {img_format} is filtered out by current preferences"
            
            # Get the appropriate save path based on format
            save_path = self.format_organizer.get_save_path(img_format)
            if status_signal:
                status_signal.emit(f"Using format-organized path: {save_path}")
        
        # Create timestamp for filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        port_safe = port.replace(':', '_').replace('/', '_')
        
        # Create save directory if it doesn't exist
        os.makedirs(save_path, exist_ok=True)
        
        # Determine file extension based on format
        extension = '.jpg'  # Default
        if "raw" in img_format.lower() and "jpeg" in img_format.lower():
            extension = '.arw'  # Sony RAW+JPEG format
        elif "raw" in img_format.lower():
            extension = '.arw'  # Sony RAW format
        elif "tiff" in img_format.lower():
            extension = '.tiff'
        
        # Create filename with prefix if provided
        if filename_prefix:
            filename = f"{filename_prefix}_{port_safe}_{timestamp}{extension}"
        else:
            filename = f"capture_{port_safe}_{timestamp}{extension}"
        
        full_path = os.path.join(save_path, filename)
        
        if progress_signal:
            progress_signal.emit(30)
            
        # Generate a simulated image
        try:
            self._generate_sample_image(
                full_path, 
                camera.model, 
                camera.iso, 
                camera.aperture, 
                camera.shutter_speed,
                img_format  # Pass the format to the image generator
            )
            
            if progress_signal:
                progress_signal.emit(100)
                
            if status_signal:
                status_signal.emit(f"Successfully captured from mock camera {camera.model}")
                
            return True, full_path, ""
        except Exception as e:
            error_msg = f"Error generating mock image: {str(e)}"
            logging.exception(error_msg)
            
            if status_signal:
                status_signal.emit(f"Failed to generate mock image: {str(e)}")
                
            return False, None, error_msg
    
    def get_preview_image(self, port: str, status_signal=None) -> Tuple[bool, Optional[bytes], str]:
        """Get a preview image from a mock camera."""
        if port not in self.mock_cameras:
            return False, None, "Camera not found"
            
        camera = self.mock_cameras[port]
        
        if status_signal:
            status_signal.emit(f"Getting preview from mock camera {camera.model}...")
            
        # Simulate a short delay
        time.sleep(random.uniform(0.2, 0.5))
        
        try:
            # Generate a preview image in memory
            image_data = self._generate_preview_image_data(
                camera.model,
                camera.iso,
                camera.aperture,
                camera.shutter_speed,
                camera.format  # Include the format
            )
            
            return True, image_data, ""
        except Exception as e:
            error_msg = f"Error generating preview: {str(e)}"
            logging.exception(error_msg)
            return False, None, error_msg
    
    def set_camera_setting(self, port: str, setting_type: str, value: str, status_signal=None) -> bool:
        """Set a specific setting on a mock camera."""
        if port not in self.mock_cameras:
            return False
            
        camera = self.mock_cameras[port]
        
        if status_signal:
            status_signal.emit(f"Setting {setting_type} to {value} on mock camera {camera.model}")
            
        # Simulate a short delay for setting change
        time.sleep(random.uniform(0.1, 0.3))
        
        try:
            # Update the camera setting
            if setting_type.lower() == "iso":
                if value in camera.iso_choices:
                    camera.iso = value
                    return True
            elif setting_type.lower() == "aperture":
                if value in camera.aperture_choices:
                    camera.aperture = value
                    return True
            elif setting_type.lower() in ["shutterspeed", "shutter_speed"]:
                if value in camera.shutter_speed_choices:
                    camera.shutter_speed = value
                    return True
            elif setting_type.lower() == "format":
                if value in camera.format_choices:
                    camera.format = value
                    logging.info(f"Set format to {value} for camera {camera.model}")
                    return True
                    
            # If we got here, setting wasn't valid
            return False
        except Exception as e:
            logging.exception(f"Error setting mock camera setting: {e}")
            return False
    
    def _generate_sample_image(self, filepath: str, model: str, iso: str, aperture: str, shutter_speed: str, format_value: Optional[str] = None):
        """Generate a sample image file with camera info overlay."""
        # Create a 1920x1080 image with random color
        r = random.randint(10, 245)
        g = random.randint(10, 245)
        b = random.randint(10, 245)
        
        img = Image.new('RGB', (1920, 1080), color=(r, g, b))
        draw = ImageDraw.Draw(img)
        
        # Try to get a font, fall back to default if necessary
        try:
            font = ImageFont.truetype("Arial", 36)
            small_font = ImageFont.truetype("Arial", 24)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Use default format if none provided
        if not format_value:
            format_value = "JPEG (Standard)"
            
        # Draw camera info
        draw.text((100, 100), f"Camera: {model}", fill=(255, 255, 255), font=font)
        draw.text((100, 150), f"ISO: {iso}", fill=(255, 255, 255), font=font)
        draw.text((100, 200), f"Aperture: {aperture}", fill=(255, 255, 255), font=font)
        draw.text((100, 250), f"Shutter Speed: {shutter_speed}", fill=(255, 255, 255), font=font)
        draw.text((100, 300), f"Format: {format_value}", fill=(255, 255, 255), font=font)
        
        # Draw current date/time
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        draw.text((100, 350), f"Captured: {timestamp}", fill=(255, 255, 255), font=font)
        
        # Draw "MOCK CAPTURE" indicator
        draw.text((img.width - 500, img.height - 100), "MOCK CAPTURE", fill=(255, 255, 0), font=font)
        
        # Add some random shapes to make each image unique
        for _ in range(20):
            x1 = random.randint(0, img.width)
            y1 = random.randint(0, img.height)
            x2 = random.randint(0, img.width)
            y2 = random.randint(0, img.height)
            shape_r = random.randint(50, 255)
            shape_g = random.randint(50, 255)
            shape_b = random.randint(50, 255)
            draw.line((x1, y1, x2, y2), fill=(shape_r, shape_g, shape_b), width=5)
        
        # Save the image
        img.save(filepath)
        logging.info(f"Generated mock image at {filepath}")
        
    def set_format_preference(self, preference: FormatPreference) -> bool:
        """Set the format preference mode.
        
        Args:
            preference: Format preference mode
            
        Returns:
            True if successful, False otherwise
        """
        if self.format_organizer:
            try:
                self.format_organizer.set_format_preference(preference)
                logging.info(f"Format preference set to: {preference.value}")
                return True
            except Exception as e:
                logging.error(f"Error setting format preference: {e}")
                return False
        else:
            logging.warning("Format organizer not available, cannot set format preference")
            return False
            
    def set_organize_by_format(self, enabled: bool) -> bool:
        """Enable or disable organizing captures by format.
        
        Args:
            enabled: Whether to organize by format
            
        Returns:
            True if successful, False otherwise
        """
        if self.format_organizer:
            try:
                self.format_organizer.set_organize_by_format(enabled)
                logging.info(f"Organize by format: {'enabled' if enabled else 'disabled'}")
                return True
            except Exception as e:
                logging.error(f"Error setting organize by format: {e}")
                return False
        else:
            logging.warning("Format organizer not available, cannot set organize by format")
            return False
            
    def _generate_preview_image_data(self, model: str, iso: str, aperture: str, shutter_speed: str, format_value: Optional[str] = None) -> bytes:
        """Generate a preview image and return as bytes."""
        # Create a smaller preview image
        r = random.randint(10, 245)
        g = random.randint(10, 245)
        b = random.randint(10, 245)
        
        img = Image.new('RGB', (640, 480), color=(r, g, b))
        draw = ImageDraw.Draw(img)
        
        # Try to get a font, fall back to default if necessary
        try:
            font = ImageFont.truetype("Arial", 20)
            small_font = ImageFont.truetype("Arial", 14)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Use default format if none provided
        if not format_value:
            format_value = "JPEG (Standard)"
            
        # Draw camera info
        draw.text((50, 50), f"Camera: {model}", fill=(255, 255, 255), font=font)
        draw.text((50, 80), f"ISO: {iso}", fill=(255, 255, 255), font=small_font)
        draw.text((50, 110), f"Aperture: {aperture}", fill=(255, 255, 255), font=small_font)
        draw.text((50, 140), f"Shutter: {shutter_speed}", fill=(255, 255, 255), font=small_font)
        draw.text((50, 170), f"Format: {format_value}", fill=(255, 255, 255), font=small_font)
        
        # Draw "PREVIEW" indicator
        draw.text((img.width - 200, img.height - 50), "LIVE PREVIEW", fill=(255, 255, 0), font=font)
        
        # Add a timestamp to make the preview change
        timestamp = time.strftime("%H:%M:%S")
        draw.text((50, img.height - 50), timestamp, fill=(255, 255, 255), font=small_font)
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        return buffer.getvalue()