#!/usr/bin/env python3
"""
Demo script to demonstrate the screenshot functionality.
This script shows how to use the screenshot functionality in the Multi-Camera app
with a simple UI that allows testing the various screenshot options.
"""

import sys
import os
import argparse
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QComboBox, QLineEdit, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon

# Add parent directory to path to allow for direct running of this script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import screenshot utility
from attached_assets.screenshot_utility import ScreenshotTool, ScreenshotSettings, ScreenshotConfigDialog

class ScreenshotDemoWindow(QMainWindow):
    """Demo window to show screenshot functionality."""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Screenshot Functionality Demo")
        self.setGeometry(100, 100, 800, 600)
        
        # Initialize screenshot tool
        self.screenshot_tool = ScreenshotTool()
        self.screenshot_settings = ScreenshotSettings()
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        
        # Add logo and title
        title_layout = QHBoxLayout()
        
        title_label = QLabel("Screenshot Feature Demo")
        title_label.setStyleSheet("font-size: 24pt; font-weight: bold;")
        
        title_layout.addStretch(1)
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        
        main_layout.addLayout(title_layout)
        main_layout.addSpacing(20)
        
        # Current settings display
        settings_group = QGroupBox("Current Screenshot Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        self.active_location_label = QLabel(f"Active Save Location: {self.screenshot_settings.active_location}")
        self.active_path_label = QLabel(f"Save Path: {self.screenshot_settings.get_active_save_path()}")
        
        settings_layout.addWidget(self.active_location_label)
        settings_layout.addWidget(self.active_path_label)
        
        main_layout.addWidget(settings_group)
        
        # Screenshot actions
        actions_group = QGroupBox("Screenshot Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        # Take screenshot button
        take_screenshot_btn = QPushButton("Take Screenshot")
        take_screenshot_btn.setIcon(QIcon.fromTheme("camera-photo"))
        take_screenshot_btn.clicked.connect(self._on_take_screenshot)
        
        # Configure settings button
        configure_btn = QPushButton("Configure Screenshot Settings")
        configure_btn.setIcon(QIcon.fromTheme("preferences-system"))
        configure_btn.clicked.connect(self._on_configure_settings)
        
        # Show available locations button
        show_locations_btn = QPushButton("Show Available Save Locations")
        show_locations_btn.clicked.connect(self._on_show_locations)
        
        # Change active location
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("Change Active Location:"))
        
        self.location_combo = QComboBox()
        self.location_combo.addItems(self.screenshot_settings.get_all_locations().keys())
        self.location_combo.setCurrentText(self.screenshot_settings.active_location)
        self.location_combo.currentTextChanged.connect(self._on_change_location)
        
        location_layout.addWidget(self.location_combo)
        
        # Add custom prefix
        prefix_layout = QHBoxLayout()
        prefix_layout.addWidget(QLabel("Screenshot Prefix:"))
        
        self.prefix_edit = QLineEdit("demo")
        
        prefix_layout.addWidget(self.prefix_edit)
        
        # Add all controls to actions layout
        actions_layout.addWidget(take_screenshot_btn)
        actions_layout.addWidget(configure_btn)
        actions_layout.addWidget(show_locations_btn)
        actions_layout.addLayout(location_layout)
        actions_layout.addLayout(prefix_layout)
        
        main_layout.addWidget(actions_group)
        
        # Results display
        results_group = QGroupBox("Screenshot Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_label = QLabel("No screenshots taken yet.")
        results_layout.addWidget(self.results_label)
        
        main_layout.addWidget(results_group)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Schedule updates of the UI
        self._update_ui()
        
        # Timer for UI updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_ui)
        self.update_timer.start(1000)  # Update UI every second
    
    def _update_ui(self):
        """Update the UI with latest settings information."""
        self.active_location_label.setText(f"Active Save Location: {self.screenshot_settings.active_location}")
        self.active_path_label.setText(f"Save Path: {self.screenshot_settings.get_active_save_path()}")
        
        # Update combo box if needed
        current_locations = list(self.screenshot_settings.get_all_locations().keys())
        combo_items = [self.location_combo.itemText(i) for i in range(self.location_combo.count())]
        
        if set(current_locations) != set(combo_items):
            current_text = self.location_combo.currentText()
            self.location_combo.clear()
            self.location_combo.addItems(current_locations)
            if current_text in current_locations:
                self.location_combo.setCurrentText(current_text)
            else:
                self.location_combo.setCurrentText(self.screenshot_settings.active_location)
    
    def _on_take_screenshot(self):
        """Handle taking a screenshot."""
        # Get the prefix from the UI
        prefix = self.prefix_edit.text().strip()
        
        # Take the screenshot
        success, filepath = self.screenshot_tool.take_screenshot(prefix)
        
        if success:
            self.statusBar().showMessage(f"Screenshot saved to: {filepath}", 5000)
            self.results_label.setText(f"Latest screenshot: {os.path.basename(filepath)}\nSaved to: {filepath}")
        else:
            self.statusBar().showMessage("Failed to take screenshot", 5000)
            self.results_label.setText("Screenshot failed")
    
    def _on_configure_settings(self):
        """Show the screenshot configuration dialog."""
        dialog = ScreenshotConfigDialog(self.screenshot_settings, self)
        if dialog.exec():
            self._update_ui()
    
    def _on_show_locations(self):
        """Show all available save locations."""
        locations = self.screenshot_settings.get_all_locations()
        
        message = "Available Save Locations:\n\n"
        for name, path in locations.items():
            message += f"{name}: {path}\n"
        
        QMessageBox.information(self, "Save Locations", message)
    
    def _on_change_location(self, location_name):
        """Change the active save location."""
        if self.screenshot_settings.set_active_location(location_name):
            self.statusBar().showMessage(f"Active location changed to {location_name}", 3000)
            self._update_ui()


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Screenshot functionality demo")
    parser.add_argument("--offscreen", action="store_true", help="Run in offscreen mode")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set platform to offscreen if requested
    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        print("Running in offscreen mode")
    
    # Initialize Qt application
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = ScreenshotDemoWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()