# profile_dialogs.py
import logging
from typing import Optional, List, Dict, Callable
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QComboBox, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QWidget, QGroupBox, QFormLayout, QDialogButtonBox,
    QRadioButton, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from camera_profiles import CameraProfile, CameraProfileSettings, profile_manager


class ProfileEditorDialog(QDialog):
    """Dialog for creating or editing a camera profile."""
    
    def __init__(self, parent=None, profile: Optional[CameraProfile] = None):
        """Initialize the dialog, optionally with an existing profile to edit."""
        super().__init__(parent)
        
        self.profile = profile
        self.editing_mode = profile is not None
        
        self.setWindowTitle("Create Camera Profile" if not self.editing_mode else "Edit Camera Profile")
        self.setMinimumWidth(400)
        
        self._init_ui()
        
        if self.editing_mode:
            self._populate_fields()
    
    def _init_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Basic information section
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        
        form_layout.addRow("Profile Name:", self.name_edit)
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Camera settings section
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QFormLayout()
        
        self.iso_combo = QComboBox()
        self.iso_combo.setEditable(False)
        self.iso_combo.addItem("(No Change)", None)
        for iso in ["100", "200", "400", "800", "1600", "3200"]:
            self.iso_combo.addItem(iso, iso)
        
        self.aperture_combo = QComboBox()
        self.aperture_combo.setEditable(False)
        self.aperture_combo.addItem("(No Change)", None)
        for aperture in ["f/1.8", "f/2.8", "f/4", "f/5.6", "f/8", "f/11", "f/16"]:
            self.aperture_combo.addItem(aperture, aperture)
        
        self.shutter_speed_combo = QComboBox()
        self.shutter_speed_combo.setEditable(False)
        self.shutter_speed_combo.addItem("(No Change)", None)
        for speed in ["1/4000", "1/2000", "1/1000", "1/500", "1/250", "1/125", "1/60", "1/30", "1/15", "1/8"]:
            self.shutter_speed_combo.addItem(speed, speed)
        
        settings_layout.addRow("ISO:", self.iso_combo)
        settings_layout.addRow("Aperture:", self.aperture_combo)
        settings_layout.addRow("Shutter Speed:", self.shutter_speed_combo)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.save_button = QPushButton("Save Profile")
        self.save_button.clicked.connect(self._save_profile)
        self.save_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _populate_fields(self):
        """Fill the form with values from the existing profile being edited."""
        if not self.profile:
            return
            
        self.name_edit.setText(self.profile.name)
        self.description_edit.setText(self.profile.description)
        
        # Set dropdowns to the profile's current values
        if self.profile.settings.iso:
            index = self.iso_combo.findData(self.profile.settings.iso)
            if index >= 0:
                self.iso_combo.setCurrentIndex(index)
        
        if self.profile.settings.aperture:
            index = self.aperture_combo.findData(self.profile.settings.aperture)
            if index >= 0:
                self.aperture_combo.setCurrentIndex(index)
        
        if self.profile.settings.shutter_speed:
            index = self.shutter_speed_combo.findData(self.profile.settings.shutter_speed)
            if index >= 0:
                self.shutter_speed_combo.setCurrentIndex(index)
    
    def _save_profile(self):
        """Validate and save the profile from form values."""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.critical(self, "Error", "Profile name cannot be empty.")
            return
        
        if not self.editing_mode and name in profile_manager.get_profile_names():
            QMessageBox.critical(self, "Error", f"A profile named '{name}' already exists.")
            return
        
        # Get values from dropdowns - None for "No Change" selections
        iso = self.iso_combo.currentData()
        aperture = self.aperture_combo.currentData()
        shutter_speed = self.shutter_speed_combo.currentData()
        
        # Check if at least one setting is specified
        if iso is None and aperture is None and shutter_speed is None:
            QMessageBox.critical(
                self, 
                "Error", 
                "At least one camera setting (ISO, Aperture, or Shutter Speed) must be specified."
            )
            return
        
        # Create or update the profile
        settings = CameraProfileSettings(
            iso=iso, 
            aperture=aperture, 
            shutter_speed=shutter_speed
        )
        
        if self.editing_mode:
            # Update existing profile
            self.profile.name = name
            self.profile.description = self.description_edit.toPlainText().strip()
            self.profile.settings = settings
            profile = self.profile
        else:
            # Create new profile
            profile = CameraProfile(
                name=name,
                description=self.description_edit.toPlainText().strip(),
                settings=settings
            )
        
        # Save it
        if profile_manager.save_profile(profile):
            logging.info(f"Saved camera profile: {name}")
            self.accept()  # Close dialog on success
        else:
            QMessageBox.critical(self, "Error", f"Failed to save profile '{name}'.")


