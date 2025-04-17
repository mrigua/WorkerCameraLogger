#!/usr/bin/env python3
# mock_tethered_shooting.py - Mock implementation of tethered shooting for testing

import os
import time
import logging
import threading
import random
import queue
import shutil
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

try:
    from tethered_shooting import TetheredShootingManager, TetheredEvent
    from format_organizer import FormatOrganizer, FormatPreference
except ImportError:
    from attached_assets.tethered_shooting import TetheredShootingManager, TetheredEvent
    from attached_assets.format_organizer import FormatOrganizer, FormatPreference


class MockTetheredShootingManager(TetheredShootingManager):
    """Mock implementation of TetheredShootingManager for testing without real cameras."""
    
    def __init__(self, base_save_dir: str = "captures", 
                 format_organizer: Optional[FormatOrganizer] = None):
        super().__init__(base_save_dir, format_organizer)
        
        # Additional mock-specific state
        self._auto_capture_threads: Dict[str, threading.Thread] = {}
        self._auto_capture_events: Dict[str, threading.Event] = {}
        self._mock_file_queue: Dict[str, queue.Queue] = {}
        
        # Mock file generation settings
        self._image_sizes = {
            "small": (800, 600),
            "medium": (1600, 1200),
            "large": (3200, 2400)
        }
        self._formats = ["jpg", "raw", "tif"]
        self._next_file_index: Dict[str, int] = {}
        
    def start_tethering(self, camera_port: str) -> bool:
        """Start mock tethered shooting for a camera."""
        if camera_port in self._monitoring_threads and self._monitoring_threads[camera_port].is_alive():
            logging.warning(f"Mock tethering already active for camera {camera_port}")
            return False
        
        logging.info(f"Starting mock tethered shooting for camera {camera_port}")
        
        # Set up stop event
        stop_event = threading.Event()
        self._stop_events[camera_port] = stop_event
        
        # Set up file queue
        file_queue = queue.Queue()
        self._camera_file_queues[camera_port] = file_queue
        
        # Initialize mock file list
        self._known_camera_files[camera_port] = []
        self._next_file_index[camera_port] = 1
        
        # Create a queue for mock file generation
        mock_file_queue = queue.Queue()
        self._mock_file_queue[camera_port] = mock_file_queue
        
        # Start mock monitoring thread
        monitor_thread = threading.Thread(
            target=self._mock_monitor_camera,
            args=(camera_port, stop_event, file_queue, mock_file_queue),
            daemon=True,
            name=f"mock-tether-monitor-{camera_port}"
        )
        self._monitoring_threads[camera_port] = monitor_thread
        monitor_thread.start()
        
        # Start downloader thread
        downloader_thread = threading.Thread(
            target=self._process_download_queue,
            args=(camera_port, stop_event, file_queue),
            daemon=True,
            name=f"mock-tether-downloader-{camera_port}"
        )
        self._downloader_threads[camera_port] = downloader_thread
        downloader_thread.start()
        
        # Emit ready event
        self._emit_event(TetheredEvent.EventType.CAMERA_READY, camera_port)
        
        return True
    
    def stop_tethering(self, camera_port: str) -> bool:
        """Stop mock tethered shooting for a camera."""
        # Stop auto-capture if running
        self.stop_auto_capture(camera_port)
        
        # Stop the base tethering
        return super().stop_tethering(camera_port)
    
    def start_auto_capture(self, camera_port: str, interval: float = 5.0, 
                           count: Optional[int] = None) -> bool:
        """Start automatic mock captures at a specified interval."""
        if camera_port not in self._monitoring_threads or not self._monitoring_threads[camera_port].is_alive():
            logging.warning(f"Cannot start auto-capture - tethering not active for camera {camera_port}")
            return False
        
        if camera_port in self._auto_capture_threads and self._auto_capture_threads[camera_port].is_alive():
            logging.warning(f"Auto-capture already running for camera {camera_port}")
            return False
        
        logging.info(f"Starting auto-capture for camera {camera_port} with interval {interval}s")
        
        # Set up stop event
        stop_event = threading.Event()
        self._auto_capture_events[camera_port] = stop_event
        
        # Start auto-capture thread
        thread = threading.Thread(
            target=self._auto_capture_thread,
            args=(camera_port, interval, count, stop_event),
            daemon=True,
            name=f"auto-capture-{camera_port}"
        )
        self._auto_capture_threads[camera_port] = thread
        thread.start()
        
        return True
    
    def stop_auto_capture(self, camera_port: str) -> bool:
        """Stop automatic mock captures."""
        if camera_port not in self._auto_capture_threads:
            return False
        
        logging.info(f"Stopping auto-capture for camera {camera_port}")
        
        # Signal thread to stop
        if camera_port in self._auto_capture_events:
            self._auto_capture_events[camera_port].set()
        
        # Wait for thread to end (with timeout)
        if camera_port in self._auto_capture_threads:
            self._auto_capture_threads[camera_port].join(timeout=3.0)
        
        # Clean up
        if camera_port in self._auto_capture_threads:
            del self._auto_capture_threads[camera_port]
        if camera_port in self._auto_capture_events:
            del self._auto_capture_events[camera_port]
        
        return True
    
    def capture_mock_image(self, camera_port: str, format_extension: Optional[str] = None) -> bool:
        """Generate a mock capture and add it to the camera's file list."""
        if camera_port not in self._mock_file_queue:
            logging.warning(f"Cannot capture mock image - tethering not active for camera {camera_port}")
            return False
        
        # If no format specified, choose a random one
        if format_extension is None:
            format_extension = random.choice(self._formats)
        
        # Queue the mock file for generation
        self._mock_file_queue[camera_port].put(format_extension)
        return True
    
    def _mock_monitor_camera(self, camera_port: str, stop_event: threading.Event, 
                          file_queue: queue.Queue, mock_file_queue: queue.Queue) -> None:
        """Mock thread that simulates monitoring camera for new files."""
        logging.info(f"Started mock file monitoring for camera {camera_port}")
        
        check_interval = 0.5  # seconds
        
        while not stop_event.is_set():
            try:
                # Check for mock file generation requests
                try:
                    format_extension = mock_file_queue.get(block=False)
                    
                    # Generate the mock file path
                    file_path = self._generate_mock_file_path(camera_port, format_extension)
                    
                    # Add it to the known files list
                    if camera_port not in self._known_camera_files:
                        self._known_camera_files[camera_port] = []
                    
                    self._known_camera_files[camera_port].append(file_path)
                    
                    # Queue it for download
                    file_queue.put(file_path)
                    
                    # Emit file added event
                    self._emit_event(
                        TetheredEvent.EventType.FILE_ADDED,
                        camera_port,
                        {"file_path": file_path}
                    )
                    
                    # Mark task as done
                    mock_file_queue.task_done()
                    
                except queue.Empty:
                    # No mock files to generate
                    pass
            
            except Exception as e:
                logging.error(f"Error in mock camera monitor for {camera_port}: {e}")
                self._emit_event(
                    TetheredEvent.EventType.ERROR,
                    camera_port,
                    {"error": str(e)}
                )
            
            # Wait for the next check interval or until stopped
            stop_event.wait(timeout=check_interval)
        
        logging.info(f"Stopped mock file monitoring for camera {camera_port}")
    
    def _auto_capture_thread(self, camera_port: str, interval: float, 
                         count: Optional[int], stop_event: threading.Event) -> None:
        """Thread that automatically generates mock captures at intervals."""
        logging.info(f"Started auto-capture for camera {camera_port}")
        
        captures_done = 0
        
        while not stop_event.is_set():
            # Generate a mock capture
            self.capture_mock_image(camera_port)
            captures_done += 1
            
            # Check if we've reached the requested count
            if count is not None and captures_done >= count:
                logging.info(f"Auto-capture for camera {camera_port} completed {count} captures")
                break
            
            # Wait for the next interval or until stopped
            stop_event.wait(timeout=interval)
        
        logging.info(f"Stopped auto-capture for camera {camera_port}")
    
    def _generate_mock_file_path(self, camera_port: str, format_extension: str) -> str:
        """Generate a mock file path for the given camera port and format."""
        # Get the next file index
        index = self._next_file_index.get(camera_port, 1)
        self._next_file_index[camera_port] = index + 1
        
        # Determine folder structure and filename
        camera_id = camera_port.replace(':', '_').replace(',', '_')
        folder = f"/store_00010001/DCIM/100{camera_id[-4:]}/"
        file_base = f"IMG_{index:04d}"
        file_path = f"{folder}{file_base}.{format_extension}"
        
        return file_path
    
    def _download_file(self, camera_port: str, file_path: str) -> Tuple[bool, str]:
        """Override to generate mock image files."""
        # Generate save path
        today = datetime.now().strftime("%Y-%m-%d")
        subdirectory = os.path.join(self.base_save_dir, today)
        os.makedirs(subdirectory, exist_ok=True)
        
        # Extract extension from the file path
        filename = os.path.basename(file_path)
        base_name, extension = os.path.splitext(filename)
        if not extension and '.' in base_name:
            parts = base_name.split('.')
            base_name = '.'.join(parts[:-1])
            extension = '.' + parts[-1]
        
        # Add timestamp to prevent overwriting
        timestamp = datetime.now().strftime("%H%M%S")
        unique_filename = f"{base_name}_{timestamp}{extension}"
        
        # Use format organizer if format information is available
        format_value = self._detect_format_from_extension(extension)
        if format_value and hasattr(self.format_organizer, 'get_save_path'):
            # Get path from format organizer
            save_dir = self.format_organizer.get_save_path(format_value)
            os.makedirs(save_dir, exist_ok=True)
        else:
            # Use default directory
            save_dir = subdirectory
        
        save_path = os.path.join(save_dir, unique_filename)
        
        # Generate a mock image file
        success = self._generate_mock_image(camera_port, save_path, format_value)
        
        if not success:
            logging.error(f"Failed to generate mock image for {file_path}")
            return False, ""
        
        # Simulate a short download delay
        time.sleep(0.5)
        
        logging.info(f"Generated mock image at {save_path}")
        return True, save_path
    
    def _generate_mock_image(self, camera_port: str, save_path: str, 
                          format_value: Optional[str] = None) -> bool:
        """Generate a mock image file with camera and timestamp info."""
        try:
            # Determine image size
            size_name = random.choice(list(self._image_sizes.keys()))
            size = self._image_sizes[size_name]
            
            # Create a new image
            image = Image.new('RGB', size, color=(random.randint(50, 200), 
                                                  random.randint(50, 200), 
                                                  random.randint(50, 200)))
            draw = ImageDraw.Draw(image)
            
            # Add text to the image
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            camera_name = camera_port.replace('usb:', '').replace(',', '-')
            
            # Title text
            title_text = f"Mock Tethered Capture"
            draw.text((size[0]/2 - 100, 50), title_text, fill=(255, 255, 255))
            
            # Camera and time info
            info_text = [
                f"Camera: {camera_name}",
                f"Time: {timestamp}",
                f"Size: {size[0]}x{size[1]}",
                f"Format: {format_value or 'Unknown'}"
            ]
            
            y_position = 100
            for text_line in info_text:
                draw.text((50, y_position), text_line, fill=(255, 255, 255))
                y_position += 30
            
            # Add some graphical elements
            # Center circle
            center_x, center_y = size[0] // 2, size[1] // 2
            radius = min(size[0], size[1]) // 4
            draw.ellipse((center_x - radius, center_y - radius, 
                          center_x + radius, center_y + radius), 
                         outline=(255, 255, 255), width=2)
            
            # Grid lines
            line_spacing = max(size[0], size[1]) // 8
            for i in range(0, size[0], line_spacing):
                draw.line([(i, 0), (i, size[1])], fill=(128, 128, 128), width=1)
            for i in range(0, size[1], line_spacing):
                draw.line([(0, i), (size[0], i)], fill=(128, 128, 128), width=1)
            
            # Get the correct file extension for saving
            # Extract extension from save_path
            _, ext = os.path.splitext(save_path)
            
            # For RAW or non-standard extensions, save as JPEG but keep the original filename
            if ext.lower() in ['.raw', '.nef', '.cr2', '.arw', '.orf', '.rw2', '.pef', '.dng', '']:
                # Keep the original filename but ensure .jpg extension is used for the actual file
                save_dir = os.path.dirname(save_path)
                base_name = os.path.basename(save_path)
                # Remove any existing extension
                base_name = os.path.splitext(base_name)[0]
                # Create a temporary path with .jpg extension for actual saving
                jpg_save_path = os.path.join(save_dir, f"{base_name}.jpg")
                
                # Save as JPEG
                image.save(jpg_save_path)
                
                # If the original path had a different extension, rename to original
                if jpg_save_path != save_path:
                    # Check if the directory exists
                    if not os.path.exists(os.path.dirname(save_path)):
                        os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    
                    # Copy the file to maintain the original extension
                    shutil.copy2(jpg_save_path, save_path)
                    # Remove the temporary .jpg file if we're not supposed to keep it
                    if ext.lower() != '.jpg' and os.path.exists(jpg_save_path) and jpg_save_path != save_path:
                        os.remove(jpg_save_path)
            else:
                # Standard image format - save directly
                image.save(save_path)
                
            return True
            
        except Exception as e:
            logging.error(f"Error generating mock image: {e}")
            return False


