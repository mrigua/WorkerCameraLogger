# main.py
import sys
import os
import logging
import argparse
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer
from gui import MainWindow, CAPTURE_DIR
from logger_setup import setup_logging

# Import for mock camera support
from main_offscreen import patch_camera_manager

if __name__ == "__main__":
    # --- Parse Command Line Arguments ---
    parser = argparse.ArgumentParser(description="Multi-Camera Control Application")
    parser.add_argument('--mock', action='store_true', help='Use mock cameras instead of real hardware')
    parser.add_argument('--mock-count', type=int, default=3, help='Number of mock cameras to create (if --mock is used)')
    parser.add_argument('--offscreen', action='store_true', help='Run in offscreen mode (no visible UI)')
    args = parser.parse_args()

    # --- Setup Logging ---
    # Use DEBUG for detailed output during development/testing
    # Use INFO for normal operation
    setup_logging(log_level=logging.DEBUG)

    # --- Ensure Capture Directory Exists ---
    capture_directory = CAPTURE_DIR # Use the constant from gui.py
    try:
        # Get absolute path for clarity in logs
        abs_capture_dir = os.path.abspath(capture_directory)
        os.makedirs(abs_capture_dir, exist_ok=True)
        logging.info(f"Capture directory set to: {abs_capture_dir}")
    except Exception as e:
        logging.error(f"Could not create capture directory '{capture_directory}': {e}")
        # Decide if the app should exit or just warn
        # For now, we log the error and continue, captures might fail later
        # You could add a QMessageBox here to inform the user

    # --- Create and Run Application ---
    # Handle offscreen mode if requested
    if args.offscreen:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        logging.info("Running in offscreen mode")
    else:
        # Set environment variable for potential Wayland/XCB issues on Linux/WSL
        # Uncomment the following line if you encounter "Could not load the Qt platform plugin" errors
        # os.environ['QT_QPA_PLATFORM'] = 'xcb' # Example: Force XCB
        pass

    app = QApplication(sys.argv)

    # Apply a style for better look & feel
    app.setStyle('Fusion')

    # Create the main window instance
    try:
        window = MainWindow()
        
        # Set up mock cameras if requested
        if args.mock:
            logging.info(f"Using {args.mock_count} mock cameras instead of real hardware")
            patch_camera_manager(window)
            
            # Show a message for clarity
            if not args.offscreen:
                QMessageBox.information(
                    window, 
                    "Mock Camera Mode", 
                    f"Running with {args.mock_count} simulated cameras.\n\n"
                    "No physical camera hardware will be used."
                )
                
            # Schedule auto-detection after brief delay
            QTimer.singleShot(500, lambda: window._on_detect_clicked())
        
        # Show window unless in offscreen mode
        if not args.offscreen:
            window.show()
        
    except Exception as e:
        logging.exception("Unhandled exception during MainWindow initialization!")
        sys.exit(1) # Exit if main window fails critically

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