class ProfileManagerDialog(QDialog):
    """Dialog for managing (viewing, editing, deleting) camera profiles."""
    
    profile_selected = pyqtSignal(CameraProfile)
    
    def __init__(self, parent=None, mode: str = "manage"):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget
            mode: Either "manage" (default) or "select" to determine dialog behavior
        """
        super().__init__(parent)
        
        self.mode = mode
        if self.mode == "select":
            self.setWindowTitle("Select Camera Profile")
        else:
            self.setWindowTitle("Manage Camera Profiles")
            
        self.setMinimumSize(500, 400)
        
        self.selected_profile = None
        
        self._init_ui()
        self._refresh_profile_list()
    
    def _init_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Profile list
        list_layout = QVBoxLayout()
        list_label = QLabel("Available Profiles:")
        list_layout.addWidget(list_label)
        
        self.profile_list = QListWidget()
        self.profile_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.profile_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        list_layout.addWidget(self.profile_list)
        
        layout.addLayout(list_layout)
        
        # Details section
        details_group = QGroupBox("Profile Details")
        details_layout = QVBoxLayout()
        
        self.name_label = QLabel()
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        
        settings_layout = QFormLayout()
        self.iso_label = QLabel()
        self.aperture_label = QLabel()
        self.shutter_speed_label = QLabel()
        
        settings_layout.addRow("ISO:", self.iso_label)
        settings_layout.addRow("Aperture:", self.aperture_label)
        settings_layout.addRow("Shutter Speed:", self.shutter_speed_label)
        
        details_layout.addWidget(self.name_label)
        details_layout.addWidget(self.description_label)
        details_layout.addLayout(settings_layout)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Button section
        button_layout = QHBoxLayout()
        
        # Left-side: actions on selected profile
        action_layout = QHBoxLayout()
        
        if self.mode == "manage":
            self.new_button = QPushButton("New Profile")
            self.new_button.clicked.connect(self._on_new_profile)
            
            self.edit_button = QPushButton("Edit")
            self.edit_button.clicked.connect(self._on_edit_profile)
            self.edit_button.setEnabled(False)
            
            self.delete_button = QPushButton("Delete")
            self.delete_button.clicked.connect(self._on_delete_profile)
            self.delete_button.setEnabled(False)
            
            action_layout.addWidget(self.new_button)
            action_layout.addWidget(self.edit_button)
            action_layout.addWidget(self.delete_button)
        else:  # select mode
            self.select_button = QPushButton("Apply Profile")
            self.select_button.clicked.connect(self._on_select_profile)
            self.select_button.setEnabled(False)
            
            action_layout.addWidget(self.select_button)
            
        button_layout.addLayout(action_layout)
        
        # Right-side: dialog buttons
        dialog_buttons = QDialogButtonBox()
        
        if self.mode == "manage":
            # Fix for PyQt6 compatibility
            self.close_button = QPushButton("Close")
            dialog_buttons.addButton(self.close_button, QDialogButtonBox.ButtonRole.RejectRole)
            self.close_button.clicked.connect(self.reject)
        else:  # select mode
            # Fix for PyQt6 compatibility
            self.cancel_button = QPushButton("Cancel")
            dialog_buttons.addButton(self.cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
            self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(dialog_buttons)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _refresh_profile_list(self):
        """Update the list of profiles displayed in the dialog."""
        self.profile_list.clear()
        
        profiles = profile_manager.get_all_profiles()
        for profile in profiles:
            item = QListWidgetItem(profile.name)
            item.setData(Qt.ItemDataRole.UserRole, profile)
            self.profile_list.addItem(item)
    
    def _on_selection_changed(self):
        """Handle selection of a profile in the list."""
        selected_items = self.profile_list.selectedItems()
        
        if selected_items:
            # Enable buttons that work on a selected profile
            if self.mode == "manage":
                self.edit_button.setEnabled(True)
                self.delete_button.setEnabled(True)
            else:  # select mode
                self.select_button.setEnabled(True)
            
            # Display the selected profile's details
            profile = selected_items[0].data(Qt.ItemDataRole.UserRole)
            self.selected_profile = profile
            
            self.name_label.setText(f"<b>{profile.name}</b>")
            self.description_label.setText(profile.description)
            
            self.iso_label.setText(profile.settings.iso or "(No Change)")
            self.aperture_label.setText(profile.settings.aperture or "(No Change)")
            self.shutter_speed_label.setText(profile.settings.shutter_speed or "(No Change)")
        else:
            # Clear and disable when no selection
            if self.mode == "manage":
                self.edit_button.setEnabled(False)
                self.delete_button.setEnabled(False)
            else:  # select mode
                self.select_button.setEnabled(False)
            
            self.selected_profile = None
            
            self.name_label.setText("")
            self.description_label.setText("")
            self.iso_label.setText("")
            self.aperture_label.setText("")
            self.shutter_speed_label.setText("")
    
    def _on_item_double_clicked(self, item):
        """Handle double-click on a profile item."""
        if self.mode == "manage":
            self._on_edit_profile()
        else:  # select mode
            self._on_select_profile()
    
    def _on_new_profile(self):
        """Create a new profile."""
        editor = ProfileEditorDialog(self)
        result = editor.exec()
        
        if result == QDialog.DialogCode.Accepted:
            self._refresh_profile_list()
    
    def _on_edit_profile(self):
        """Edit the selected profile."""
        if not self.selected_profile:
            return
            
        editor = ProfileEditorDialog(self, self.selected_profile)
        result = editor.exec()
        
        if result == QDialog.DialogCode.Accepted:
            self._refresh_profile_list()
            
            # Try to re-select the profile after refresh
            for i in range(self.profile_list.count()):
                item = self.profile_list.item(i)
                profile = item.data(Qt.ItemDataRole.UserRole)
                if profile.name == self.selected_profile.name:
                    self.profile_list.setCurrentItem(item)
                    break
    
    def _on_delete_profile(self):
        """Delete the selected profile."""
        if not self.selected_profile:
            return
            
        profile_name = self.selected_profile.name
        
        # Confirm deletion
        result = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the profile '{profile_name}'?"
        )
        
        if result == QMessageBox.StandardButton.Yes:
            if profile_manager.delete_profile(profile_name):
                logging.info(f"Deleted camera profile: {profile_name}")
                self._refresh_profile_list()
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete profile '{profile_name}'.")
    
    def _on_select_profile(self):
        """Emit signal with the selected profile when in select mode."""
        if self.mode == "select" and self.selected_profile:
            self.profile_selected.emit(self.selected_profile)
            self.accept()


class ApplyProfileDialog(QDialog):
    """Dialog for applying a profile to selected cameras."""
    
    def __init__(self, parent=None, profile: CameraProfile = None, camera_ports: List[str] = None,
                 camera_names: Dict[str, str] = None):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget
            profile: The profile to apply
            camera_ports: List of available camera ports
            camera_names: Mapping of port to display name for each camera
        """
        super().__init__(parent)
        
        self.profile = profile
        self.camera_ports = camera_ports or []
        self.camera_names = camera_names or {}
        
        self.setWindowTitle(f"Apply Profile: {profile.name}")
        self.setMinimumWidth(400)
        
        self.selected_cameras = []
        
        self._init_ui()
    
    def _init_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Profile info
        info_group = QGroupBox("Profile Settings")
        info_layout = QFormLayout()
        
        self.iso_label = QLabel(self.profile.settings.iso or "(No Change)")
        self.aperture_label = QLabel(self.profile.settings.aperture or "(No Change)")
        self.shutter_speed_label = QLabel(self.profile.settings.shutter_speed or "(No Change)")
        
        info_layout.addRow("ISO:", self.iso_label)
        info_layout.addRow("Aperture:", self.aperture_label)
        info_layout.addRow("Shutter Speed:", self.shutter_speed_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Camera selection
        camera_group = QGroupBox("Apply To Cameras")
        camera_layout = QVBoxLayout()
        
        # Radio buttons for selection mode
        selection_layout = QHBoxLayout()
        
        self.all_cameras_radio = QRadioButton("All Cameras")
        self.all_cameras_radio.setChecked(True)
        self.all_cameras_radio.toggled.connect(self._on_selection_mode_changed)
        
        self.selected_cameras_radio = QRadioButton("Selected Cameras")
        self.selected_cameras_radio.toggled.connect(self._on_selection_mode_changed)
        
        selection_layout.addWidget(self.all_cameras_radio)
        selection_layout.addWidget(self.selected_cameras_radio)
        
        camera_layout.addLayout(selection_layout)
        
        # Individual camera checkboxes
        self.camera_checkboxes = []
        
        for port in self.camera_ports:
            name = self.camera_names.get(port, port)
            checkbox = QCheckBox(f"{name} ({port})")
            checkbox.setChecked(True)
            checkbox.setEnabled(False)  # Initially disabled when "All Cameras" is selected
            checkbox.setProperty("port", port)
            self.camera_checkboxes.append(checkbox)
            camera_layout.addWidget(checkbox)
        
        camera_group.setLayout(camera_layout)
        layout.addWidget(camera_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.apply_button = QPushButton("Apply Profile")
        self.apply_button.clicked.connect(self._on_apply)
        self.apply_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _on_selection_mode_changed(self, checked):
        """Handle change between "All Cameras" and "Selected Cameras" modes."""
        # Only act when a radio button is checked (not when unchecked)
        if not checked:
            return
            
        # Enable or disable checkboxes based on selection mode
        for checkbox in self.camera_checkboxes:
            checkbox.setEnabled(self.selected_cameras_radio.isChecked())
    
    def _on_apply(self):
        """Apply the profile to selected cameras."""
        if self.all_cameras_radio.isChecked():
            # All cameras are selected
            self.selected_cameras = self.camera_ports
        else:
            # Only checked cameras are selected
            self.selected_cameras = []
            for checkbox in self.camera_checkboxes:
                if checkbox.isChecked():
                    port = checkbox.property("port")
                    self.selected_cameras.append(port)
        
        if not self.selected_cameras:
            QMessageBox.critical(self, "Error", "No cameras selected. Please select at least one camera.")
            return
        
        self.accept()
    
    def get_selected_cameras(self):
        """Return the list of selected camera ports."""
        return self.selected_cameras


class SmartProfileDetectionDialog(QDialog):
    """Dialog for configuring and using smart profile detection."""
    
    profile_selected = pyqtSignal(CameraProfile, str)  # profile, camera_port
    
    def __init__(self, parent=None, camera_info=None, camera_port=None):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget
            camera_info: Information about the camera for which to detect profiles
            camera_port: The port of the camera for which to detect profiles
        """
        super().__init__(parent)
        
        self.camera_info = camera_info
        self.camera_port = camera_port
        
        if camera_info:
            self.setWindowTitle(f"Smart Profile Detection: {camera_info.model}")
        else:
            self.setWindowTitle("Smart Profile Detection")
            
        self.setMinimumSize(550, 450)
        
        self.suggested_profiles = []
        self.selected_profile = None
        
        self._init_ui()
        
        # Detect profiles as soon as dialog is shown
        if self.camera_info:
            self._detect_profiles()
    
    def _init_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Camera info header
        if self.camera_info:
            model_name = self.camera_info.model
            header_label = QLabel(f"<h3>Smart Profile Detection for {model_name}</h3>")
            header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(header_label)
            
            # Brief explanation
            info_text = (
                "Smart profile detection analyzes your camera and suggests profiles "
                "that are likely to work well with it. The confidence score shows how "
                "well each profile matches your camera."
            )
            info_label = QLabel(info_text)
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
            
            # Current settings
            settings_group = QGroupBox("Current Camera Settings")
            settings_layout = QFormLayout()
            
            # Show current camera settings
            if self.camera_info.settings:
                iso_label = QLabel(self.camera_info.settings.iso or "Not set")
                aperture_label = QLabel(self.camera_info.settings.aperture or "Not set")
                shutter_speed_label = QLabel(self.camera_info.settings.shutter_speed or "Not set")
                
                settings_layout.addRow("ISO:", iso_label)
                settings_layout.addRow("Aperture:", aperture_label)
                settings_layout.addRow("Shutter Speed:", shutter_speed_label)
            else:
                settings_layout.addRow("Settings:", QLabel("No settings available"))
            
            settings_group.setLayout(settings_layout)
            layout.addWidget(settings_group)
        
        # List of suggested profiles
        profile_group = QGroupBox("Suggested Profiles")
        profile_layout = QVBoxLayout()
        
        self.profile_list = QListWidget()
        self.profile_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.profile_list.itemDoubleClicked.connect(self._on_apply_profile)
        profile_layout.addWidget(self.profile_list)
        
        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)
        
        # Profile details
        details_group = QGroupBox("Profile Details")
        details_layout = QVBoxLayout()
        
        self.details_label = QLabel("Select a profile to see details")
        self.details_label.setWordWrap(True)
        details_layout.addWidget(self.details_label)
        
        settings_layout = QFormLayout()
        self.iso_label = QLabel()
        self.aperture_label = QLabel()
        self.shutter_speed_label = QLabel()
        
        settings_layout.addRow("ISO:", self.iso_label)
        settings_layout.addRow("Aperture:", self.aperture_label)
        settings_layout.addRow("Shutter Speed:", self.shutter_speed_label)
        
        details_layout.addLayout(settings_layout)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Smart detection settings
        self.enabled_checkbox = QCheckBox("Enable Smart Detection")
        self.enabled_checkbox.setChecked(profile_manager.smart_detection_enabled)
        self.enabled_checkbox.clicked.connect(self._on_toggle_smart_detection)
        button_layout.addWidget(self.enabled_checkbox)
        
        button_layout.addStretch()
        
        # Action buttons
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.apply_button = QPushButton("Apply Selected Profile")
        self.apply_button.clicked.connect(self._on_apply_profile)
        self.apply_button.setEnabled(False)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _detect_profiles(self):
        """Detect and display suggested profiles for the camera."""
        if not self.camera_info:
            return
            
        # Get profile suggestions from profile manager
        self.suggested_profiles = profile_manager.get_suggested_profiles(self.camera_info)
        
        # Clear and repopulate the list
        self.profile_list.clear()
        
        if not self.suggested_profiles:
            self.profile_list.addItem("No suitable profiles found")
            return
            
        # Add items to the list, sorted by confidence
        for profile, confidence in self.suggested_profiles:
            # Format confidence as percentage
            confidence_str = f"{confidence * 100:.1f}%"
            
            # Create a formatted item
            text = f"{profile.name} (Match: {confidence_str})"
            item = QListWidgetItem(text)
            
            # Store the profile and confidence as item data
            item.setData(Qt.ItemDataRole.UserRole, profile)
            item.setData(Qt.ItemDataRole.UserRole + 1, confidence)
            
            # Color code the item based on confidence
            if confidence >= 0.9:
                # High confidence - green
                item.setForeground(Qt.GlobalColor.darkGreen)
            elif confidence >= 0.7:
                # Good confidence - blue
                item.setForeground(Qt.GlobalColor.darkBlue)
            elif confidence >= 0.5:
                # Medium confidence - neutral
                pass
            else:
                # Low confidence - gray
                item.setForeground(Qt.GlobalColor.gray)
            
            self.profile_list.addItem(item)
    
    def _on_selection_changed(self):
        """Handle selection of a profile in the list."""
        selected_items = self.profile_list.selectedItems()
        
        if selected_items:
            # Get the selected profile
            profile = selected_items[0].data(Qt.ItemDataRole.UserRole)
            confidence = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)
            
            if profile:
                self.selected_profile = profile
                
                # Update the details display
                self.details_label.setText(f"<b>{profile.name}</b>: {profile.description}")
                
                self.iso_label.setText(profile.settings.iso or "(No Change)")
                self.aperture_label.setText(profile.settings.aperture or "(No Change)")
                self.shutter_speed_label.setText(profile.settings.shutter_speed or "(No Change)")
                
                # Enable the apply button
                self.apply_button.setEnabled(True)
            else:
                self._clear_details()
        else:
            self._clear_details()
    
    def _clear_details(self):
        """Clear the profile details display."""
        self.selected_profile = None
        self.details_label.setText("Select a profile to see details")
        self.iso_label.setText("")
        self.aperture_label.setText("")
        self.shutter_speed_label.setText("")
        self.apply_button.setEnabled(False)
    
    def _on_apply_profile(self):
        """Apply the selected profile to the camera."""
        if self.selected_profile and self.camera_port:
            # Emit the signal with profile and camera port
            self.profile_selected.emit(self.selected_profile, self.camera_port)
            
            # Learn from this selection
            profile_manager.learn_from_assignment(self.camera_info, self.selected_profile)
            
            # Close the dialog
            self.accept()
    
    def _on_toggle_smart_detection(self, enabled):
        """Toggle smart profile detection on/off."""
        profile_manager.set_smart_detection_enabled(enabled)
        
        # If turning on, refresh the profile list
        if enabled and self.camera_info:
            self._detect_profiles()