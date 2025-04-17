#!/usr/bin/env python3
# main_tethered.py - Entry point for camera control application with tethered shooting

import sys
import os
import logging
import argparse
from typing import Dict, List, Optional, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QLabel, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QAction, QIcon, QColor, QPalette

# Import from attached_assets directory
import importlib.util
import sys

# Check if running from attached_assets or parent directory
if __name__ == "__main__":
    # Adjust import style based on how script is being run
    if __file__.split('/')[-2] == "attached_assets":
        # Running from within attached_assets directory
        sys.path.append('..')  # Add parent directory to path
        
        # Local imports
        from main_enhanced import MinimalistMainWindow, MINIMALIST_PALETTE, MINIMALIST_STYLE
        from gui_updated import MainWindow as OriginalMainWindow, CAPTURE_DIR
        from tethered_ui import TetheredShootingPanel
        from mock_tethered_shooting import MockTetheredShootingManager
        from tethered_shooting import TetheredShootingManager
        from worker import Worker
        
        # Other imports
        from logger_setup import setup_logging
        from main_offscreen import patch_camera_manager
        from camera_reset import kill_competing_processes, reset_usb_device, reset_all_cameras
        from format_organizer import FormatPreference, FormatOrganizer
    else:
        # Running from parent directory
        from attached_assets.main_enhanced import MinimalistMainWindow, MINIMALIST_PALETTE, MINIMALIST_STYLE
        from attached_assets.gui_updated import MainWindow as OriginalMainWindow, CAPTURE_DIR
        from attached_assets.tethered_ui import TetheredShootingPanel
        from attached_assets.mock_tethered_shooting import MockTetheredShootingManager
        from attached_assets.tethered_shooting import TetheredShootingManager
        from attached_assets.worker import Worker
        
        # Other imports
        from attached_assets.logger_setup import setup_logging
        from attached_assets.main_offscreen import patch_camera_manager
        from attached_assets.camera_reset import kill_competing_processes, reset_usb_device, reset_all_cameras
        from attached_assets.format_organizer import FormatPreference, FormatOrganizer


class TetheredMainWindow(MinimalistMainWindow):
    """Extended version of the minimalist window with tethered shooting capabilities."""
    
    def __init__(self):
        super().__init__()
        
        # Set window title
        self.setWindowTitle("Multi-Camera Controller with Tethered Shooting")
        
        # Create a larger window for tethered view
        self.setGeometry(100, 100, 1280, 800)
        
        # Set up the UI with tabbed interface for tethered shooting
        self._setup_tabbed_ui()
    
    def _setup_tabbed_ui(self):
        """Set up the tabbed interface with standard and tethered views."""
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)  # Use a more minimal style
        
        # Add the original central widget as first tab
        self.standard_tab = self.centralWidget()
        self.tab_widget.addTab(self.standard_tab, "Standard Control")
        
        # Create tethered shooting tab
        self.tethered_tab = QWidget()
        tethered_layout = QVBoxLayout(self.tethered_tab)
        tethered_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create the tethered shooting panel
        if self.original_window._is_using_mock_cameras:
            # Use mock tethering for mock cameras
            self.tethering_manager = MockTetheredShootingManager(CAPTURE_DIR)
            logging.info("Using mock tethered shooting manager")
        else:
            # Use real tethering for real cameras
            self.tethering_manager = TetheredShootingManager(CAPTURE_DIR)
            logging.info("Using real tethered shooting manager")
        
        # Share format organizer if available
        if hasattr(self.original_window.camera_manager, 'format_organizer'):
            self.tethering_manager.format_organizer = self.original_window.camera_manager.format_organizer
        
        self.tethered_panel = TetheredShootingPanel(self.tethering_manager)
        tethered_layout.addWidget(self.tethered_panel)
        
        # Add tethered tab
        self.tab_widget.addTab(self.tethered_tab, "Tethered Shooting")
        
        # Set the tab widget as central widget
        self.setCentralWidget(self.tab_widget)
        
        # Connect signals
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        
        # Connect to camera detection updates
        self.original_window._old_on_detect_finished = self.original_window._on_detect_finished
        self.original_window._on_detect_finished = self._on_detect_finished_proxy
    
    def _on_tab_changed(self, index: int):
        """Handle tab change events."""
        if index == 1:  # Tethered tab
            # Update tethered view with current cameras
            self._sync_cameras_to_tethered_panel()
        else:  # Standard tab
            # Stop any active tethering to avoid conflicts
            self.tethered_panel.stop_all_tethering()
    
    def _on_detect_finished_proxy(self, detected_cameras_info: Dict[str, Any]):
        """Proxy for the detect finished signal to update the tethered panel."""
        # Call the original handler
        self.original_window._old_on_detect_finished(detected_cameras_info)
        
        # Update the tethered panel with the new cameras
        self._sync_cameras_to_tethered_panel()
    
    def _sync_cameras_to_tethered_panel(self):
        """Synchronize detected cameras to the tethered panel."""
        # Get current cameras from the original window
        current_cameras = {}
        for port, widget in self.original_window.camera_widgets.items():
            current_cameras[port] = widget.camera_info.model
        
        # Get cameras currently in the tethered panel
        tethered_cameras = set(self.tethered_panel.camera_panels.keys())
        
        # Remove cameras that are no longer present
        for port in tethered_cameras - set(current_cameras.keys()):
            self.tethered_panel.remove_camera(port)
        
        # Add new cameras
        for port, model in current_cameras.items():
            if port not in self.tethered_panel.camera_panels:
                self.tethered_panel.add_camera(port, model)
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop tethering
        self.tethered_panel.stop_all_tethering()
        
        # Call parent close handler
        super().closeEvent(event)


