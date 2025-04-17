# gui_updated.py
import sys
import os
import logging
import time
from typing import Optional, List, Dict, Tuple, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QFrame, QGridLayout, QComboBox, QTextEdit, QMessageBox, QSizePolicy, QApplication,
    QFileDialog, QLineEdit, QMenu, QToolBar, QStatusBar, QCheckBox,
    QDialog, QFormLayout, QGroupBox, QTabWidget, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QThreadPool
from PyQt6.QtGui import QPixmap, QImage, QPalette, QColor, QTextCursor, QIcon, QAction

from camera_manager import CameraManager, CameraInfo, CameraSettings
from worker import Worker
from logger_setup import QTextEditLogHandler
from camera_profiles import profile_manager, CameraProfile, CameraProfileSettings
from profile_dialogs import ProfileManagerDialog, ProfileEditorDialog, ApplyProfileDialog

# --- Constants ---
PREVIEW_REFRESH_INTERVAL = 2000 # milliseconds (2 seconds)
PLACEHOLDER_IMAGE_PATH = "placeholder.png" # Optional placeholder image
CAPTURE_DIR = "captures" # Default capture directory

# --- Styling Constants ---
STYLE_PREVIEW_CONNECTED = "background-color: #333; color: white; border: 2px solid limegreen;"
STYLE_PREVIEW_BUSY = "background-color: #333; color: white; border: 2px solid dodgerblue;"
STYLE_PREVIEW_ERROR = "background-color: #333; color: white; border: 2px solid red;"
STYLE_PREVIEW_DISCONNECTED = "background-color: #333; color: white; border: 1px solid gray;"

STYLE_STATUS_CONNECTED = "font-weight: bold; color: green;"
STYLE_STATUS_BUSY = "font-weight: bold; color: blue;"
STYLE_STATUS_ERROR = "font-weight: bold; color: red;"
STYLE_STATUS_DISCONNECTED = "font-weight: bold; color: gray;"

# --- SUPPORTED FILE FORMATS ---
IMAGE_FORMATS = [
    "JPEG (Standard)",
    "JPEG Fine",
    "JPEG Extra Fine",
    "RAW",
    "RAW + JPEG",
    "TIFF"
]

# --- Advanced Naming Templates ---
NAMING_TEMPLATES = [
    # Original templates
    "Camera_{camera}_Date_{date}",
    "Session_{prefix}_Camera_{camera}_{date}_{time}",
    "{prefix}_{date}_{time}_{seq}",
    "{camera}_{iso}_{aperture}_{shutter}_{date}",
    # New professional naming templates
    "{date}_ProjectName_{prefix}_Camera{camera}_{seq}",  # Date-Project-Camera-Sequence
    "ProjectName_{prefix}_{date}_Location_Camera{camera}_{seq}",  # Project-Date-Location-Camera
    "{date}_ProfileName_{profile}_Description_{prefix}_Camera{camera}",  # Date-Profile-Descriptor
    "{date}/ProjectName_{prefix}/Camera{camera}/{seq}",  # Hierarchical-Numeric
    "{date}_Camera{camera}_ISO{iso}_F{aperture}_{shutter}_Description_{prefix}",  # Technical-Descriptive
    "Custom"
]

# --- Template Descriptions for Help ---
TEMPLATE_DESCRIPTIONS = {
    "Camera_{camera}_Date_{date}": "Basic template with camera name and date",
    "Session_{prefix}_Camera_{camera}_{date}_{time}": "Session-based template with camera and timestamp",
    "{prefix}_{date}_{time}_{seq}": "Simple sequence-based template with timestamp",
    "{camera}_{iso}_{aperture}_{shutter}_{date}": "Technical template with camera settings",
    "{date}_ProjectName_{prefix}_Camera{camera}_{seq}": "Date-first professional format for chronological sorting",
    "ProjectName_{prefix}_{date}_Location_Camera{camera}_{seq}": "Project-first format ideal for client projects",
    "{date}_ProfileName_{profile}_Description_{prefix}_Camera{camera}": "Profile-based format ideal for studio work",
    "{date}/ProjectName_{prefix}/Camera{camera}/{seq}": "Hierarchical format for folder-based organization",
    "{date}_Camera{camera}_ISO{iso}_F{aperture}_{shutter}_Description_{prefix}": "Technical format embedding actual camera settings",
    "Custom": "Create your own custom naming template"
}

