# main_enhanced_minimalist.py - Main entry point for minimalist multi-camera control app
import sys
import os
import logging
import argparse
from PyQt6.QtWidgets import (
    QApplication, QMessageBox, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QLabel, QScrollArea, QFrame, QToolBar, 
    QStatusBar, QToolButton, QMenu, QStyle, QLineEdit, QSizePolicy
)
from PyQt6.QtCore import QTimer, QSize, Qt
from PyQt6.QtGui import QAction, QIcon, QColor, QPalette

from gui_updated import MainWindow as OriginalMainWindow, CAPTURE_DIR
from logger_setup import setup_logging
from main_offscreen import patch_camera_manager
from camera_reset import kill_competing_processes, reset_usb_device, reset_all_cameras

try:
    from format_organizer import FormatPreference
except ImportError:
    # Try relative import
    from attached_assets.format_organizer import FormatPreference

# === Minimalist UI Constants === 
MINIMALIST_PALETTE = {
    "primary": "#2c3e50",     # Dark blue-gray
    "secondary": "#34495e",   # Slightly lighter blue-gray
    "accent": "#3498db",      # Blue
    "success": "#2ecc71",     # Green
    "warning": "#f39c12",     # Orange
    "error": "#e74c3c",       # Red
    "background": "#ecf0f1",  # Light gray
    "text": "#2c3e50",        # Dark blue-gray (same as primary)
    "text_light": "#7f8c8d"   # Medium gray
}

MINIMALIST_STYLE = f"""
QMainWindow, QDialog {{
    background-color: {MINIMALIST_PALETTE["background"]};
}}

QToolBar, QStatusBar {{
    background-color: {MINIMALIST_PALETTE["primary"]};
    color: white;
    border: none;
}}

QPushButton {{
    background-color: {MINIMALIST_PALETTE["accent"]};
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
}}

QPushButton:hover {{
    background-color: #2980b9;
}}

QPushButton:pressed {{
    background-color: #1c6ea4;
}}

QPushButton:disabled {{
    background-color: #95a5a6;
    color: #ecf0f1;
}}

QToolButton {{
    background-color: transparent;
    color: white;
    border: none;
    padding: 8px;
}}

QToolButton:hover {{
    background-color: rgba(255, 255, 255, 0.1);
}}

QLabel {{
    color: {MINIMALIST_PALETTE["text"]};
}}

QGroupBox {{
    border: 1px solid {MINIMALIST_PALETTE["secondary"]};
    border-radius: 4px;
    margin-top: 1em;
    padding-top: 10px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: {MINIMALIST_PALETTE["text"]};
}}

QScrollArea {{
    border: 1px solid {MINIMALIST_PALETTE["secondary"]};
    border-radius: 4px;
}}

QComboBox {{
    border: 1px solid {MINIMALIST_PALETTE["secondary"]};
    border-radius: 4px;
    padding: 5px;
    background-color: white;
}}

QLineEdit {{
    border: 1px solid {MINIMALIST_PALETTE["secondary"]};
    border-radius: 4px;
    padding: 5px;
    background-color: white;
}}

QStatusBar QLabel {{
    color: white;
}}
"""

