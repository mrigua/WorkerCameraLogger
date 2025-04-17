#!/usr/bin/env python3
# screenshot_utility.py - Screenshot functionality for the camera app

import os
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QFileDialog, QCheckBox, QComboBox, QMessageBox,
    QGroupBox, QGridLayout
)
from PyQt6.QtCore import Qt, QSettings, QSize, QTimer
from PyQt6.QtGui import QPixmap, QScreen, QGuiApplication, QImageWriter


class ScreenshotSettings:
    """Manages screenshot capture settings."""
    
    def __init__(self):
        """Initialize screenshot settings with defaults."""
        self.settings = QSettings("MultiCameraApp", "ScreenshotUtility")
        
        # Default locations
        default_location = os.path.join(os.path.expanduser("~"), "Pictures", "CameraAppScreenshots")
        replit_location = os.path.join(os.getcwd(), "Replit_screenshots")
        
        # Load or create settings
        self.locations = self.settings.value("screenshot_locations", {})
        if not self.locations:
            # Set up default locations if none exist
            self.locations = {
                "Default": default_location,
                "Configuration": os.path.join(default_location, "Configurations"),
                "Error Logs": os.path.join(default_location, "ErrorLogs"),
                "Replit": replit_location,
                "Replit-Config": os.path.join(replit_location, "Configuration"),
                "Replit-Camera": os.path.join(replit_location, "Camera_Settings")
            }
            self.settings.setValue("screenshot_locations", self.locations)
            
        # For Replit environment, set the default active location to Replit
        if os.path.exists(replit_location):
            self.active_location = "Replit"
            self.settings.setValue("active_location", self.active_location)
        
        # Default active location
        self.active_location = self.settings.value("active_location", "Default")
        if self.active_location not in self.locations:
            self.active_location = "Default"
            self.settings.setValue("active_location", self.active_location)
        
        # Create directories if they don't exist
        for location in self.locations.values():
            os.makedirs(location, exist_ok=True)
    
    def get_active_save_path(self) -> str:
        """Get the active save path."""
        return self.locations.get(self.active_location, self.locations.get("Default", ""))
    
    def get_all_locations(self) -> Dict[str, str]:
        """Get all configured save locations."""
        return self.locations
    
    def set_active_location(self, location_name: str) -> bool:
        """Set the active save location."""
        if location_name in self.locations:
            self.active_location = location_name
            self.settings.setValue("active_location", location_name)
            return True
        return False
    
    def add_location(self, name: str, path: str) -> bool:
        """Add a new save location."""
        if name and path and name not in self.locations:
            # Create the directory if it doesn't exist
            os.makedirs(path, exist_ok=True)
            
            # Add to locations
            self.locations[name] = path
            self.settings.setValue("screenshot_locations", self.locations)
            return True
        return False
    
    def remove_location(self, name: str) -> bool:
        """Remove a save location."""
        if name in self.locations and name != "Default":
            del self.locations[name]
            
            # Update active location if it was removed
            if self.active_location == name:
                self.active_location = "Default"
                self.settings.setValue("active_location", "Default")
            
            self.settings.setValue("screenshot_locations", self.locations)
            return True
        return False
    
    def update_location(self, name: str, new_path: str) -> bool:
        """Update an existing save location's path."""
        if name in self.locations and new_path:
            # Create the directory if it doesn't exist
            os.makedirs(new_path, exist_ok=True)
            
            # Update the path
            self.locations[name] = new_path
            self.settings.setValue("screenshot_locations", self.locations)
            return True
        return False


