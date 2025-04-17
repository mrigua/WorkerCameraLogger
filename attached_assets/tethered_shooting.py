#!/usr/bin/env python3
# tethered_shooting.py - Implements tethered shooting capabilities for the camera control app

import os
import time
import logging
import subprocess
import threading
import queue
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
from enum import Enum
import shutil

from PyQt6.QtCore import QObject, pyqtSignal

try:
    from format_organizer import FormatOrganizer, FormatPreference
except ImportError:
    from attached_assets.format_organizer import FormatOrganizer, FormatPreference


class TetheredEvent:
    """Represents an event that occurs during tethered shooting."""
    
    class EventType(Enum):
        FILE_ADDED = "file_added"      # New file detected on camera
        FILE_DOWNLOADED = "file_downloaded"  # File successfully downloaded to computer
        CAMERA_BUSY = "camera_busy"    # Camera is busy (during capture)
        CAMERA_READY = "camera_ready"  # Camera is ready for new actions
        ERROR = "error"                # Error occurred during tethering
    
    def __init__(self, event_type: EventType, camera_port: str, 
                 data: Optional[Dict[str, Any]] = None):
        self.event_type = event_type
        self.camera_port = camera_port
        self.data = data or {}
        self.timestamp = datetime.now()
    
    def __str__(self):
        return f"TetheredEvent({self.event_type.value}, {self.camera_port}, {self.data})"