class MinimalistMainWindow(QMainWindow):
    """A minimalist redesign of the camera control application UI."""
    
    def __init__(self):
        super().__init__()
        
        # Configure window
        self.setWindowTitle("Multi-Camera Controller")
        self.setGeometry(100, 100, 1024, 700)
        
        # Create backing instance of original MainWindow for functionality
        self.original_window = OriginalMainWindow()
        
        # Set up the UI with minimalist design
        self._setup_ui()
        
        # Connect to original window signals
        self._connect_signals()
        
        # Set up auto-reset for Sony cameras
        self._setup_auto_reset()
    
    def _setup_ui(self):
        """Set up the minimalist UI."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # === Create toolbar ===
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        
        # Detect action
        detect_action = QAction("Detect Cameras", self)
        detect_action.triggered.connect(self.original_window._on_detect_clicked)
        toolbar.addAction(detect_action)
        
        # Capture all action
        capture_action = QAction("Capture All", self)
        capture_action.triggered.connect(self.original_window._on_capture_all_clicked)
        toolbar.addAction(capture_action)
        
        # Toggle preview action
        self.preview_action = QAction("Start Previews", self)
        self.preview_action.setCheckable(True)
        self.preview_action.toggled.connect(self.original_window._on_toggle_previews)
        toolbar.addAction(self.preview_action)
        
        toolbar.addSeparator()
        
        # Reset cameras action
        reset_action = QAction("Reset Cameras", self)
        reset_action.triggered.connect(self._on_reset_cameras)
        toolbar.addAction(reset_action)
        
        # Profile menu button
        profile_menu = QMenu()
        
        manage_profiles_action = QAction("Manage Profiles...", self)
        manage_profiles_action.triggered.connect(self.original_window._on_manage_profiles)
        
        select_profile_action = QAction("Apply Profile...", self)
        select_profile_action.triggered.connect(self.original_window._on_select_profile)
        
        profile_capture_action = QAction("Apply Profile and Capture...", self)
        profile_capture_action.triggered.connect(self.original_window._on_profile_capture)
        
        profile_menu.addAction(manage_profiles_action)
        profile_menu.addAction(select_profile_action)
        profile_menu.addAction(profile_capture_action)
        
        profile_button = QToolButton()
        profile_button.setText("Profiles")
        profile_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        profile_button.setMenu(profile_menu)
        toolbar.addWidget(profile_button)
        
        self.addToolBar(toolbar)
        
        # Save options bar
        save_options = QWidget()
        save_options_layout = QHBoxLayout(save_options)
        save_options_layout.setContentsMargins(10, 5, 10, 5)
        
        # Choose directory button
        choose_dir_button = QPushButton("Save Directory")
        choose_dir_button.clicked.connect(self.original_window._choose_save_directory)
        
        # Save directory label (linked from original window)
        self.original_window.save_dir_label = QLabel(f"Save: {self.original_window.save_directory}")
        self.original_window.save_dir_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Prefix input
        prefix_label = QLabel("Prefix:")
        self.original_window.prefix_edit = QLineEdit(self.original_window.filename_prefix)
        self.original_window.prefix_edit.setPlaceholderText("Optional prefix...")
        self.original_window.prefix_edit.setMaximumWidth(150)
        self.original_window.prefix_edit.textChanged.connect(self.original_window._update_filename_prefix)
        
        # Add to layout
        save_options_layout.addWidget(choose_dir_button)
        save_options_layout.addWidget(self.original_window.save_dir_label)
        save_options_layout.addWidget(prefix_label)
        save_options_layout.addWidget(self.original_window.prefix_edit)
        
        main_layout.addWidget(save_options)
        
        # Camera grid section (linked from original window)
        self.original_window.camera_scroll = QScrollArea()
        self.original_window.camera_scroll.setWidgetResizable(True)
        self.original_window.camera_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.original_window.camera_container = QWidget()
        self.original_window.camera_layout = QHBoxLayout(self.original_window.camera_container)
        self.original_window.camera_layout.setContentsMargins(10, 10, 10, 10)
        self.original_window.camera_layout.setSpacing(10)
        
        self.original_window.camera_scroll.setWidget(self.original_window.camera_container)
        main_layout.addWidget(self.original_window.camera_scroll, 1)  # Give it stretch factor
        
        # Status bar
        status_bar = QStatusBar()
        self.original_window.status_bar = QLabel("Status: Initializing...")
        status_bar.addPermanentWidget(self.original_window.status_bar, 1)
        self.setStatusBar(status_bar)
        
        # Store references to key buttons for enabling/disabling
        self.detect_action = detect_action
        self.capture_action = capture_action
        self.select_profile_action = select_profile_action
        self.profile_capture_action = profile_capture_action
        
        # Set initial button states
        self.capture_action.setEnabled(False)
        self.preview_action.setEnabled(False)
        self.select_profile_action.setEnabled(False)
        self.profile_capture_action.setEnabled(False)
    
    def _connect_signals(self):
        """Connect signals between this window and the original main window."""
        # Redirect signal connections for enabling/disabling buttons
        self.original_window._old_on_detect_task_finished = self.original_window._on_detect_task_finished
        self.original_window._on_detect_task_finished = self._on_detect_task_finished_proxy
        
        # Start initial detection
        QTimer.singleShot(500, self.original_window._on_detect_clicked)
    
    def _on_detect_task_finished_proxy(self):
        """Proxy for the detect task finished signal to update our UI buttons."""
        # First call the original method
        self.original_window._old_on_detect_task_finished()
        
        # Now update our UI
        self.detect_action.setEnabled(True)
        
        # Update button states based on camera availability
        has_cameras = bool(self.original_window.camera_widgets)
        self.capture_action.setEnabled(has_cameras)
        self.preview_action.setEnabled(has_cameras)
        self.select_profile_action.setEnabled(has_cameras)
        self.profile_capture_action.setEnabled(has_cameras)
        
        # Update preview button text if needed
        self.preview_action.setText("Stop Previews" if self.preview_action.isChecked() else "Start Previews")
    
    def _setup_auto_reset(self):
        """Set up automatic USB device reset for Sony cameras."""
        # We'll reset cameras when the app starts
        QTimer.singleShot(100, self._reset_sony_cameras)
    
    def _on_reset_cameras(self):
        """Handle reset cameras button click."""
        # Show a confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Reset Camera Connections?",
            "This will attempt to fix 'Could not claim the USB device' errors by:\n\n"
            "1. Killing competing processes\n"
            "2. Resetting USB connections\n"
            "3. Re-detecting all cameras\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Show busy status
            self.original_window._update_status_bar("Resetting camera connections...")
            
            # Run the reset in a separate thread to avoid UI freezing
            worker = Worker(reset_all_cameras)
            worker.signals.finished.connect(self._on_camera_reset_finished)
            self.original_window.threadpool.start(worker)
            
            # Disable the detect button during reset
            self.detect_action.setEnabled(False)
    
    def _on_camera_reset_finished(self):
        """Handle completion of camera reset operation."""
        self.original_window._update_status_bar("Camera reset completed, detecting cameras...")
        
        # Run camera detection
        QTimer.singleShot(500, self.original_window._on_detect_clicked)
    
    def _reset_sony_cameras(self):
        """Attempt to fix Sony camera connectivity issues."""
        # Don't show dialog, just silently reset when app starts
        kill_competing_processes()
        logging.info("Killed potential competing processes during startup")
        
        # Look for Sony cameras in auto-detect output
        self.original_window._update_status_bar("Checking for Sony cameras...")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop any running processes
        if hasattr(self.original_window, 'preview_timer') and self.original_window.preview_timer.isActive():
            self.original_window.preview_timer.stop()
        
        # Accept the event to close the window
        event.accept()


class MinimalistApp(QApplication):
    """Application class with minimalist styling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Apply minimalist style
        self.setStyle('Fusion')
        self.setStyleSheet(MINIMALIST_STYLE)
        
        # Set dark palette for contrast
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(MINIMALIST_PALETTE["background"]))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(MINIMALIST_PALETTE["text"]))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(MINIMALIST_PALETTE["background"]))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(MINIMALIST_PALETTE["secondary"]))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(MINIMALIST_PALETTE["secondary"]))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor("white"))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(MINIMALIST_PALETTE["text"]))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(MINIMALIST_PALETTE["accent"]))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(MINIMALIST_PALETTE["accent"]))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(MINIMALIST_PALETTE["accent"]))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
        
        # Apply palette to the application
        self.setPalette(dark_palette)