class ScreenshotConfigDialog(QDialog):
    """Dialog for configuring screenshot save locations."""
    
    def __init__(self, settings: ScreenshotSettings, parent=None):
        super().__init__(parent)
        
        self.settings = settings
        self.original_locations = settings.get_all_locations().copy()
        self.original_active = settings.active_location
        
        self.setWindowTitle("Screenshot Settings")
        self.setMinimumWidth(500)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Active location selection group
        active_group = QGroupBox("Active Save Location")
        active_layout = QHBoxLayout(active_group)
        
        self.location_combo = QComboBox()
        self.location_combo.addItems(self.settings.get_all_locations().keys())
        self.location_combo.setCurrentText(self.settings.active_location)
        
        active_layout.addWidget(QLabel("Save to:"))
        active_layout.addWidget(self.location_combo, 1)
        
        layout.addWidget(active_group)
        
        # Locations group
        locations_group = QGroupBox("Manage Save Locations")
        locations_layout = QGridLayout(locations_group)
        
        # Add headers
        headers = ["Location Name", "Path", "Actions"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("font-weight: bold;")
            locations_layout.addWidget(label, 0, col)
        
        # Add existing locations
        self.location_widgets = {}
        row = 1
        
        for name, path in self.settings.get_all_locations().items():
            # Name label
            name_label = QLabel(name)
            
            # Path display with browse button
            path_layout = QHBoxLayout()
            path_edit = QLineEdit(path)
            path_edit.setReadOnly(True)
            browse_btn = QPushButton("Browse...")
            browse_btn.clicked.connect(lambda checked, n=name: self._browse_location(n))
            
            path_layout.addWidget(path_edit, 1)
            path_layout.addWidget(browse_btn)
            
            # Actions
            actions_layout = QHBoxLayout()
            edit_btn = QPushButton("Edit")
            edit_btn.clicked.connect(lambda checked, n=name: self._edit_location(n))
            
            delete_btn = QPushButton("Delete")
            delete_btn.setEnabled(name != "Default")  # Can't delete default
            delete_btn.clicked.connect(lambda checked, n=name: self._delete_location(n))
            
            actions_layout.addWidget(edit_btn)
            actions_layout.addWidget(delete_btn)
            
            # Add to grid
            locations_layout.addWidget(name_label, row, 0)
            locations_layout.addLayout(path_layout, row, 1)
            locations_layout.addLayout(actions_layout, row, 2)
            
            # Store widgets for later reference
            self.location_widgets[name] = {
                "name_label": name_label,
                "path_edit": path_edit,
                "browse_btn": browse_btn,
                "edit_btn": edit_btn,
                "delete_btn": delete_btn
            }
            
            row += 1
        
        # Add "Add New" row
        self.new_name_edit = QLineEdit()
        self.new_name_edit.setPlaceholderText("New location name")
        
        new_path_layout = QHBoxLayout()
        self.new_path_edit = QLineEdit()
        self.new_path_edit.setPlaceholderText("Path")
        self.new_path_edit.setReadOnly(True)
        new_browse_btn = QPushButton("Browse...")
        new_browse_btn.clicked.connect(self._browse_new_location)
        
        new_path_layout.addWidget(self.new_path_edit, 1)
        new_path_layout.addWidget(new_browse_btn)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_location)
        
        locations_layout.addWidget(self.new_name_edit, row, 0)
        locations_layout.addLayout(new_path_layout, row, 1)
        locations_layout.addWidget(add_btn, row, 2)
        
        layout.addWidget(locations_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
    
    def _browse_location(self, location_name: str):
        """Browse for a new path for an existing location."""
        current_path = self.settings.locations[location_name]
        new_path = QFileDialog.getExistingDirectory(
            self, f"Select Directory for {location_name}", current_path
        )
        
        if new_path:
            self.settings.update_location(location_name, new_path)
            self.location_widgets[location_name]["path_edit"].setText(new_path)
    
    def _edit_location(self, location_name: str):
        """Edit a location name and path."""
        # Create an edit dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Location: {location_name}")
        
        layout = QVBoxLayout(dialog)
        
        # Name field (only if not default)
        form_layout = QGridLayout()
        row = 0
        
        new_name = location_name
        if location_name != "Default":
            name_label = QLabel("Name:")
            name_edit = QLineEdit(location_name)
            
            form_layout.addWidget(name_label, row, 0)
            form_layout.addWidget(name_edit, row, 1)
            row += 1
        
        # Path field
        path_label = QLabel("Path:")
        path_edit = QLineEdit(self.settings.locations[location_name])
        path_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse...")
        
        form_layout.addWidget(path_label, row, 0)
        form_layout.addWidget(path_edit, row, 1)
        form_layout.addWidget(browse_btn, row, 2)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        
        button_layout.addStretch(1)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)
        
        layout.addLayout(button_layout)
        
        # Connect signals
        browse_btn.clicked.connect(lambda: self._browse_edit_path(path_edit))
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        
        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Update values
            if location_name != "Default" and 'name_edit' in locals():
                new_name = name_edit.text()
            
            new_path = path_edit.text()
            
            # Handle name change
            if new_name != location_name and new_name:
                # Remove old location
                old_path = self.settings.locations[location_name]
                self.settings.remove_location(location_name)
                
                # Add with new name
                self.settings.add_location(new_name, old_path)
                
                # Update combo box
                self.location_combo.clear()
                self.location_combo.addItems(self.settings.get_all_locations().keys())
                
                # Refresh UI (simplified - would be better to update widgets)
                self.reject()  # Close dialog
                dialog = ScreenshotConfigDialog(self.settings, self.parent())
                dialog.exec()
            
            # Handle path change
            if new_path != self.settings.locations.get(new_name, ""):
                self.settings.update_location(new_name, new_path)
                
                # Update path display
                if new_name in self.location_widgets:
                    self.location_widgets[new_name]["path_edit"].setText(new_path)
    
    def _browse_edit_path(self, path_edit: QLineEdit):
        """Browse for a path in the edit dialog."""
        current_path = path_edit.text()
        new_path = QFileDialog.getExistingDirectory(
            self, "Select Directory", current_path
        )
        
        if new_path:
            path_edit.setText(new_path)
    
    def _delete_location(self, location_name: str):
        """Delete a save location."""
        if location_name == "Default":
            QMessageBox.warning(self, "Cannot Delete", "The Default location cannot be deleted.")
            return
        
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the '{location_name}' save location?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            self.settings.remove_location(location_name)
            
            # Update combo box
            self.location_combo.clear()
            self.location_combo.addItems(self.settings.get_all_locations().keys())
            
            # Set active location if needed
            if self.location_combo.currentText() not in self.settings.locations:
                self.location_combo.setCurrentText("Default")
            
            # Refresh UI (simplified - would be better to update widgets)
            self.reject()  # Close dialog
            dialog = ScreenshotConfigDialog(self.settings, self.parent())
            dialog.exec()
    
    def _browse_new_location(self):
        """Browse for a path for a new location."""
        default_path = os.path.expanduser("~")
        new_path = QFileDialog.getExistingDirectory(
            self, "Select Directory for New Location", default_path
        )
        
        if new_path:
            self.new_path_edit.setText(new_path)
    
    def _add_location(self):
        """Add a new save location."""
        name = self.new_name_edit.text().strip()
        path = self.new_path_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a name for the new location.")
            return
        
        if name in self.settings.locations:
            QMessageBox.warning(self, "Duplicate Name", f"A location named '{name}' already exists.")
            return
        
        if not path:
            QMessageBox.warning(self, "No Path Selected", "Please select a path for the new location.")
            return
        
        # Add the new location
        if self.settings.add_location(name, path):
            # Update combo box
            self.location_combo.clear()
            self.location_combo.addItems(self.settings.get_all_locations().keys())
            
            # Clear input fields
            self.new_name_edit.clear()
            self.new_path_edit.clear()
            
            # Refresh UI (simplified - would be better to update widgets)
            self.reject()  # Close dialog
            dialog = ScreenshotConfigDialog(self.settings, self.parent())
            dialog.exec()
        else:
            QMessageBox.warning(self, "Error", "Failed to add new location.")
    
    def accept(self):
        """Handle OK button click."""
        # Set active location
        self.settings.set_active_location(self.location_combo.currentText())
        super().accept()
    
    def reject(self):
        """Handle Cancel button click."""
        # Restore original settings if dialog is cancelled
        # Note: This is not a perfect implementation as changes are applied immediately
        # In a real app, you'd want to make all changes only on accept()
        super().reject()