if __name__ == "__main__":
    # --- Parse Command Line Arguments ---
    parser = argparse.ArgumentParser(description="Multi-Camera Control Application with Tethered Shooting")
    parser.add_argument('--mock', action='store_true', help='Use mock cameras instead of real hardware')
    parser.add_argument('--mock-count', type=int, default=3, help='Number of mock cameras to create (if --mock is used)')
    parser.add_argument('--offscreen', action='store_true', help='Run in offscreen mode (no visible UI)')
    parser.add_argument('--classic-ui', action='store_true', help='Use the classic UI instead of the minimalist design')
    
    # Format related arguments
    parser.add_argument('--format', choices=['jpeg', 'raw', 'tiff'], help='Default image format for all cameras')
    parser.add_argument('--quality', choices=['standard', 'fine', 'extra-fine'], help='JPEG quality setting')
    
    # Format organization arguments
    parser.add_argument('--organize-by-format', action='store_true', help='Organize captures by format (creates separate directories for each format)')
    parser.add_argument('--format-preference', choices=['keep_all', 'prefer_raw', 'prefer_jpeg'], default='keep_all',
                      help='Format preference for captures (keep_all, prefer_raw, prefer_jpeg)')
    
    # Naming related arguments
    parser.add_argument('--prefix', type=str, help='Default filename prefix')
    parser.add_argument('--naming-template', type=str, help='Naming template for captured files')
    
    # Automatically reset cameras on startup
    parser.add_argument('--auto-reset', action='store_true', help='Automatically reset USB devices and kill competing processes on startup')
    
    args = parser.parse_args()

    # --- Setup Logging ---
    setup_logging(log_level=logging.INFO)
    
    # Kill competing processes if requested
    if args.auto_reset:
        logging.info("Auto-reset enabled, killing competing processes")
        kill_competing_processes()
        
    # --- Ensure Capture Directory Exists ---
    capture_directory = CAPTURE_DIR
    try:
        abs_capture_dir = os.path.abspath(capture_directory)
        os.makedirs(abs_capture_dir, exist_ok=True)
        logging.info(f"Capture directory set to: {abs_capture_dir}")
    except Exception as e:
        logging.error(f"Could not create capture directory '{capture_directory}': {e}")

    # --- Create and Run Application ---
    # Handle offscreen mode if requested
    if args.offscreen:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        logging.info("Running in offscreen mode")

    # Create application with appropriate styling
    if args.classic_ui:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
    else:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setStyleSheet(MINIMALIST_STYLE)

    # Create the main window instance
    try:
        if args.classic_ui:
            window = OriginalMainWindow()
            
            # Apply command line argument settings if provided
            if args.prefix:
                window.filename_prefix = args.prefix
                window.prefix_edit.setText(args.prefix)
                
            if args.naming_template:
                window.naming_template = args.naming_template
        else:
            # Use tethered version of the minimalist window
            window = TetheredMainWindow()
            
            # Get reference to the original window for configuration
            orig_window = window.original_window
            
            # Apply command line argument settings if provided
            if args.prefix:
                orig_window.filename_prefix = args.prefix
                orig_window.prefix_edit.setText(args.prefix)
                
            if args.naming_template:
                orig_window.naming_template = args.naming_template
            
        # Reference to actual functionality window
        func_window = window if args.classic_ui else window.original_window
        
        # Flag to track if mock cameras are being used
        func_window._is_using_mock_cameras = args.mock
            
        # Set up mock cameras if requested
        if args.mock:
            logging.info(f"Using {args.mock_count} mock cameras instead of real hardware")
            
            # Patch the camera manager with mock cameras
            mock_manager = patch_camera_manager(func_window)
            
            # Apply format organization settings if provided
            if mock_manager and hasattr(mock_manager, 'format_organizer'):
                # Set format preference if specified
                if args.format_preference:
                    pref_map = {
                        'keep_all': FormatPreference.KEEP_ALL,
                        'prefer_raw': FormatPreference.PREFER_RAW,
                        'prefer_jpeg': FormatPreference.PREFER_JPEG
                    }
                    if args.format_preference in pref_map:
                        mock_manager.format_organizer.set_format_preference(pref_map[args.format_preference])
                        logging.info(f"Format preference set to: {args.format_preference}")
                
                # Enable/disable format organization
                if args.organize_by_format:
                    mock_manager.format_organizer.set_organize_by_format(True)
                    logging.info("Format organization enabled")
                    
                    # Create the needed format directories
                    import os
                    from datetime import datetime
                    today = datetime.now().strftime("%Y-%m-%d")
                    for format_dir in ["JPEG", "RAW", "TIFF"]:
                        os.makedirs(os.path.join("captures", today, format_dir), exist_ok=True)
                    logging.info(f"Created format directories in captures/{today}/")
            
            # Show a message for clarity
            if not args.offscreen:
                QMessageBox.information(
                    window, 
                    "Mock Camera Mode", 
                    f"Running with {args.mock_count} simulated cameras.\n\n"
                    "No physical camera hardware will be used."
                )
                
            # Force mock cameras to be added to the UI even if gphoto2 detection fails
            if args.classic_ui:
                # Schedule auto-detection after brief delay
                QTimer.singleShot(500, lambda: func_window._on_detect_clicked())
                QTimer.singleShot(2000, lambda: func_window._on_force_mock_detection(mock_manager))
            else:
                QTimer.singleShot(1000, lambda: func_window._on_force_mock_detection(mock_manager))
        
        # Show window unless in offscreen mode
        if not args.offscreen:
            window.show()
        
    except Exception as e:
        logging.exception("Unhandled exception during MainWindow initialization!")
        sys.exit(1) # Exit if main window fails critically

    # Log startup state
    ui_type = "classic" if args.classic_ui else "minimalist+tethered"
    if args.mock and args.offscreen:
        logging.info(f"Application started in offscreen mode with mock cameras ({ui_type} UI).")
    elif args.mock:
        logging.info(f"Application started with mock cameras ({ui_type} UI).")
    elif args.offscreen:
        logging.info(f"Application started in offscreen mode ({ui_type} UI).")
    else:
        logging.info(f"Application started in normal mode ({ui_type} UI).")
        
    # Start the Qt event loop
    sys.exit(app.exec())