if __name__ == "__main__":
    # --- Parse Command Line Arguments ---
    parser = argparse.ArgumentParser(description="Multi-Camera Control Application")
    parser.add_argument('--mock', action='store_true', help='Use mock cameras instead of real hardware')
    parser.add_argument('--mock-count', type=int, default=3, help='Number of mock cameras to create (if --mock is used)')
    parser.add_argument('--offscreen', action='store_true', help='Run in offscreen mode (no visible UI)')
    
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
    
    # Create application with minimalist styling
    app = MinimalistApp(sys.argv)

    # Create the main window instance
    try:
        window = MinimalistMainWindow()
        
        # Get reference to the original window for configuration
        orig_window = window.original_window
        
        # Apply command line argument settings if provided
        if args.prefix:
            orig_window.filename_prefix = args.prefix
            orig_window.prefix_edit.setText(args.prefix)
            
        if args.naming_template:
            orig_window.naming_template = args.naming_template
            
        # Set up mock cameras if requested
        if args.mock:
            logging.info(f"Using {args.mock_count} mock cameras instead of real hardware")
            
            # Patch the camera manager with mock cameras
            mock_manager = patch_camera_manager(orig_window)
            
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
            QTimer.singleShot(1000, lambda: orig_window._on_force_mock_detection(mock_manager))
        
        # Show window unless in offscreen mode
        if not args.offscreen:
            window.show()
        
    except Exception as e:
        logging.exception("Unhandled exception during MainWindow initialization!")
        sys.exit(1) # Exit if main window fails critically

    # Log startup state
    if args.mock and args.offscreen:
        logging.info("Application started in offscreen mode with mock cameras.")
    elif args.mock:
        logging.info("Application started with mock cameras.")
    elif args.offscreen:
        logging.info("Application started in offscreen mode.")
    else:
        logging.info("Application started in normal mode.")
        
    # Start the Qt event loop
    sys.exit(app.exec())