# Standalone testing code
if __name__ == "__main__":
    import sys
    import argparse
    
    logging.basicConfig(level=logging.DEBUG, 
                      format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
    
    parser = argparse.ArgumentParser(description="Test mock tethered shooting")
    parser.add_argument("--port", default="usb:mock01", help="Mock camera port")
    parser.add_argument("--save-dir", default="captures", help="Directory to save images")
    parser.add_argument("--count", type=int, default=5, help="Number of auto-captures to generate")
    parser.add_argument("--interval", type=float, default=3.0, help="Auto-capture interval in seconds")
    
    args = parser.parse_args()
    
    def handle_tethered_event(event):
        print(f"Event: {event.event_type.value} from {event.camera_port}")
        if event.data:
            print(f"  Data: {event.data}")
    
    # Create mock tethered shooting manager
    manager = MockTetheredShootingManager(args.save_dir)
    
    # Connect to event signal
    manager.tethered_event.connect(handle_tethered_event)
    
    try:
        # Start tethering
        if manager.start_tethering(args.port):
            print(f"Started mock tethering for camera {args.port}")
            
            # Start auto-capture
            if manager.start_auto_capture(args.port, args.interval, args.count):
                print(f"Started auto-capture with interval {args.interval}s for {args.count} images")
                
                # Wait for auto-capture to complete
                while args.port in manager._auto_capture_threads and manager._auto_capture_threads[args.port].is_alive():
                    time.sleep(1)
                
                print("Auto-capture completed")
            else:
                print("Failed to start auto-capture")
                
            # Wait for all downloads to complete
            if args.port in manager._camera_file_queues:
                manager._camera_file_queues[args.port].join()
            
            print("All downloads completed")
        else:
            print(f"Failed to start tethering for camera {args.port}")
    
    except KeyboardInterrupt:
        print("\nStopping mock tethered shooting...")
    finally:
        # Clean up
        manager.stop_all_tethering()
        print("Mock tethered shooting stopped.")