class ScreenshotTool:
    """Tool for capturing screenshots of the application."""
    
    def __init__(self, parent_widget: Optional[QWidget] = None):
        """Initialize the screenshot tool."""
        self.parent = parent_widget
        self.settings = ScreenshotSettings()
    
    def capture_screenshot(self, window_or_widget: Optional[QWidget] = None,
                          location_name: Optional[str] = None,
                          filename_prefix: str = "",
                          show_notification: bool = True) -> Tuple[bool, str]:
        """
        Capture a screenshot of the specified window or widget.
        
        Args:
            window_or_widget: Window or widget to capture (uses parent if None)
            location_name: Name of save location (uses active if None)
            filename_prefix: Prefix for the filename
            show_notification: Whether to show a notification message
            
        Returns:
            Tuple of (success, file_path)
        """
        # Use the parent if no specific widget is provided
        widget = window_or_widget or self.parent
        if not widget:
            return False, "No widget to capture"
        
        # Get save location
        if location_name and location_name in self.settings.locations:
            save_dir = self.settings.locations[location_name]
        else:
            save_dir = self.settings.get_active_save_path()
        
        # Ensure directory exists
        os.makedirs(save_dir, exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if filename_prefix:
            filename = f"{filename_prefix}_{timestamp}.png"
        else:
            filename = f"screenshot_{timestamp}.png"
        
        save_path = os.path.join(save_dir, filename)
        
        try:
            # Capture screenshot
            screen = QGuiApplication.primaryScreen()
            if not screen:
                return False, "Could not access screen"
            
            pixmap = widget.grab()
            
            # Save to file
            success = pixmap.save(save_path, "PNG")
            
            if success and show_notification:
                self._show_capture_notification(save_path)
            
            return success, save_path
        
        except Exception as e:
            logging.error(f"Screenshot capture error: {e}")
            return False, str(e)
    
    def _show_capture_notification(self, file_path: str):
        """Show a notification that a screenshot was captured."""
        if not self.parent:
            return
        
        # Simple notification using a QMessageBox
        msg = QMessageBox(self.parent)
        msg.setWindowTitle("Screenshot Captured")
        msg.setText(f"Screenshot saved to:\n{file_path}")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        # Add option to open the file
        open_button = msg.addButton("Open File", QMessageBox.ButtonRole.ActionRole)
        open_folder_button = msg.addButton("Open Folder", QMessageBox.ButtonRole.ActionRole)
        
        # Show message
        msg.exec()
        
        # Handle button clicks
        if msg.clickedButton() == open_button:
            self._open_file(file_path)
        elif msg.clickedButton() == open_folder_button:
            self._open_folder(os.path.dirname(file_path))
    
    def _open_file(self, file_path: str):
        """Open a file using the system's default application."""
        try:
            import subprocess
            import sys
            
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', file_path])
            else:  # Linux and other Unix-like
                subprocess.call(['xdg-open', file_path])
        except Exception as e:
            logging.error(f"Error opening file: {e}")
    
    def _open_folder(self, folder_path: str):
        """Open a folder using the system's file explorer."""
        try:
            import subprocess
            import sys
            
            if sys.platform == 'win32':
                os.startfile(folder_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.call(['open', folder_path])
            else:  # Linux and other Unix-like
                subprocess.call(['xdg-open', folder_path])
        except Exception as e:
            logging.error(f"Error opening folder: {e}")
    
    def configure_settings(self):
        """Show configuration dialog for screenshot settings."""
        dialog = ScreenshotConfigDialog(self.settings, self.parent)
        return dialog.exec()


# Testing code when run directly
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    
    # Create a test window
    window = QMainWindow()
    window.setWindowTitle("Screenshot Test")
    
    central = QWidget()
    layout = QVBoxLayout(central)
    
    # Create screenshot tool
    screenshot_tool = ScreenshotTool(window)
    
    # Add buttons
    capture_btn = QPushButton("Capture Screenshot")
    capture_btn.clicked.connect(lambda: screenshot_tool.capture_screenshot())
    
    settings_btn = QPushButton("Configure Screenshot Settings")
    settings_btn.clicked.connect(screenshot_tool.configure_settings)
    
    layout.addWidget(capture_btn)
    layout.addWidget(settings_btn)
    
    window.setCentralWidget(central)
    window.resize(400, 300)
    window.show()
    
    sys.exit(app.exec())