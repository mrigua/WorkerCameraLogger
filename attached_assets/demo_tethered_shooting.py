#!/usr/bin/env python3
# demo_tethered_shooting.py - Demonstrates tethered shooting capabilities

import sys
import os
import logging
import argparse
from typing import Dict, List, Optional, Any
import time
from datetime import datetime

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer

# Import tethered shooting components
try:
    from mock_tethered_shooting import MockTetheredShootingManager
    from tethered_ui import TetheredShootingPanel
    from logger_setup import setup_logging
    from format_organizer import FormatOrganizer, FormatPreference
except ImportError:
    # If we're in the main directory structure
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from mock_tethered_shooting import MockTetheredShootingManager
    from tethered_ui import TetheredShootingPanel
    from logger_setup import setup_logging
    from format_organizer import FormatOrganizer, FormatPreference

# Constants
CAPTURE_DIR = "captures"


class DemoTetheredWindow(QMainWindow):
    """Demo window for tethered shooting."""
    
    def __init__(self, mock_mode=True, auto_capture=False,
                 format_organize=False, format_preference="keep_all"):
        super().__init__()
        
        # Set up window properties
        self.setWindowTitle("Tethered Shooting Demo")
        self.setGeometry(100, 100, 1280, 800)
        
        # Set up format organizer
        self.format_organizer = FormatOrganizer(CAPTURE_DIR)
        if format_organize:
            self.format_organizer.set_organize_by_format(True)
            logging.info("Format organization enabled")
        
        # Set format preference
        pref_map = {
            'keep_all': FormatPreference.KEEP_ALL,
            'prefer_raw': FormatPreference.PREFER_RAW,
            'prefer_jpeg': FormatPreference.PREFER_JPEG
        }
        if format_preference in pref_map:
            self.format_organizer.set_format_preference(pref_map[format_preference])
            logging.info(f"Format preference set to: {format_preference}")
        
        # Set up tethering manager
        if mock_mode:
            self.tethering_manager = MockTetheredShootingManager(CAPTURE_DIR, self.format_organizer)
            logging.info("Using mock tethered shooting manager")
        else:
            # Use real tethering manager
            try:
                from tethered_shooting import TetheredShootingManager
            except ImportError:
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.abspath(__file__)))
                from tethered_shooting import TetheredShootingManager
            
            self.tethering_manager = TetheredShootingManager(CAPTURE_DIR, self.format_organizer)
            logging.info("Using real tethered shooting manager")
        
        # Create central widget
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create tethered shooting panel
        self.tethered_panel = TetheredShootingPanel(self.tethering_manager)
        layout.addWidget(self.tethered_panel)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Add mock cameras
        if mock_mode:
            self._add_mock_cameras()
            
            # Auto-start tethering
            QTimer.singleShot(1000, self._start_mock_tethering)
            
            # Auto-capture if requested
            if auto_capture:
                QTimer.singleShot(2000, self._start_auto_capture)
    
    def _add_mock_cameras(self):
        """Add mock cameras to the tethered panel."""
        mock_cameras = [
            ("usb:mock01", "Canon EOS 5D Mark IV"),
            ("usb:mock02", "Sony Alpha a7 III"),
            ("usb:mock03", "Nikon Z6 II")
        ]
        
        for port, model in mock_cameras:
            self.tethered_panel.add_camera(port, model)
            logging.info(f"Added mock camera to tethered panel: {model} at {port}")
    
    def _start_mock_tethering(self):
        """Auto-start tethering for mock cameras."""
        for port in ["usb:mock01", "usb:mock02", "usb:mock03"]:
            self.tethered_panel._on_start_tethering(port)
            logging.info(f"Auto-started tethering for camera at {port}")
    
    def _start_auto_capture(self):
        """Start auto-capture for the first mock camera."""
        port = "usb:mock01"
        if hasattr(self.tethering_manager, 'start_auto_capture'):
            self.tethering_manager.start_auto_capture(port, interval=3.0, count=5)
            logging.info(f"Started auto-capture for camera at {port}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop tethering for all cameras
        self.tethered_panel.stop_all_tethering()
        super().closeEvent(event)


def main():
    """Main function to run the demo."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Tethered Shooting Demo")
    parser.add_argument('--real', action='store_true', help='Use real cameras instead of mock cameras')
    parser.add_argument('--auto-capture', action='store_true', help='Automatically start capture in demo mode')
    parser.add_argument('--organize-by-format', action='store_true', help='Organize captures by format')
    parser.add_argument('--format-preference', choices=['keep_all', 'prefer_raw', 'prefer_jpeg'], 
                      default='keep_all', help='Format preference for captures')
    parser.add_argument('--offscreen', action='store_true', help='Run in offscreen mode (no visible UI)')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(log_level=logging.INFO)
    
    # Ensure capture directory exists
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    
    # Create date-based directories if organizing by format
    if args.organize_by_format:
        today = datetime.now().strftime("%Y-%m-%d")
        for format_dir in ["JPEG", "RAW", "TIFF"]:
            os.makedirs(os.path.join(CAPTURE_DIR, today, format_dir), exist_ok=True)
        logging.info(f"Created format directories in {CAPTURE_DIR}/{today}/")
    
    # Handle offscreen mode if requested
    if args.offscreen:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        logging.info("Running in offscreen mode")
    
    # Create and run application
    app = QApplication(sys.argv)
    
    window = DemoTetheredWindow(
        mock_mode=not args.real,
        auto_capture=args.auto_capture,
        format_organize=args.organize_by_format,
        format_preference=args.format_preference
    )
    
    if not args.offscreen:
        window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()