class TetheredShootingManager(QObject):
    """Manages tethered shooting for multiple cameras."""
    
    # Signals for communication with the UI
    tethered_event = pyqtSignal(object)  # Emits TetheredEvent objects
    
    def __init__(self, base_save_dir: str = "captures", 
                 format_organizer: Optional[FormatOrganizer] = None):
        super().__init__()
        
        # Configuration
        self.base_save_dir = os.path.abspath(base_save_dir)
        self.format_organizer = format_organizer or FormatOrganizer(base_save_dir)
        
        # Create base directory if it doesn't exist
        os.makedirs(self.base_save_dir, exist_ok=True)
        
        # State tracking
        self._tethering_active = False
        self._monitoring_threads: Dict[str, threading.Thread] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._camera_file_queues: Dict[str, queue.Queue] = {}
        self._known_camera_files: Dict[str, List[str]] = {}
        
        # Track file processors
        self._downloader_threads: Dict[str, threading.Thread] = {}
        
        # Track camera busy state
        self._camera_busy: Dict[str, bool] = {}
        
    def start_tethering(self, camera_port: str) -> bool:
        """Start tethered shooting for a specific camera."""
        if camera_port in self._monitoring_threads and self._monitoring_threads[camera_port].is_alive():
            logging.warning(f"Tethering already active for camera {camera_port}")
            return False
        
        logging.info(f"Starting tethered shooting for camera {camera_port}")
        
        # Set up monitoring
        stop_event = threading.Event()
        self._stop_events[camera_port] = stop_event
        
        # Create file queue for this camera
        file_queue = queue.Queue()
        self._camera_file_queues[camera_port] = file_queue
        
        # Start monitoring thread for this camera
        monitor_thread = threading.Thread(
            target=self._monitor_camera_files,
            args=(camera_port, stop_event, file_queue),
            daemon=True,
            name=f"tether-monitor-{camera_port}"
        )
        self._monitoring_threads[camera_port] = monitor_thread
        monitor_thread.start()
        
        # Start downloader thread for this camera
        downloader_thread = threading.Thread(
            target=self._process_download_queue,
            args=(camera_port, stop_event, file_queue),
            daemon=True,
            name=f"tether-downloader-{camera_port}"
        )
        self._downloader_threads[camera_port] = downloader_thread
        downloader_thread.start()
        
        # Emit event
        self._emit_event(TetheredEvent.EventType.CAMERA_READY, camera_port)
        
        return True
    
    def stop_tethering(self, camera_port: str) -> bool:
        """Stop tethered shooting for a specific camera."""
        if camera_port not in self._monitoring_threads:
            logging.warning(f"Tethering not active for camera {camera_port}")
            return False
        
        logging.info(f"Stopping tethered shooting for camera {camera_port}")
        
        # Signal thread to stop
        if camera_port in self._stop_events:
            self._stop_events[camera_port].set()
        
        # Wait for thread to end (with timeout)
        if camera_port in self._monitoring_threads:
            self._monitoring_threads[camera_port].join(timeout=3.0)
        
        # Wait for downloader thread to end
        if camera_port in self._downloader_threads:
            self._downloader_threads[camera_port].join(timeout=3.0)
        
        # Clean up
        if camera_port in self._monitoring_threads:
            del self._monitoring_threads[camera_port]
        if camera_port in self._stop_events:
            del self._stop_events[camera_port]
        if camera_port in self._camera_file_queues:
            del self._camera_file_queues[camera_port]
        if camera_port in self._downloader_threads:
            del self._downloader_threads[camera_port]
        if camera_port in self._known_camera_files:
            del self._known_camera_files[camera_port]
        
        return True
    
    def stop_all_tethering(self) -> None:
        """Stop tethered shooting for all cameras."""
        ports = list(self._monitoring_threads.keys())
        for port in ports:
            self.stop_tethering(port)
    
    def is_tethering_active(self, camera_port: str) -> bool:
        """Check if tethered shooting is active for a specific camera."""
        return (camera_port in self._monitoring_threads and 
                self._monitoring_threads[camera_port].is_alive())
    
    def _run_gphoto_command(self, args: List[str], port: Optional[str] = None, timeout: int = 45) -> Tuple[bool, str, str]:
        """Run a gphoto2 command and return success status, stdout, and stderr."""
        command = ["gphoto2"]
        
        # Add port if specified
        if port:
            command.extend(["--port", port])
        
        # Add the specified command arguments
        command.extend(args)
        
        logging.debug(f"Running gphoto command: {command}")
        
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            if not success:
                logging.error(f"gphoto2 command failed: {result.stderr}")
            
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            logging.error(f"gphoto2 command timed out: {command}")
            return False, "", "Command timed out"
        except Exception as e:
            logging.error(f"Error running gphoto2 command: {e}")
            return False, "", str(e)
    
    def _monitor_camera_files(self, camera_port: str, stop_event: threading.Event, file_queue: queue.Queue) -> None:
        """Monitor a camera for new files in a background thread."""
        logging.info(f"Started file monitoring for camera {camera_port}")
        
        # Initialize list of known files
        self._known_camera_files[camera_port] = []
        self._update_known_files(camera_port)
        
        check_interval = 1.0  # seconds
        
        while not stop_event.is_set():
            try:
                # Check for new files on the camera
                new_files = self._check_for_new_files(camera_port)
                
                # Queue any new files for download
                for file_path in new_files:
                    logging.info(f"New file detected on camera {camera_port}: {file_path}")
                    file_queue.put(file_path)
                    
                    # Emit event
                    self._emit_event(
                        TetheredEvent.EventType.FILE_ADDED, 
                        camera_port,
                        {"file_path": file_path}
                    )
            
            except Exception as e:
                logging.error(f"Error monitoring camera {camera_port}: {e}")
                self._emit_event(
                    TetheredEvent.EventType.ERROR,
                    camera_port,
                    {"error": str(e)}
                )
            
            # Wait for the next check interval or until stopped
            stop_event.wait(timeout=check_interval)
        
        logging.info(f"Stopped file monitoring for camera {camera_port}")
    
    def _process_download_queue(self, camera_port: str, stop_event: threading.Event, file_queue: queue.Queue) -> None:
        """Process the queue of files to download from a camera."""
        logging.info(f"Started download processor for camera {camera_port}")
        
        while not stop_event.is_set():
            try:
                # Get the next file path from the queue, with timeout
                # This allows the thread to check stop_event periodically
                try:
                    file_path = file_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Mark camera as busy during download
                self._camera_busy[camera_port] = True
                self._emit_event(TetheredEvent.EventType.CAMERA_BUSY, camera_port)
                
                # Download the file
                success, save_path = self._download_file(camera_port, file_path)
                
                # Mark task as done in the queue
                file_queue.task_done()
                
                # Mark camera as ready
                self._camera_busy[camera_port] = False
                self._emit_event(TetheredEvent.EventType.CAMERA_READY, camera_port)
                
                # Emit download event if successful
                if success:
                    self._emit_event(
                        TetheredEvent.EventType.FILE_DOWNLOADED,
                        camera_port,
                        {
                            "camera_file_path": file_path,
                            "local_file_path": save_path,
                            "file_name": os.path.basename(save_path)
                        }
                    )
            
            except Exception as e:
                logging.error(f"Error processing download queue for camera {camera_port}: {e}")
                self._camera_busy[camera_port] = False
                self._emit_event(
                    TetheredEvent.EventType.ERROR,
                    camera_port,
                    {"error": str(e)}
                )
        
        logging.info(f"Stopped download processor for camera {camera_port}")
    
    def _update_known_files(self, camera_port: str) -> None:
        """Update the list of known files on the camera."""
        success, stdout, stderr = self._run_gphoto_command(["--list-files"], camera_port)
        
        if not success:
            logging.error(f"Failed to list files on camera {camera_port}: {stderr}")
            return
        
        # Parse the output to get file paths
        files = []
        for line in stdout.split('\n'):
            if '#' in line and line.startswith(' '):
                # This line likely contains a file entry
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        # Extract the file path, formats vary by camera
                        file_path = None
                        for i, part in enumerate(parts):
                            if '/' in part and not part.startswith('-'):
                                file_path = part
                                break
                        
                        if file_path:
                            files.append(file_path)
                    except Exception as e:
                        logging.warning(f"Error parsing file path from line: {line}, {e}")
        
        self._known_camera_files[camera_port] = files
    
    def _check_for_new_files(self, camera_port: str) -> List[str]:
        """Check for new files on the camera and return a list of new file paths."""
        # Get the current list of known files
        old_files = self._known_camera_files.get(camera_port, [])
        
        # Update the list of files on the camera
        self._update_known_files(camera_port)
        
        # Get the updated list of files
        new_files = self._known_camera_files.get(camera_port, [])
        
        # Find files that weren't in the old list
        added_files = [f for f in new_files if f not in old_files]
        
        return added_files
    
    def _download_file(self, camera_port: str, file_path: str) -> Tuple[bool, str]:
        """Download a file from the camera and return success status and local path."""
        # Generate save path using format organizer if available
        today = datetime.now().strftime("%Y-%m-%d")
        subdirectory = os.path.join(self.base_save_dir, today)
        os.makedirs(subdirectory, exist_ok=True)
        
        # Generate a filename for the downloaded file
        filename = os.path.basename(file_path)
        # Add timestamp to prevent overwriting
        timestamp = datetime.now().strftime("%H%M%S")
        base_name, extension = os.path.splitext(filename)
        if not extension and '.' in base_name:
            # Handle cases where the extension might be part of the basename
            parts = base_name.split('.')
            base_name = '.'.join(parts[:-1])
            extension = '.' + parts[-1]
            
        filename = f"{base_name}_{timestamp}{extension}"
        
        # Use format organizer if format information is available
        format_value = self._detect_format_from_extension(extension)
        if format_value and hasattr(self.format_organizer, 'get_save_path'):
            # Get path from format organizer
            save_dir = self.format_organizer.get_save_path(format_value)
            os.makedirs(save_dir, exist_ok=True)
        else:
            # Use default directory
            save_dir = subdirectory
        
        save_path = os.path.join(save_dir, filename)
        
        # Download the file
        success, stdout, stderr = self._run_gphoto_command(
            ["--get-file", file_path, "--filename", save_path],
            camera_port
        )
        
        if not success:
            logging.error(f"Failed to download file {file_path} from camera {camera_port}: {stderr}")
            return False, ""
        
        logging.info(f"Downloaded file from camera {camera_port} to {save_path}")
        return True, save_path
    
    def _detect_format_from_extension(self, extension: str) -> Optional[str]:
        """Detect the format type from a file extension."""
        if not extension:
            return None
            
        # Normalize extension
        ext = extension.lower().lstrip('.')
        
        # Map common extensions to format values
        format_map = {
            'jpg': 'JPEG (Standard)',
            'jpeg': 'JPEG (Standard)',
            'jpe': 'JPEG (Standard)',
            'raw': 'RAW',
            'nef': 'RAW',  # Nikon
            'cr2': 'RAW',  # Canon
            'cr3': 'RAW',  # Canon (newer)
            'arw': 'RAW',  # Sony
            'orf': 'RAW',  # Olympus
            'rw2': 'RAW',  # Panasonic
            'pef': 'RAW',  # Pentax
            'dng': 'RAW',  # Adobe Digital Negative
            'tif': 'TIFF',
            'tiff': 'TIFF'
        }
        
        return format_map.get(ext)
    
    def _emit_event(self, event_type: TetheredEvent.EventType, camera_port: str, 
                    data: Optional[Dict[str, Any]] = None) -> None:
        """Create and emit a tethered event."""
        event = TetheredEvent(event_type, camera_port, data)
        logging.debug(f"Emitting tethered event: {event}")
        self.tethered_event.emit(event)


