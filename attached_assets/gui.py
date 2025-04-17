# gui.py
import sys
import os
import logging
from typing import Optional, List, Dict, Tuple
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QFrame, QGridLayout, QComboBox, QTextEdit, QMessageBox, QSizePolicy, QApplication,
    QFileDialog, QLineEdit # Added for directory/prefix
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QThreadPool
from PyQt6.QtGui import QPixmap, QImage, QPalette, QColor, QTextCursor

from camera_manager import CameraManager, CameraInfo, CameraSettings
from worker import Worker
from logger_setup import QTextEditLogHandler

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

# --- Camera Control Widget ---
class CameraControlWidget(QFrame):
    """Widget to display controls for a single camera."""
    capture_requested = pyqtSignal(str)
    setting_changed = pyqtSignal(str, str, str)
    retry_capture_requested = pyqtSignal(str)

    def __init__(self, camera_info: CameraInfo, parent=None):
        super().__init__(parent)
        self.port = camera_info.port
        self.camera_info = camera_info
        self.setFrameShape(QFrame.Shape.StyledPanel); self.setMinimumWidth(300)
        layout = QVBoxLayout(self); layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(6)

        # Header
        header_layout = QHBoxLayout()
        self.name_label = QLabel(f"<b>{camera_info.model}</b><br/>({camera_info.port})"); self.name_label.setWordWrap(True)
        self.status_label = QLabel(f"Status: {camera_info.status}"); self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        header_layout.addWidget(self.name_label); header_layout.addWidget(self.status_label); layout.addLayout(header_layout)

        # Preview
        self.preview_label = QLabel(f"Preview N/A\n{self.port}"); self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(160, 120); self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setStyleSheet(STYLE_PREVIEW_DISCONNECTED); self._load_placeholder_image(); layout.addWidget(self.preview_label)

        # Settings
        settings_layout = QGridLayout(); settings_layout.setColumnStretch(1, 1); settings_layout.setHorizontalSpacing(10); settings_layout.setVerticalSpacing(5)
        settings_layout.addWidget(QLabel("ISO:"), 0, 0); self.iso_combo = QComboBox(); self.iso_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.iso_combo.currentTextChanged.connect(lambda v: self._on_setting_change("iso", v)); settings_layout.addWidget(self.iso_combo, 0, 1)
        settings_layout.addWidget(QLabel("Aperture:"), 1, 0); self.aperture_combo = QComboBox(); self.aperture_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.aperture_combo.currentTextChanged.connect(lambda v: self._on_setting_change("aperture", v)); settings_layout.addWidget(self.aperture_combo, 1, 1)
        settings_layout.addWidget(QLabel("Shutter Spd:"), 2, 0); self.shutter_combo = QComboBox(); self.shutter_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.shutter_combo.currentTextChanged.connect(lambda v: self._on_setting_change("shutterspeed", v)); settings_layout.addWidget(self.shutter_combo, 2, 1)
        layout.addLayout(settings_layout)

        # Action Buttons
        action_layout = QHBoxLayout()
        self.capture_button = QPushButton("Capture"); self.capture_button.clicked.connect(self._emit_capture_request)
        self.retry_button = QPushButton("Retry"); self.retry_button.clicked.connect(self._emit_retry_request)
        self.retry_button.setVisible(False); self.retry_button.setStyleSheet("background-color: orange; color: black;")
        action_layout.addStretch(); action_layout.addWidget(self.retry_button); action_layout.addWidget(self.capture_button); layout.addLayout(action_layout)

        # Error Display
        self.error_label = QLabel(""); self.error_label.setStyleSheet("color: red; padding-top: 5px;"); self.error_label.setWordWrap(True); self.error_label.setVisible(False); layout.addWidget(self.error_label)
        self.update_info(camera_info) # Initial population

    def _load_placeholder_image(self):
        if os.path.exists(PLACEHOLDER_IMAGE_PATH):
             pixmap = QPixmap(PLACEHOLDER_IMAGE_PATH)
             scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
             self.preview_label.setPixmap(scaled_pixmap)
        else: self.preview_label.setText(f"Preview N/A\n{self.port}")

    def _emit_capture_request(self): self.capture_requested.emit(self.port)
    def _emit_retry_request(self): self.retry_capture_requested.emit(self.port); self.retry_button.setVisible(False)
    def _on_setting_change(self, setting_type: str, value: str):
        sender_combo = self.sender()
        if sender_combo and sender_combo.isEnabled() and value:
             logging.debug(f"GUI Change: Port {self.port}, Setting {setting_type}, Value {value}")
             self.setting_changed.emit(self.port, setting_type, value)

    def update_info(self, camera_info: CameraInfo):
        self.camera_info = camera_info; status = camera_info.status; self.status_label.setText(f"Status: {status}")
        is_ready = status == "Connected"; is_busy = status in ["Capturing...", "Previewing...", "Connecting...", "Fetching Settings...", "Applying Settings..."]; is_error = status == "Error"

        if is_ready:
            self.status_label.setStyleSheet(STYLE_STATUS_CONNECTED); self.preview_label.setStyleSheet(STYLE_PREVIEW_CONNECTED)
            self.capture_button.setEnabled(True); self.retry_button.setVisible(False); self.error_label.setVisible(False)
            self._set_controls_enabled(True)
        elif is_busy:
            self.status_label.setStyleSheet(STYLE_STATUS_BUSY); self.preview_label.setStyleSheet(STYLE_PREVIEW_BUSY)
            self.capture_button.setEnabled(False); self.retry_button.setVisible(False); self.error_label.setVisible(False)
            self._set_controls_enabled(False)
        elif is_error:
            self.status_label.setStyleSheet(STYLE_STATUS_ERROR); self.preview_label.setStyleSheet(STYLE_PREVIEW_ERROR)
            self.capture_button.setEnabled(True); self.retry_button.setVisible(True); self.error_label.setText(f"Last Error: {camera_info.last_error or 'Unknown'}"); self.error_label.setVisible(True)
            self._set_controls_enabled(True)
        else: # Disconnected or other
            self.status_label.setStyleSheet(STYLE_STATUS_DISCONNECTED); self.preview_label.setStyleSheet(STYLE_PREVIEW_DISCONNECTED)
            self.capture_button.setEnabled(False); self.retry_button.setVisible(False); self.error_label.setVisible(False)
            self._set_controls_enabled(False); self._load_placeholder_image()

        self._update_combo(self.iso_combo, camera_info.settings.iso, camera_info.settings.iso_choices)
        self._update_combo(self.aperture_combo, camera_info.settings.aperture, camera_info.settings.aperture_choices)
        self._update_combo(self.shutter_combo, camera_info.settings.shutter_speed, camera_info.settings.shutter_speed_choices)

    def _set_controls_enabled(self, enabled: bool):
         self._enable_combo_if_valid(self.iso_combo, enabled); self._enable_combo_if_valid(self.aperture_combo, enabled); self._enable_combo_if_valid(self.shutter_combo, enabled)
    def _enable_combo_if_valid(self, combo: QComboBox, parent_enabled: bool):
        has_valid_items = combo.count() > 0 and combo.itemText(0) not in ["N/A", "Error", "Unknown", "Parse Error"]
        combo.setEnabled(parent_enabled and has_valid_items)
    def _update_combo(self, combo: QComboBox, current_value: Optional[str], choices: List[str]):
        was_blocked = combo.blockSignals(True); stored_current_text = combo.currentText(); combo.clear()
        parent_allows_enable = combo.isEnabled(); valid_value = current_value and current_value not in ["Error", "Unknown", "N/A", "Parse Error"]
        if choices:
            combo.addItems(choices)
            if valid_value and current_value in choices: combo.setCurrentText(current_value)
            elif stored_current_text in choices: combo.setCurrentText(stored_current_text)
            elif choices: combo.setCurrentIndex(0)
            combo.setEnabled(parent_allows_enable and True)
        elif valid_value:
            combo.addItem(current_value); combo.setCurrentIndex(0); combo.setEnabled(parent_allows_enable and True)
        else: combo.addItem(current_value or "N/A"); combo.setEnabled(False)
        combo.blockSignals(was_blocked)

    def update_preview(self, image_data: Optional[bytes]):
        if image_data:
            try:
                qimage = QImage.fromData(image_data)
                if not qimage.isNull():
                    pixmap = QPixmap.fromImage(qimage)
                    scaled_pixmap = pixmap.scaled(self.preview_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.preview_label.setPixmap(scaled_pixmap)
                else: self.preview_label.setText(f"Preview Error\nInvalid Data\n{self.port}"); logging.warning(f"Invalid image data for {self.port}")
            except Exception as e: self.preview_label.setText(f"Preview Error\nLoad Failed\n{self.port}"); logging.error(f"Error loading preview for {self.port}: {e}")
        else: self._load_placeholder_image()

# --- Main Window ---
class MainWindow(QWidget):
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt Multi-Camera Control"); self.setGeometry(100, 100, 1000, 750)
        self.camera_manager = CameraManager(); self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(max(4, QThreadPool.globalInstance().maxThreadCount())); logging.info(f"Thread pool max threads: {self.threadpool.maxThreadCount()}")
        self.camera_widgets: Dict[str, CameraControlWidget] = {}
        self.capture_results: Dict[str, Optional[str]] = {}
        self._current_capture_all_expected_count = 0 # For tracking Capture All
        self.save_directory = os.path.abspath(CAPTURE_DIR) # Initialize save dir
        self.filename_prefix = "" # Initialize prefix

        self.log_text_edit = QTextEdit(); self.log_text_edit.setReadOnly(True); self.log_text_edit.setMaximumHeight(150); self.log_text_edit.setStyleSheet("background-color: #f0f0f0;")
        self._setup_gui_logging()
        self._init_ui()
        self.preview_timer = QTimer(self); self.preview_timer.timeout.connect(self._request_previews)
        self._update_status_bar("Starting initial detection..."); self._run_task(self.camera_manager.detect_cameras, on_result_slot=self._on_detect_finished, on_finish_slot=self._on_detect_task_finished)
        self.detect_button.setEnabled(False)

    def _init_ui(self):
        main_layout = QVBoxLayout(self); main_layout.setSpacing(10)

        # Top Controls
        top_layout = QHBoxLayout()
        self.detect_button = QPushButton("Detect Cameras"); self.detect_button.clicked.connect(self._on_detect_clicked)
        self.capture_all_button = QPushButton("Capture All"); self.capture_all_button.clicked.connect(self._on_capture_all_clicked); self.capture_all_button.setEnabled(False)
        self.toggle_preview_button = QPushButton("Start Previews"); self.toggle_preview_button.setCheckable(True); self.toggle_preview_button.toggled.connect(self._on_toggle_previews); self.toggle_preview_button.setEnabled(False)
        top_layout.addWidget(self.detect_button); top_layout.addWidget(self.capture_all_button); top_layout.addWidget(self.toggle_preview_button); top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # --- Save Options ---
        save_options_layout = QHBoxLayout()
        self.choose_dir_button = QPushButton("Choose Save Directory")
        self.choose_dir_button.clicked.connect(self._choose_save_directory)
        self.save_dir_label = QLabel(f"Save Dir: {self.save_directory}") # Display current dir
        self.save_dir_label.setToolTip(self.save_directory) # Show full path on hover
        self.save_dir_label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred) # Allow shrinking/expanding a bit
        self.save_dir_label.setWordWrap(False) # Keep on one line unless very long

        prefix_label = QLabel("Filename Prefix:")
        self.prefix_edit = QLineEdit(self.filename_prefix)
        self.prefix_edit.setPlaceholderText("Optional prefix...")
        self.prefix_edit.setFixedWidth(150) # Limit width of prefix input
        self.prefix_edit.textChanged.connect(self._update_filename_prefix) # Update internal state on change

        save_options_layout.addWidget(self.choose_dir_button)
        save_options_layout.addWidget(self.save_dir_label)
        save_options_layout.addStretch() # Push prefix to the right
        save_options_layout.addWidget(prefix_label)
        save_options_layout.addWidget(self.prefix_edit)
        main_layout.addLayout(save_options_layout)

        # Status Bar
        self.status_bar = QLabel("Status: Initializing..."); self.status_bar.setStyleSheet("padding: 3px; background-color: #e8e8e8; border: 1px solid #c0c0c0; border-radius: 3px;")
        main_layout.addWidget(self.status_bar)

        # Camera Controls Area
        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True); self.scroll_area.setStyleSheet("background-color: #ffffff;")
        self.scroll_content_widget = QWidget()
        self.camera_grid_layout = QGridLayout(self.scroll_content_widget); self.camera_grid_layout.setSpacing(15); self.camera_grid_layout.setContentsMargins(10, 10, 10, 10); self.camera_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_content_widget.setLayout(self.camera_grid_layout); self.scroll_area.setWidget(self.scroll_content_widget); main_layout.addWidget(self.scroll_area)

        # Log Area
        log_label = QLabel("Logs:"); log_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        main_layout.addWidget(log_label); main_layout.addWidget(self.log_text_edit)

    def _setup_gui_logging(self):
        log_handler = QTextEditLogHandler(self.log_signal)
        log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s'))
        logging.getLogger().addHandler(log_handler); self.log_signal.connect(self._append_log_message)
    def _append_log_message(self, message):
        self.log_text_edit.moveCursor(QTextCursor.MoveOperation.End); self.log_text_edit.insertPlainText(message + '\n'); self.log_text_edit.moveCursor(QTextCursor.MoveOperation.End)
    def _update_status_bar(self, message: str): self.status_bar.setText(f"Status: {message}")
    def _run_task(self, func, on_finish_slot=None, on_error_slot=None, on_result_slot=None, *args, **kwargs):
        worker = Worker(func, *args, **kwargs)
        if on_finish_slot: worker.signals.finished.connect(on_finish_slot)
        if on_error_slot: worker.signals.error.connect(on_error_slot)
        else: worker.signals.error.connect(self._on_worker_error) # Default error handler
        if on_result_slot: worker.signals.result.connect(on_result_slot)
        worker.signals.status_update.connect(self._update_status_bar)
        self.threadpool.start(worker)
    def _on_worker_error(self, error_tuple):
        exctype, value, tb_str = error_tuple
        logging.error(f"Unhandled Worker Error: {exctype.__name__}: {value}\n{tb_str}")
        QMessageBox.warning(self, "Worker Error", f"An background task failed:\n{exctype.__name__}: {value}")
        self.detect_button.setEnabled(True) # Ensure detect button is always usable after error
        any_connected = any(c.status == "Connected" for c in self.camera_manager.cameras.values())
        self.capture_all_button.setEnabled(any_connected)
        self._update_status_bar(f"Error occurred: {value}")

    # --- New Save Option Handlers ---
    def _choose_save_directory(self):
        """Opens a dialog to choose the save directory."""
        chosen_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Save Directory",
            self.save_directory, # Start in the current directory
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )
        if chosen_dir: # User didn't cancel
            self.save_directory = os.path.normpath(chosen_dir)
            logging.info(f"Save directory changed to: {self.save_directory}")
            # Update label - shorten path if too long for display
            display_path = self.save_directory
            if len(display_path) > 50: # Arbitrary length limit
                display_path = "..." + display_path[-47:]
            self.save_dir_label.setText(f"Save Dir: {display_path}")
            self.save_dir_label.setToolTip(self.save_directory) # Update tooltip with full path

    def _update_filename_prefix(self, text):
        """Updates the internal filename prefix state."""
        # Optional: Add validation here (e.g., allow only alphanumeric, _, -)
        self.filename_prefix = text.strip()
        logging.debug(f"Filename prefix changed to: '{self.filename_prefix}'")

    # --- Button Click Handlers ---
    def _on_detect_clicked(self):
        self._update_status_bar("Detecting cameras..."); self.detect_button.setEnabled(False); self.capture_all_button.setEnabled(False); self.toggle_preview_button.setEnabled(False)
        if self.preview_timer.isActive(): self.toggle_preview_button.setChecked(False)
        self._clear_camera_widgets(); self._run_task(self.camera_manager.detect_cameras, on_result_slot=self._on_detect_finished, on_finish_slot=self._on_detect_task_finished)

    def _on_capture_all_clicked(self):
        connected_cameras = self.camera_manager.get_connected_cameras()
        if not connected_cameras: QMessageBox.information(self, "Capture All", "No connected cameras found."); return

        num_cameras = len(connected_cameras); self.capture_all_button.setEnabled(False)
        for widget in self.camera_widgets.values(): widget.capture_button.setEnabled(False) # Disable individual buttons
        self._update_status_bar(f"Initiating capture for {num_cameras} cameras..."); logging.info(f"Capture All triggered for {num_cameras} cameras.")

        self._current_capture_all_expected_count = num_cameras # Store expected count
        self.capture_results = {} # Reset results tracker

        current_save_dir = self.save_directory # Use current settings
        current_prefix = self.filename_prefix

        for cam_info in connected_cameras:
             self._run_task(
                 self.camera_manager.capture_image,
                 on_result_slot=lambda result, p=cam_info.port: self._on_single_capture_finished(p, result),
                 on_error_slot=lambda error, p=cam_info.port: self._on_single_capture_error(p, error),
                 # Removed finish slot connection for check - check happens in result/error slots
                 port=cam_info.port,
                 save_dir=current_save_dir, # Pass save dir
                 prefix=current_prefix # Pass prefix
             )

    def _on_toggle_previews(self, checked):
         if checked:
             self.preview_timer.start(PREVIEW_REFRESH_INTERVAL); self.toggle_preview_button.setText("Stop Previews"); logging.info("Started preview updates.")
             self._request_previews()
         else:
             self.preview_timer.stop(); self.toggle_preview_button.setText("Start Previews"); logging.info("Stopped preview updates.")
             for widget in self.camera_widgets.values(): widget.update_preview(None)

    # --- Task Completion Handlers ---
    def _on_detect_task_finished(self):
        self.detect_button.setEnabled(True); logging.debug("Detect task finished signal received.")
    def _on_detect_finished(self, detected_cameras_info: Dict[str, CameraInfo]):
        num_detected = len(detected_cameras_info)
        current_manager_state = self.camera_manager.cameras
        num_connected = sum(1 for c in current_manager_state.values() if c.status == "Connected")
        num_error = sum(1 for c in current_manager_state.values() if c.status == "Error")
        self._update_status_bar(f"Detection complete. Connected: {num_connected}, Errors: {num_error}, Total Found: {num_detected}.")
        logging.info(f"Detection task result: {detected_cameras_info}")
        self._update_camera_widgets(current_manager_state)
        any_connected = num_connected > 0
        self.capture_all_button.setEnabled(any_connected); self.toggle_preview_button.setEnabled(any_connected)

    def _clear_camera_widgets(self):
        ports_to_clear = list(self.camera_widgets.keys()); logging.debug(f"Clearing widgets for ports: {ports_to_clear}")
        for port in ports_to_clear:
            widget = self.camera_widgets.pop(port, None)
            if widget:
                self.camera_grid_layout.removeWidget(widget)
                try: widget.capture_requested.disconnect()
                except TypeError: pass
                try: widget.setting_changed.disconnect()
                except TypeError: pass
                try: widget.retry_capture_requested.disconnect()
                except TypeError: pass
                widget.deleteLater(); logging.debug(f"Removed and scheduled deletion for widget {port}")
        while self.camera_grid_layout.count(): # Clear any remaining items (like placeholder label)
            item = self.camera_grid_layout.takeAt(0)
            if item: widget = item.widget(); widget.deleteLater() if widget else None

    def _update_camera_widgets(self, current_cameras_state: Dict[str, CameraInfo]):
        logging.debug(f"Updating camera widgets with state: {current_cameras_state}")
        self._clear_camera_widgets()
        MAX_COLS = 3; row, col = 0, 0; displayed_widgets = 0
        sorted_ports = sorted(list(current_cameras_state.keys()))

        for port in sorted_ports:
            cam_info = current_cameras_state[port]
            if cam_info.status == "Disconnected": continue # Skip disconnected
            logging.debug(f"Creating/Updating widget for {port} with status {cam_info.status}")
            widget = CameraControlWidget(cam_info)
            widget.capture_requested.connect(self._on_single_capture_requested)
            widget.setting_changed.connect(self._on_setting_change_requested)
            widget.retry_capture_requested.connect(self._on_retry_capture_requested)
            self.camera_widgets[port] = widget; self.camera_grid_layout.addWidget(widget, row, col); displayed_widgets += 1
            col += 1;
            if col >= MAX_COLS: col = 0; row += 1

        if displayed_widgets == 0:
             logging.info("No cameras connected or available to display.")
             empty_label = QLabel("No cameras connected or detected successfully."); empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter); empty_label.setStyleSheet("font-style: italic; color: gray;")
             self.camera_grid_layout.addWidget(empty_label, 0, 0, 1, MAX_COLS)

        self.scroll_content_widget.adjustSize()
        any_connected = any(c.status == "Connected" for c in current_cameras_state.values())
        self.capture_all_button.setEnabled(any_connected); self.toggle_preview_button.setEnabled(any_connected)

    def _on_single_capture_requested(self, port: str):
        logging.info(f"Single capture requested for {port}")
        if port in self.camera_widgets and self.camera_manager.cameras.get(port):
            self.camera_widgets[port].capture_button.setEnabled(False); QApplication.processEvents()
            current_save_dir = self.save_directory # Use current settings
            current_prefix = self.filename_prefix
            self._run_task(
                 self.camera_manager.capture_image,
                 on_result_slot=lambda result, p=port: self._on_single_capture_finished(p, result),
                 on_error_slot=lambda error, p=port: self._on_single_capture_error(p, error),
                 on_finish_slot=lambda p=port: self._refresh_widget_state(p),
                 port=port, save_dir=current_save_dir, prefix=current_prefix
            )
        else: logging.warning(f"Capture requested for unknown/disconnected port: {port}")

    def _on_retry_capture_requested(self, port:str):
        logging.info(f"Retry capture requested for {port}")
        if port in self.camera_widgets:
             self.camera_widgets[port].retry_button.setVisible(False); self.camera_widgets[port].error_label.setVisible(False)
        self._on_single_capture_requested(port)

    def _on_single_capture_finished(self, port: str, filepath: Optional[str]):
        logging.info(f"Capture task result signal received for {port}. Result: {filepath}")
        is_capture_all = hasattr(self, '_current_capture_all_expected_count') and self._current_capture_all_expected_count > 0
        if is_capture_all and port in self.capture_results:
             self.capture_results[port] = filepath
             logging.debug(f"Stored capture result for {port}. Current count: {len(self.capture_results)}")
        self._refresh_widget_state(port) # Refresh UI based on manager's state
        if is_capture_all: self._check_all_captures_done(self._current_capture_all_expected_count) # Check completion

    def _on_single_capture_error(self, port: str, error_tuple):
        exctype, value, tb = error_tuple
        logging.error(f"Capture worker task EXCEPTION for {port}: {exctype.__name__}: {value}\n{tb}")
        if port in self.camera_manager.cameras:
            self.camera_manager.cameras[port].status = "Error"; self.camera_manager.cameras[port].last_error = f"Worker Exception: {value}"
        is_capture_all = hasattr(self, '_current_capture_all_expected_count') and self._current_capture_all_expected_count > 0
        if is_capture_all and port in self.capture_results:
             self.capture_results[port] = None
             logging.debug(f"Stored capture error for {port}. Current count: {len(self.capture_results)}")
        self._refresh_widget_state(port) # Refresh UI
        if is_capture_all: self._check_all_captures_done(self._current_capture_all_expected_count) # Check completion

    def _check_all_captures_done(self, total_expected: int):
        logging.debug(f"_check_all_captures_done called. Expected: {total_expected}, Current results count: {len(self.capture_results)}")
        if len(self.capture_results) >= total_expected:
            logging.info(f"All {total_expected} capture tasks for 'Capture All' appear complete. Triggering pop-up.")
            success_count = sum(1 for path in self.capture_results.values() if path is not None)
            fail_count = total_expected - success_count
            msg = f"Capture All finished. Success: {success_count}, Failed: {fail_count}."
            self._update_status_bar(msg)
            if total_expected > 0: QMessageBox.information(self, "Capture All Complete", msg)
            any_connected = any(c.status == "Connected" for c in self.camera_manager.cameras.values())
            self.capture_all_button.setEnabled(any_connected)
            for port, widget in self.camera_widgets.items():
                 if widget and self.camera_manager.cameras.get(port, CameraInfo("",port,"Disconnected")).status == "Connected":
                     widget.capture_button.setEnabled(True)
            self.capture_results = {} # Reset tracker
            self._current_capture_all_expected_count = 0 # Reset expected count
        else: logging.debug(f"Not all tasks finished yet ({len(self.capture_results)}/{total_expected}). Waiting...")

    def _on_setting_change_requested(self, port: str, setting_type: str, value: str):
        logging.info(f"Setting change requested: Port={port}, Setting={setting_type}, Value={value}")
        if port in self.camera_widgets and self.camera_manager.cameras.get(port):
            widget = self.camera_widgets[port]; widget._set_controls_enabled(False); QApplication.processEvents()
            self._run_task(
                self.camera_manager.set_camera_setting,
                on_finish_slot=lambda p=port: self._refresh_widget_state(p),
                port=port, setting_type=setting_type, value=value
            )
        else: logging.warning(f"Setting change requested for unknown/disconnected port: {port}")

    def _refresh_widget_state(self, port: str):
        if port in self.camera_manager.cameras and port in self.camera_widgets:
            cam_info = self.camera_manager.cameras[port]
            self.camera_widgets[port].update_info(cam_info)
            logging.debug(f"Refreshed widget state for {port} to status {cam_info.status}")
        else: logging.warning(f"Attempted to refresh widget for unknown/removed port: {port}")
        any_connected = any(c.status == "Connected" for c in self.camera_manager.cameras.values())
        self.capture_all_button.setEnabled(any_connected); self.toggle_preview_button.setEnabled(any_connected)

    # --- Preview Handling ---
    def _request_previews(self):
        if not self.preview_timer.isActive(): return
        eligible_ports = [p for p, cam in self.camera_manager.cameras.items() if cam.status == "Connected"]
        if not eligible_ports: return
        logging.debug(f"Requesting previews for ports: {eligible_ports}")
        for port in eligible_ports:
             self._run_task(self.camera_manager.capture_preview, on_result_slot=lambda result, p=port: self._on_preview_received(p, result), port=port)
    def _on_preview_received(self, port: str, image_data: Optional[bytes]):
        if port in self.camera_widgets: self.camera_widgets[port].update_preview(image_data)

    def closeEvent(self, event):
        logging.info("Close event received. Shutting down..."); self.preview_timer.stop(); self.threadpool.clear()
        if not self.threadpool.waitForDone(2000): logging.warning("Thread pool did not finish tasks gracefully within timeout.")
        logging.shutdown(); event.accept()