# --- Camera Control Widget ---
class CameraControlWidget(QFrame):
    """Widget to display controls for a single camera."""
    capture_requested = pyqtSignal(str)
    setting_changed = pyqtSignal(str, str, str)
    retry_capture_requested = pyqtSignal(str)
    
    # New signals for enhanced settings
    format_changed = pyqtSignal(str, str)
    naming_changed = pyqtSignal(str, str)

    def __init__(self, camera_info: CameraInfo, parent=None):
        super().__init__(parent)
        self.port = camera_info.port
        self.camera_info = camera_info
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(300)
        
        # Selected format and naming template
        self.selected_format = "JPEG (Standard)"
        self.selected_naming = NAMING_TEMPLATES[0]
        
        # Create layout and UI elements
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header_layout = QHBoxLayout()
        self.name_label = QLabel(f"<b>{camera_info.model}</b><br/>({camera_info.port})") 
        self.name_label.setWordWrap(True)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setStyleSheet(STYLE_STATUS_DISCONNECTED)
        
        header_layout.addWidget(self.name_label)
        header_layout.addWidget(self.status_label)
        layout.addLayout(header_layout)
        
        # Error label (initially hidden)
        self.error_label = QLabel("No Error")
        self.error_label.setStyleSheet("color: red; font-style: italic;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
        
        # Preview area
        self.preview_label = QLabel("No Preview Available")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedHeight(200)
        self.preview_label.setMinimumWidth(220)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setStyleSheet(STYLE_PREVIEW_DISCONNECTED)
        self._load_placeholder_image()
        layout.addWidget(self.preview_label)
        
        # Settings area
        settings_group = QGroupBox("Camera Settings")
        settings_layout = QGridLayout()
        
        # ISO, Aperture, Shutter Speed
        iso_label = QLabel("ISO:")
        self.iso_combo = QComboBox()
        self.iso_combo.currentIndexChanged.connect(lambda: self._on_setting_change("iso", self.iso_combo.currentText()))
        
        aperture_label = QLabel("Aperture:")
        self.aperture_combo = QComboBox()
        self.aperture_combo.currentIndexChanged.connect(lambda: self._on_setting_change("aperture", self.aperture_combo.currentText()))
        
        shutter_label = QLabel("Shutter:")
        self.shutter_combo = QComboBox()
        self.shutter_combo.currentIndexChanged.connect(lambda: self._on_setting_change("shutterspeed", self.shutter_combo.currentText()))
        
        # File format selection
        format_label = QLabel("Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(IMAGE_FORMATS)
        self.format_combo.currentIndexChanged.connect(lambda: self._on_format_change(self.format_combo.currentText()))
        
        # Add to grid layout
        settings_layout.addWidget(iso_label, 0, 0)
        settings_layout.addWidget(self.iso_combo, 0, 1)
        settings_layout.addWidget(aperture_label, 1, 0)
        settings_layout.addWidget(self.aperture_combo, 1, 1)
        settings_layout.addWidget(shutter_label, 2, 0)
        settings_layout.addWidget(self.shutter_combo, 2, 1)
        settings_layout.addWidget(format_label, 3, 0)
        settings_layout.addWidget(self.format_combo, 3, 1)
        
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        
        # Capture button
        self.capture_button = QPushButton("Capture Image")
        self.capture_button.clicked.connect(self._emit_capture_request)
        self.capture_button.setEnabled(False)
        layout.addWidget(self.capture_button)
        
        # Retry button (initially hidden)
        self.retry_button = QPushButton("Retry Capture")
        self.retry_button.clicked.connect(self._emit_retry_request)
        self.retry_button.setVisible(False)
        layout.addWidget(self.retry_button)
        
        # Initially update widget with camera info
        self.update_info(camera_info)

    def _load_placeholder_image(self):
        """Load a placeholder image for when there's no preview available."""
        # Try to use a placeholder image if it exists, otherwise just display text
        if os.path.exists(PLACEHOLDER_IMAGE_PATH):
            pixmap = QPixmap(PLACEHOLDER_IMAGE_PATH)
            scaled_pixmap = pixmap.scaled(220, 200, Qt.AspectRatioMode.KeepAspectRatio)
            self.preview_label.setPixmap(scaled_pixmap)
        else:
            self.preview_label.setText("No Preview Available")

    def _emit_capture_request(self):
        self.capture_requested.emit(self.port)
        
    def _emit_retry_request(self):
        self.retry_capture_requested.emit(self.port)
        self.retry_button.setVisible(False)
        
    def _on_setting_change(self, setting_type: str, value: str):
        """Handle when camera settings are changed by the user."""
        if value and value != "N/A":
            self.setting_changed.emit(self.port, setting_type, value)
            
    def _on_format_change(self, format_value: str):
        """Handle when image format is changed by the user."""
        self.selected_format = format_value
        self.format_changed.emit(self.port, format_value)

    def update_info(self, camera_info: CameraInfo):
        """Update the widget with current camera information."""
        self.camera_info = camera_info
        
        # Update model and port labels 
        self.name_label.setText(f"<b>{camera_info.model}</b><br/>({camera_info.port})")
        
        # Update status display
        self.status_label.setText(camera_info.status)
        
        # Determine if camera is connected, busy (status contains substring), or in error state
        is_connected = camera_info.status == "Connected"
        is_busy = "..." in camera_info.status or camera_info.status in ["Detecting", "Capturing", "Applying Settings", "Busy"]
        is_error = camera_info.status == "Error" or camera_info.last_error is not None
        
        # Update UI based on status
        if is_connected:
            self.status_label.setStyleSheet(STYLE_STATUS_CONNECTED)
            self.preview_label.setStyleSheet(STYLE_PREVIEW_CONNECTED)
            self.capture_button.setEnabled(True)
            self.retry_button.setVisible(False)
            self.error_label.setVisible(False)
            self._set_controls_enabled(True)
        elif is_busy:
            self.status_label.setStyleSheet(STYLE_STATUS_BUSY)
            self.preview_label.setStyleSheet(STYLE_PREVIEW_BUSY)
            self.capture_button.setEnabled(False)
            self.retry_button.setVisible(False)
            self.error_label.setVisible(False)
            self._set_controls_enabled(False)
        elif is_error:
            self.status_label.setStyleSheet(STYLE_STATUS_ERROR)
            self.preview_label.setStyleSheet(STYLE_PREVIEW_ERROR)
            self.capture_button.setEnabled(True)
            self.retry_button.setVisible(True)
            self.error_label.setText(f"Last Error: {camera_info.last_error or 'Unknown'}")
            self.error_label.setVisible(True)
            self._set_controls_enabled(True)
        else: # Disconnected or other
            self.status_label.setStyleSheet(STYLE_STATUS_DISCONNECTED)
            self.preview_label.setStyleSheet(STYLE_PREVIEW_DISCONNECTED)
            self.capture_button.setEnabled(False)
            self.retry_button.setVisible(False)
            self.error_label.setVisible(False)
            self._set_controls_enabled(False)
            self._load_placeholder_image()

        # Update dropdown contents with current settings
        self._update_combo(self.iso_combo, camera_info.settings.iso, camera_info.settings.iso_choices)
        self._update_combo(self.aperture_combo, camera_info.settings.aperture, camera_info.settings.aperture_choices)
        self._update_combo(self.shutter_combo, camera_info.settings.shutter_speed, camera_info.settings.shutter_speed_choices)

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all camera controls based on camera status."""
        self._enable_combo_if_valid(self.iso_combo, enabled)
        self._enable_combo_if_valid(self.aperture_combo, enabled)
        self._enable_combo_if_valid(self.shutter_combo, enabled)
        self.format_combo.setEnabled(enabled)
        
    def _enable_combo_if_valid(self, combo: QComboBox, parent_enabled: bool):
        """Enable combo box only if it has valid items and parent allows it."""
        has_valid_items = combo.count() > 0 and combo.itemText(0) not in ["N/A", "Error", "Unknown", "Parse Error"]
        combo.setEnabled(parent_enabled and has_valid_items)
        
    def _update_combo(self, combo: QComboBox, current_value: Optional[str], choices: List[str]):
        """Update a combo box with current choices while preserving selection when possible."""
        was_blocked = combo.blockSignals(True)
        stored_current_text = combo.currentText()
        combo.clear()
        
        parent_allows_enable = combo.isEnabled()
        valid_value = current_value and current_value not in ["Error", "Unknown", "N/A", "Parse Error"]
        
        if choices:
            combo.addItems(choices)
            if valid_value and current_value in choices:
                combo.setCurrentText(current_value)
            elif stored_current_text in choices:
                combo.setCurrentText(stored_current_text)
            elif choices:
                combo.setCurrentIndex(0)
            combo.setEnabled(parent_allows_enable and True)
        elif valid_value:
            combo.addItem(current_value)
            combo.setCurrentIndex(0)
            combo.setEnabled(parent_allows_enable and True)
        else:
            combo.addItem(current_value or "N/A")
            combo.setEnabled(False)
            
        combo.blockSignals(was_blocked)

    def update_preview(self, image_data: Optional[bytes]):
        """Update the preview image with new data from camera."""
        if image_data:
            try:
                qimage = QImage.fromData(image_data)
                if not qimage.isNull():
                    pixmap = QPixmap.fromImage(qimage)
                    scaled_pixmap = pixmap.scaled(
                        self.preview_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.preview_label.setPixmap(scaled_pixmap)
                else:
                    self.preview_label.setText(f"Preview Error\nInvalid Data\n{self.port}")
                    logging.warning(f"Invalid image data for {self.port}")
            except Exception as e:
                self.preview_label.setText(f"Preview Error\nLoad Failed\n{self.port}")
                logging.error(f"Error loading preview for {self.port}: {e}")
        else:
            self._load_placeholder_image()
            
    def apply_profile(self, profile: CameraProfile):
        """Apply settings from a profile to this camera."""
        # Don't proceed if camera isn't connected
        if self.camera_info.status != "Connected":
            logging.warning(f"Cannot apply profile to {self.port} - not connected")
            return False
            
        settings = profile.settings
        changes_made = False
        
        # Apply ISO if specified in profile and available for camera
        if settings.iso and settings.iso in self.camera_info.settings.iso_choices:
            self._on_setting_change("iso", settings.iso)
            changes_made = True
            
        # Apply aperture if specified in profile and available for camera
        if settings.aperture and settings.aperture in self.camera_info.settings.aperture_choices:
            self._on_setting_change("aperture", settings.aperture)
            changes_made = True
            
        # Apply shutter speed if specified in profile and available for camera
        if settings.shutter_speed and settings.shutter_speed in self.camera_info.settings.shutter_speed_choices:
            self._on_setting_change("shutterspeed", settings.shutter_speed)
            changes_made = True
            
        return changes_made


# --- Advanced Naming Options Dialog ---
class AdvancedNamingDialog(QDialog):
    """Dialog for configuring advanced file naming options."""
    
    def __init__(self, parent=None, current_template=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Naming Options")
        self.setMinimumWidth(450)
        
        self.selected_template = current_template or NAMING_TEMPLATES[0]
        self.custom_template = ""
        
        self._init_ui()
        
    def _init_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout()
        
        # Template selection
        template_group = QGroupBox("Naming Template")
        template_layout = QVBoxLayout()
        
        template_label = QLabel("Select a naming template:")
        template_layout.addWidget(template_label)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(NAMING_TEMPLATES)
        if self.selected_template in NAMING_TEMPLATES:
            self.template_combo.setCurrentText(self.selected_template)
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        template_layout.addWidget(self.template_combo)
        
        # Template description label
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("font-style: italic; color: #666;")
        if self.template_combo.currentText() in TEMPLATE_DESCRIPTIONS:
            self.description_label.setText(TEMPLATE_DESCRIPTIONS[self.template_combo.currentText()])
        template_layout.addWidget(self.description_label)
        
        # Custom template input (initially hidden)
        self.custom_group = QGroupBox("Custom Template")
        custom_layout = QVBoxLayout()
        
        help_label = QLabel("Use the following placeholders:\n"
                          "{camera} - Camera model\n"
                          "{date} - Date (YYYYMMDD)\n"
                          "{time} - Time (HHMMSS)\n"
                          "{prefix} - File prefix\n"
                          "{seq} - Sequence number\n"
                          "{iso} - ISO setting\n"
                          "{aperture} - Aperture setting\n"
                          "{shutter} - Shutter speed\n"
                          "{profile} - Profile name\n"
                          "ProjectName - Your project name\n"
                          "Location - Location name\n"
                          "Description - Content description")
        custom_layout.addWidget(help_label)
        
        self.custom_edit = QLineEdit()
        self.custom_edit.setPlaceholderText("Enter custom naming template...")
        custom_layout.addWidget(self.custom_edit)
        
        self.custom_group.setLayout(custom_layout)
        self.custom_group.setVisible(self.template_combo.currentText() == "Custom")
        
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)
        layout.addWidget(self.custom_group)
        
        # Example section
        example_group = QGroupBox("Example")
        example_layout = QVBoxLayout()
        
        self.example_label = QLabel("Example filename will appear here")
        example_layout.addWidget(self.example_label)
        
        example_group.setLayout(example_layout)
        layout.addWidget(example_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Update example
        self._update_example()
        
    def _on_template_changed(self):
        """Handle template selection change."""
        self.selected_template = self.template_combo.currentText()
        self.custom_group.setVisible(self.selected_template == "Custom")
        # Update description when template changes
        if self.selected_template in TEMPLATE_DESCRIPTIONS:
            self.description_label.setText(TEMPLATE_DESCRIPTIONS[self.selected_template])
        else:
            self.description_label.setText("")
        self._update_example()
        
    def _update_example(self):
        """Update the example filename display."""
        template = self.selected_template
        if template == "Custom":
            template = self.custom_edit.text() or "custom_template"
            
        # Sample values for example
        example = template
        example = example.replace("{camera}", "Nikon_Z6")
        example = example.replace("{date}", "20250417")
        example = example.replace("{time}", "145530")
        example = example.replace("{prefix}", "Wedding")
        example = example.replace("{seq}", "001")
        example = example.replace("{iso}", "400")
        example = example.replace("{aperture}", "f2.8")
        example = example.replace("{shutter}", "1-500")
        example = example.replace("ProjectName", "Smith_Wedding")
        example = example.replace("Location", "GrandHall")
        example = example.replace("ProfileName", "WeddingLow")
        example = example.replace("Description", "BrideGroom")
        example = example.replace("{profile}", "Reception")
        
        # Format the example display
        if "/" in example:
            # For hierarchical formats, show the full path
            self.example_label.setText(f"Example full path: {example}.jpg")
        else:
            # For normal formats, just show the filename
            self.example_label.setText(f"Example: {example}.jpg")
        
    def get_template(self):
        """Get the currently selected template."""
        if self.selected_template == "Custom":
            return self.custom_edit.text()
        return self.selected_template


# --- Main Window ---
class MainWindow(QWidget):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt Multi-Camera Control")
        self.setGeometry(100, 100, 1024, 768)
        
        # Core functionality
        self.camera_manager = CameraManager()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max(4, QThreadPool.globalInstance().maxThreadCount()))
        logging.info(f"Thread pool max threads: {self.threadpool.maxThreadCount()}")
        
        # State management
        self.camera_widgets: Dict[str, CameraControlWidget] = {}
        self.capture_results: Dict[str, Optional[str]] = {}
        self._current_capture_all_expected_count = 0
        
        # File management
        self.save_directory = os.path.abspath(CAPTURE_DIR)
        self.filename_prefix = ""
        self.naming_template = NAMING_TEMPLATES[0]
        
        # Initialize Camera Profiles
        profile_manager.create_default_profiles()
        
        # Set up UI elements
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setMaximumHeight(150)
        self.log_text_edit.setStyleSheet("background-color: #f0f0f0;")
        self._setup_gui_logging()
        
        self._init_ui()
        
        # Set up preview timer
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self._request_previews)
        
        # Start initial detection
        self._update_status_bar("Starting initial detection...")
        self._run_task(
            self.camera_manager.detect_cameras,
            on_result_slot=self._on_detect_finished,
            on_finish_slot=self._on_detect_task_finished
        )
        self.detect_button.setEnabled(False)

    def _init_ui(self):
        """Set up the main UI layout and elements."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # --- Top Toolbar Section ---
        toolbar_layout = QHBoxLayout()
        
        # Camera control buttons
        self.detect_button = QPushButton("Detect Cameras")
        self.detect_button.clicked.connect(self._on_detect_clicked)
        
        self.capture_all_button = QPushButton("Capture All")
        self.capture_all_button.clicked.connect(self._on_capture_all_clicked)
        self.capture_all_button.setEnabled(False)
        
        self.toggle_preview_button = QPushButton("Start Previews")
        self.toggle_preview_button.setCheckable(True)
        self.toggle_preview_button.toggled.connect(self._on_toggle_previews)
        self.toggle_preview_button.setEnabled(False)
        
        # Profiles menu button
        self.profiles_button = QPushButton("Camera Profiles")
        profiles_menu = QMenu(self)
        
        self.manage_profiles_action = QAction("Manage Profiles...", self)
        self.manage_profiles_action.triggered.connect(self._on_manage_profiles)
        
        self.select_profile_action = QAction("Apply Profile...", self)
        self.select_profile_action.triggered.connect(self._on_select_profile)
        self.select_profile_action.setEnabled(False)  # Only enable when cameras are connected
        
        self.profile_capture_action = QAction("Apply Profile and Capture...", self)
        self.profile_capture_action.triggered.connect(self._on_profile_capture)
        self.profile_capture_action.setEnabled(False)  # Only enable when cameras are connected
        
        profiles_menu.addAction(self.manage_profiles_action)
        profiles_menu.addAction(self.select_profile_action)
        profiles_menu.addAction(self.profile_capture_action)
        self.profiles_button.setMenu(profiles_menu)
        
        # Add all controls to toolbar
        toolbar_layout.addWidget(self.detect_button)
        toolbar_layout.addWidget(self.capture_all_button)
        toolbar_layout.addWidget(self.toggle_preview_button)
        toolbar_layout.addWidget(self.profiles_button)
        toolbar_layout.addStretch()
        
        main_layout.addLayout(toolbar_layout)

        # --- Save Options Section ---
        save_options_layout = QHBoxLayout()
        
        # Directory selection
        self.choose_dir_button = QPushButton("Choose Save Directory")
        self.choose_dir_button.clicked.connect(self._choose_save_directory)
        
        self.save_dir_label = QLabel(f"Save Dir: {self.save_directory}")
        self.save_dir_label.setToolTip(self.save_directory)
        self.save_dir_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred)
        self.save_dir_label.setWordWrap(False)
        
        # Filename prefix
        prefix_label = QLabel("Filename Prefix:")
        self.prefix_edit = QLineEdit(self.filename_prefix)
        self.prefix_edit.setPlaceholderText("Optional prefix...")
        self.prefix_edit.setFixedWidth(150)
        self.prefix_edit.textChanged.connect(self._update_filename_prefix)
        
        # Advanced naming options
        self.adv_naming_button = QPushButton("Advanced Naming...")
        self.adv_naming_button.clicked.connect(self._on_advanced_naming)
        
        # Add to layout
        save_options_layout.addWidget(self.choose_dir_button)
        save_options_layout.addWidget(self.save_dir_label)
        save_options_layout.addSpacing(20)
        save_options_layout.addWidget(prefix_label)
        save_options_layout.addWidget(self.prefix_edit)
        save_options_layout.addWidget(self.adv_naming_button)
        
        main_layout.addLayout(save_options_layout)
        
        # --- Camera Grid Section ---
        self.camera_scroll = QScrollArea()
        self.camera_scroll.setWidgetResizable(True)
        self.camera_scroll.setMinimumHeight(300)
        
        self.camera_container = QWidget()
        self.camera_layout = QGridLayout(self.camera_container)
        self.camera_layout.setContentsMargins(10, 10, 10, 10)
        self.camera_layout.setSpacing(10)
        
        self.camera_scroll.setWidget(self.camera_container)
        main_layout.addWidget(self.camera_scroll)
        
        # --- Status and Log Section ---
        self.status_bar = QLabel("Status: Initializing...")
        self.status_bar.setFrameShape(QFrame.Shape.Panel)
        self.status_bar.setFrameShadow(QFrame.Shadow.Sunken)
        self.status_bar.setStyleSheet("padding: 3px;")
        
        main_layout.addWidget(self.status_bar)
        main_layout.addWidget(self.log_text_edit)

    def _setup_gui_logging(self):
        """Configure logging to both file and GUI."""
        self.log_handler = QTextEditLogHandler(self.log_signal)
        self.log_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(self.log_handler)
        self.log_signal.connect(self._append_log_message)
        
    def _append_log_message(self, message):
        """Append log message to the text edit."""
        self.log_text_edit.append(message)
        self.log_text_edit.moveCursor(QTextCursor.MoveOperation.End)
        
    def _update_status_bar(self, message: str):
        """Update the status bar with a message."""
        self.status_bar.setText(f"Status: {message}")
        
    def _run_task(self, func, on_finish_slot=None, on_error_slot=None, on_result_slot=None, *args, **kwargs):
        """Run a function in a background thread."""
        worker = Worker(func, *args, **kwargs)
        
        if on_finish_slot:
            worker.signals.finished.connect(on_finish_slot)
        if on_error_slot:
            worker.signals.error.connect(on_error_slot)
        if on_result_slot:
            worker.signals.result.connect(on_result_slot)
            
        # Connect default slots for progress and status
        worker.signals.progress.connect(lambda v: self._update_status_bar(f"Progress: {v}%"))
        worker.signals.status_update.connect(self._update_status_bar)
        
        self.threadpool.start(worker)
        
    def _on_worker_error(self, error_tuple):
        """Handle errors from worker threads."""
        exctype, value, traceback_str = error_tuple
        logging.error(f"Worker error: {value}\n{traceback_str}")
        self._update_status_bar(f"Error: {value}")
    
    def _choose_save_directory(self):
        """Opens a dialog to choose the save directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setDirectory(self.save_directory)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_dir = dialog.selectedFiles()[0]
            self.save_directory = selected_dir
            self.save_dir_label.setText(f"Save Dir: {selected_dir}")
            self.save_dir_label.setToolTip(selected_dir)
            logging.info(f"Save directory set to: {selected_dir}")
    
    def _update_filename_prefix(self, text):
        """Updates the internal filename prefix state."""
        self.filename_prefix = text.strip()
        
    def _on_advanced_naming(self):
        """Show the advanced naming options dialog."""
        dialog = AdvancedNamingDialog(self, self.naming_template)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.naming_template = dialog.get_template()
            logging.info(f"Updated naming template: {self.naming_template}")
    
    def _on_detect_clicked(self):
        """Handle detect button click."""
        self._update_status_bar("Detecting cameras...")
        self.detect_button.setEnabled(False)
        self._run_task(
            self.camera_manager.detect_cameras,
            on_result_slot=self._on_detect_finished,
            on_finish_slot=self._on_detect_task_finished,
            on_error_slot=self._on_worker_error
        )
    
    def _on_capture_all_clicked(self):
        """Handle capture all button click."""
        connected_cameras = [port for port, widget in self.camera_widgets.items()
                            if widget.camera_info.status == "Connected"]
        
        if not connected_cameras:
            logging.warning("No connected cameras to capture from")
            return
            
        self._update_status_bar(f"Capturing from {len(connected_cameras)} cameras...")
        self.capture_all_button.setEnabled(False)
        
        # Reset results tracking
        self.capture_results = {}
        self._current_capture_all_expected_count = len(connected_cameras)
        
        # Start capture for each camera
        for port in connected_cameras:
            self._on_single_capture_requested(port)
    
    def _on_toggle_previews(self, checked):
        """Handle preview toggle button."""
        if checked:
            self.toggle_preview_button.setText("Stop Previews")
            self.preview_timer.start(PREVIEW_REFRESH_INTERVAL)
            logging.info(f"Started previews with {PREVIEW_REFRESH_INTERVAL}ms interval")
        else:
            self.toggle_preview_button.setText("Start Previews")
            self.preview_timer.stop()
            logging.info("Stopped previews")
    
    def _on_manage_profiles(self):
        """Open the profile manager dialog."""
        dialog = ProfileManagerDialog(self, mode="manage")
        dialog.exec()
    
    def _on_select_profile(self):
        """Open the profile selection dialog."""
        # Get available profiles
        profiles = profile_manager.get_all_profiles()
        if not profiles:
            QMessageBox.information(self, "No Profiles", "No camera profiles are available. Create profiles first.")
            return
            
        # Open profile selection dialog
        dialog = ProfileManagerDialog(self, mode="select")
        dialog.profile_selected.connect(self._on_profile_selected)
        dialog.exec()
    
    def _on_profile_selected(self, profile: CameraProfile):
        """Handle when a profile is selected from the dialog."""
        # Get all connected camera ports
        connected_cameras = [port for port, widget in self.camera_widgets.items()
                           if widget.camera_info.status == "Connected"]
                           
        if not connected_cameras:
            QMessageBox.warning(self, "No Cameras", "No connected cameras to apply profile to.")
            return
            
        # Show the apply profile dialog
        camera_names = {port: widget.camera_info.model for port, widget in self.camera_widgets.items()}
        apply_dialog = ApplyProfileDialog(self, profile, connected_cameras, camera_names)
        
        if apply_dialog.exec() == QDialog.DialogCode.Accepted:
            selected_cameras = apply_dialog.get_selected_cameras()
            if not selected_cameras:
                return
                
            logging.info(f"Applying profile '{profile.name}' to {len(selected_cameras)} cameras")
            
            # Apply profile to selected cameras
            applied_count = 0
            for port in selected_cameras:
                if port in self.camera_widgets:
                    widget = self.camera_widgets[port]
                    if widget.apply_profile(profile):
                        applied_count += 1
                        
            if applied_count > 0:
                self._update_status_bar(f"Applied profile '{profile.name}' to {applied_count} cameras")
            else:
                self._update_status_bar(f"No settings applied from profile '{profile.name}'")
                
    def _on_profile_capture(self):
        """Open the profile selection dialog for profile application and capture."""
        # Import profile capture manager
        from profile_capture import ProfileCaptureManager
        
        # Get available profiles
        profiles = profile_manager.get_all_profiles()
        if not profiles:
            QMessageBox.information(self, "No Profiles", "No camera profiles are available. Create profiles first.")
            return
            
        # Open profile selection dialog
        dialog = ProfileManagerDialog(self, mode="select")
        
        # Override the window title for clarity
        dialog.setWindowTitle("Select Profile for Capture")
        
        # Connect to profile selected signal
        dialog.profile_selected.connect(self._on_profile_selected_for_capture)
        dialog.exec()
        
    def _on_profile_selected_for_capture(self, profile: CameraProfile):
        """Handle when a profile is selected for the capture workflow."""
        from profile_capture import ProfileCaptureManager
        
        # Get all connected camera ports
        connected_cameras = [port for port, widget in self.camera_widgets.items()
                           if widget.camera_info.status == "Connected"]
                           
        if not connected_cameras:
            QMessageBox.warning(self, "No Cameras", "No connected cameras to apply profile to.")
            return
            
        # Show the apply profile dialog
        camera_names = {port: widget.camera_info.model for port, widget in self.camera_widgets.items()}
        apply_dialog = ApplyProfileDialog(self, profile, connected_cameras, camera_names)
        
        # Update the dialog title to reflect it will capture afterwards
        apply_dialog.setWindowTitle(f"Apply Profile '{profile.name}' and Capture")
        
        if apply_dialog.exec() == QDialog.DialogCode.Accepted:
            selected_cameras = apply_dialog.get_selected_cameras()
            if not selected_cameras:
                return
                
            # Create the profile capture manager
            pcm = ProfileCaptureManager(self.camera_manager, self.format_organizer)
            
            # Process the capture with the profile
            self._update_status_bar(f"Applying profile '{profile.name}' and capturing...")
            
            # Disable UI elements during operation
            self.capture_all_button.setEnabled(False)
            
            # Show confirmation to user
            proceed = QMessageBox.question(
                self,
                "Confirm Profile Capture",
                f"Apply profile '{profile.name}' to {len(selected_cameras)} cameras and capture images?"
            )
            
            if proceed != QMessageBox.StandardButton.Yes:
                self.capture_all_button.setEnabled(True)
                self._update_status_bar("Profile capture canceled")
                return
            
            # Perform the operation in a background thread
            self._run_task(
                pcm.capture_with_profile,
                on_result_slot=self._on_profile_capture_completed,
                on_error_slot=self._on_worker_error,
                profile_name=profile.name,
                camera_ports=selected_cameras,
                save_dir=self.save_directory,
                prefix=self.filename_prefix
            )
    
    def _on_profile_capture_completed(self, results):
        """Handle completion of profile application and capture."""
        # Count successes 
        success_count = sum(1 for success, _ in results.values() if success)
        total_count = len(results)
        
        # Re-enable UI
        self.capture_all_button.setEnabled(True)
        
        # Update status
        if success_count == total_count:
            self._update_status_bar(f"Profile applied and captured successfully on all {success_count} cameras")
        else:
            self._update_status_bar(f"Profile capture completed: {success_count}/{total_count} successful")
            
        # Refresh widgets to show latest camera state
        for port in results.keys():
            self._refresh_widget_state(port)
    
    def _on_detect_task_finished(self):
        """Handle detect task completion."""
        self.detect_button.setEnabled(True)
        logging.debug("Detect task finished signal received.")
    
    def _on_detect_finished(self, detected_cameras_info: Dict[str, CameraInfo]):
        """Handle results of camera detection."""
        logging.info(f"Detection task result: {detected_cameras_info}")
        
        # Enable profile actions if we have cameras
        has_cameras = bool(detected_cameras_info)
        self.select_profile_action.setEnabled(has_cameras)
        self.profile_capture_action.setEnabled(has_cameras)
        
        # Update UI with detected cameras
        self._update_camera_widgets(detected_cameras_info)
        
        # Enable capture and preview buttons if we have cameras
        has_cameras = len(detected_cameras_info) > 0
        self.capture_all_button.setEnabled(has_cameras)
        self.toggle_preview_button.setEnabled(has_cameras)
        
        self._update_status_bar(f"Detected {len(detected_cameras_info)} cameras")
        
    def _on_force_mock_detection(self, mock_manager):
        """
        Force mock cameras to be added to the UI even if gphoto2 detection fails.
        This is useful in environments where gphoto2 can't properly detect devices.
        
        Args:
            mock_manager: The MockCameraManager instance
        """
        if not mock_manager or not hasattr(mock_manager, 'get_mock_cameras'):
            logging.error("Cannot force mock detection: invalid mock_manager")
            return
            
        mock_cameras = mock_manager.get_mock_cameras()
        if not mock_cameras:
            logging.error("No mock cameras available")
            return
            
        # Create CameraInfo objects for the mock cameras
        from camera_manager import CameraInfo, CameraSettings
        
        camera_info_dict = {}
        for port, mock_cam in mock_cameras.items():
            # Create a new CameraInfo object
            camera_info = CameraInfo(model=mock_cam.model, port=port, status="Connected")
            
            # Set up settings
            camera_info.settings.iso = mock_cam.iso
            camera_info.settings.aperture = mock_cam.aperture
            camera_info.settings.shutter_speed = mock_cam.shutter_speed
            
            # Set up choices
            camera_info.settings.iso_choices = mock_cam.iso_choices
            camera_info.settings.aperture_choices = mock_cam.aperture_choices
            camera_info.settings.shutter_speed_choices = mock_cam.shutter_speed_choices
            
            # Add to our cameras dictionary
            camera_info_dict[port] = camera_info
            
            # Add to camera_manager's cameras dictionary as well
            self.camera_manager.cameras[port] = camera_info
            
            logging.info(f"Added mock camera to UI: {mock_cam.model} at {port}")
        
        # Update the UI with the mock cameras
        if camera_info_dict:
            self._update_status_bar(f"Added {len(camera_info_dict)} mock cameras")
            self._update_camera_widgets(camera_info_dict)
            
            # Enable capture and preview buttons
            self.capture_all_button.setEnabled(True)
            self.toggle_preview_button.setEnabled(True)
            
            # Enable profile actions
            self.select_profile_action.setEnabled(True)
            self.profile_capture_action.setEnabled(True)
        else:
            self._update_status_bar("No mock cameras available")
            self._clear_camera_widgets()
    
    def _clear_camera_widgets(self):
        """Remove all camera widgets from the UI."""
        for port in list(self.camera_widgets.keys()):
            widget = self.camera_widgets.pop(port)
            # Disconnect signals to avoid memory leaks
            widget.capture_requested.disconnect()
            widget.setting_changed.disconnect()
            widget.retry_capture_requested.disconnect()
            widget.format_changed.disconnect()
            # Remove from layout
            self.camera_layout.removeWidget(widget)
            widget.deleteLater()
            
        logging.debug("Cleared all camera widgets")
    
    def _update_camera_widgets(self, current_cameras_state: Dict[str, CameraInfo]):
        """Update the camera widgets based on current camera state."""
        logging.debug(f"Updating camera widgets with state: {current_cameras_state}")
        
        # Get list of cameras that need to be removed (no longer present)
        ports_to_remove = [port for port in self.camera_widgets if port not in current_cameras_state]
        logging.debug(f"Clearing widgets for ports: {ports_to_remove}")
        
        # Remove widgets that are no longer needed
        for port in ports_to_remove:
            widget = self.camera_widgets.pop(port)
            widget.capture_requested.disconnect()
            widget.setting_changed.disconnect()
            widget.retry_capture_requested.disconnect()
            widget.format_changed.disconnect()
            self.camera_layout.removeWidget(widget)
            widget.deleteLater()
        
        # Now update or create widgets for current cameras
        if not current_cameras_state:
            # No cameras to display
            logging.info("No cameras connected or available to display.")
            placeholder = QLabel("No cameras detected. Click 'Detect Cameras' to scan for connected cameras.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("padding: 20px; color: #666;")
            self.camera_layout.addWidget(placeholder, 0, 0)
            return
            
        # Remove any existing placeholder
        for i in range(self.camera_layout.count()):
            item = self.camera_layout.itemAt(i)
            if item and isinstance(item.widget(), QLabel):
                self.camera_layout.removeItem(item)
                item.widget().deleteLater()
        
        # Update or create a widget for each camera
        row, col = 0, 0
        max_cols = 2  # Adjust based on your UI needs
        
        for port, camera_info in current_cameras_state.items():
            if port in self.camera_widgets:
                # Update existing widget
                widget = self.camera_widgets[port]
                widget.update_info(camera_info)
                logging.debug(f"Updating widget for {port} with status {camera_info.status}")
            else:
                # Create new widget
                widget = CameraControlWidget(camera_info)
                widget.capture_requested.connect(self._on_single_capture_requested)
                widget.setting_changed.connect(self._on_setting_change_requested)
                widget.retry_capture_requested.connect(self._on_retry_capture_requested)
                widget.format_changed.connect(self._on_format_change_requested)
                
                self.camera_widgets[port] = widget
                logging.debug(f"Creating/Updating widget for {port} with status {camera_info.status}")
                
                # Add to grid layout
                self.camera_layout.addWidget(widget, row, col)
                
                # Update grid position for next widget
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
    
    def _on_single_capture_requested(self, port: str):
        """Handle capture request from a single camera."""
        # Find the camera widget
        if port not in self.camera_widgets:
            logging.error(f"Cannot capture from unknown port: {port}")
            return
            
        widget = self.camera_widgets[port]
        camera_model = widget.camera_info.model
        
        logging.info(f"Capturing from camera at {port} ({camera_model})")
        self._update_status_bar(f"Capturing from {camera_model}...")
        
        # Run capture in background
        self._run_task(
            self.camera_manager.capture_image,
            on_result_slot=lambda filepath: self._on_single_capture_finished(port, filepath),
            on_error_slot=lambda error_tuple: self._on_single_capture_error(port, error_tuple),
            port=port,
            save_dir=self.save_directory,
            prefix=self.filename_prefix
        )
    
    def _on_retry_capture_requested(self, port: str):
        """Handle retry capture request."""
        self._on_single_capture_requested(port)
    
    def _on_single_capture_finished(self, port: str, filepath: Optional[str]):
        """Handle completion of single camera capture."""
        camera_name = self.camera_widgets[port].camera_info.model if port in self.camera_widgets else port
        
        if filepath:
            self.capture_results[port] = filepath
            success_message = f"Capture successful from {camera_name}: {os.path.basename(filepath)}"
            logging.info(success_message)
            self._update_status_bar(success_message)
            
            # Make sure the camera widget is updated with latest status
            self._refresh_widget_state(port)
        else:
            self.capture_results[port] = None
            error_message = f"Capture failed from {camera_name}"
            logging.error(error_message)
            self._update_status_bar(error_message)
            
            # Make sure the camera widget is updated with latest status
            self._refresh_widget_state(port)
        
        # If this was part of a "Capture All" operation, check if all captures are complete
        if len(self.capture_results) >= self._current_capture_all_expected_count:
            self._check_all_captures_done(self._current_capture_all_expected_count)
    
    def _on_single_capture_error(self, port: str, error_tuple):
        """Handle errors during single camera capture."""
        exctype, value, traceback_str = error_tuple
        camera_name = self.camera_widgets[port].camera_info.model if port in self.camera_widgets else port
        
        error_message = f"Capture error from {camera_name}: {value}"
        logging.error(f"{error_message}\n{traceback_str}")
        self._update_status_bar(error_message)
        
        # Record the failure for "Capture All" tracking
        self.capture_results[port] = None
        
        # Update the camera status
        self._refresh_widget_state(port)
        
        # If this was part of a "Capture All" operation, check if all captures are complete
        if len(self.capture_results) >= self._current_capture_all_expected_count:
            self._check_all_captures_done(self._current_capture_all_expected_count)
    
    def _check_all_captures_done(self, total_expected: int):
        """Check if all captures in a "Capture All" operation are complete."""
        if len(self.capture_results) < total_expected:
            return  # Still waiting for more results
            
        # Count successes
        success_count = sum(1 for filepath in self.capture_results.values() if filepath is not None)
        
        # Enable capture button again
        self.capture_all_button.setEnabled(True)
        
        if success_count == total_expected:
            self._update_status_bar(f"All {success_count} cameras captured successfully!")
        else:
            self._update_status_bar(f"Capture complete: {success_count}/{total_expected} successful")
            
        # Reset tracking
        self._current_capture_all_expected_count = 0
        self.capture_results = {}
    
    def _on_setting_change_requested(self, port: str, setting_type: str, value: str):
        """Handle camera setting change requests."""
        if port not in self.camera_widgets:
            logging.error(f"Cannot change settings for unknown port: {port}")
            return
            
        camera_name = self.camera_widgets[port].camera_info.model
        logging.info(f"Setting {setting_type} to {value} on {camera_name} ({port})")
        
        self._run_task(
            self.camera_manager.set_camera_setting,
            on_finish_slot=lambda: self._refresh_widget_state(port),
            port=port,
            setting_type=setting_type,
            value=value
        )
    
    def _on_format_change_requested(self, port: str, format_value: str):
        """Handle camera format change requests."""
        if port not in self.camera_widgets:
            return
            
        camera_name = self.camera_widgets[port].camera_info.model
        logging.info(f"Setting image format to {format_value} on {camera_name} ({port})")
        
        # In a real implementation, you would call your camera manager to set this
        # For now, we just log it
        self._update_status_bar(f"Set format {format_value} on {camera_name}")
    
    def _refresh_widget_state(self, port: str):
        """Refresh a camera widget with the latest camera state."""
        if port not in self.camera_widgets:
            return
            
        # Get the latest info from camera manager
        camera_info = self.camera_manager.cameras.get(port)
        if camera_info:
            self.camera_widgets[port].update_info(camera_info)
    
    def _request_previews(self):
        """Request preview images from all connected cameras."""
        connected_ports = [port for port, widget in self.camera_widgets.items()
                        if widget.camera_info.status == "Connected"]
                        
        if not connected_ports:
            return
            
        logging.debug(f"Requesting previews for ports: {connected_ports}")
        
        for port in connected_ports:
            self._run_task(
                self.camera_manager.capture_preview,
                on_result_slot=lambda image_data, port=port: self._on_preview_received(port, image_data),
                port=port
            )
    
    def _on_preview_received(self, port: str, image_data: Optional[bytes]):
        """Handle receipt of preview image data."""
        if port in self.camera_widgets:
            self.camera_widgets[port].update_preview(image_data)
    
    def closeEvent(self, event):
        """Handle application close event."""
        logging.info("Application closing")
        
        # Stop the preview timer if running
        if self.preview_timer.isActive():
            self.preview_timer.stop()
            
        # Wait for any remaining tasks to complete
        self.threadpool.waitForDone(2000)  # Wait up to 2 seconds
        
        # Accept the close event
        event.accept()