# Standalone testing code
if __name__ == "__main__":
    import sys
    import argparse
    
    logging.basicConfig(level=logging.DEBUG, 
                      format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
    
    parser = argparse.ArgumentParser(description="Test tethered shooting")
    parser.add_argument("--port", required=True, help="Camera port (e.g., usb:001,004)")
    parser.add_argument("--save-dir", default="captures", help="Directory to save images")
    
    args = parser.parse_args()
    
    def handle_tethered_event(event):
        print(f"Event: {event.event_type.value} from {event.camera_port}")
        if event.data:
            print(f"  Data: {event.data}")
    
    # Create tethered shooting manager
    manager = TetheredShootingManager(args.save_dir)
    
    # Connect to event signal
    manager.tethered_event.connect(handle_tethered_event)
    
    try:
        # Start tethering
        if manager.start_tethering(args.port):
            print(f"Started tethering for camera {args.port}")
            print("Take some pictures with your camera. Press Ctrl+C to stop.")
            
            # Just keep the script running
            while True:
                time.sleep(1)
        else:
            print(f"Failed to start tethering for camera {args.port}")
    
    except KeyboardInterrupt:
        print("\nStopping tethered shooting...")
    finally:
        # Clean up
        manager.stop_all_tethering()
        print("Tethered shooting stopped.")