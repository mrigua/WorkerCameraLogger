#!/usr/bin/env python3
# tethered_ui.py - UI components for tethered shooting

import os
import logging
from typing import Dict, List, Optional, Union, Tuple
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QFrame, QSplitter, QScrollArea, QListWidget, QListWidgetItem, QFileDialog,
    QGridLayout, QGroupBox, QComboBox, QSpinBox, QToolButton, QMenu,
    QMessageBox, QSizePolicy, QProgressBar, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QThread
from PyQt6.QtGui import QPixmap, QImage, QIcon, QColor, QPalette, QFont, QAction

try:
    from tethered_shooting import TetheredShootingManager, TetheredEvent
    from mock_tethered_shooting import MockTetheredShootingManager
except ImportError:
    from attached_assets.tethered_shooting import TetheredShootingManager, TetheredEvent
    from attached_assets.mock_tethered_shooting import MockTetheredShootingManager


class ImageThumbnailWidget(QFrame):
    """Widget for displaying an image thumbnail with metadata."""
    
    clicked = pyqtSignal(str)  # Emits the file path
    
    def __init__(self, file_path: str, camera_port: str = "", parent=None):
        super().__init__(parent)
        
        self.file_path = file_path
        self.camera_port = camera_port
        
        # Configure frame
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setMinimumSize(180, 180)
        self.setMaximumSize(250, 240)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # Image preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        self.image_label.setMinimumSize(160, 120)
        
        # Set up initial image or placeholder
        self._load_image()
        
        # File info label
        self.info_label = QLabel(os.path.basename(file_path))
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        
        # Time label
        self.time_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add to layout
        layout.addWidget(self.image_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.time_label)
        
        # Enable mouse tracking
        self.setMouseTracking(True)
    
    def _load_image(self):
        """Load the image file or display a placeholder."""
        try:
            if os.path.exists(self.file_path):
                pixmap = QPixmap(self.file_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        160, 120,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled_pixmap)
                    return
            
            # Display placeholder if unable to load
            self.image_label.setText("No Preview")
            self.image_label.setStyleSheet("background-color: #444; color: white;")
        
        except Exception as e:
            logging.error(f"Error loading thumbnail for {self.file_path}: {e}")
            self.image_label.setText("Error")
            self.image_label.setStyleSheet("background-color: #700; color: white;")
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        self.clicked.emit(self.file_path)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Handle mouse enter events."""
        self.setStyleSheet("background-color: #3498db; color: white;")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        self.setStyleSheet("")
        super().leaveEvent(event)


class TetheredCameraPanel(QFrame):
    """Panel for controlling a tethered camera and viewing its captures."""
    
    start_tethering_signal = pyqtSignal(str)  # Emits camera port
    stop_tethering_signal = pyqtSignal(str)   # Emits camera port
    capture_requested = pyqtSignal(str)       # Emits camera port
    image_selected = pyqtSignal(str)          # Emits file path
    
    def __init__(self, camera_port: str, camera_name: str, parent=None):
        super().__init__(parent)
        
        self.camera_port = camera_port
        self.camera_name = camera_name
        self.is_tethering = False
        self.downloaded_files: List[str] = []
        
        # Create main layout
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Camera info header
        header_layout = QHBoxLayout()
        
        self.title_label = QLabel(f"<b>{camera_name}</b>")
        self.title_label.setFont(QFont("Arial", 12))
        
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: gray; font-size: 16px;")
        self.status_indicator.setFixedWidth(20)
        
        self.status_label = QLabel("Not Tethered")
        
        header_layout.addWidget(self.status_indicator)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        
        main_layout.addLayout(header_layout)
        
        # Control buttons
        controls_layout = QHBoxLayout()
        
        self.tether_button = QPushButton("Start Tethering")
        self.tether_button.clicked.connect(self._on_tether_button_clicked)
        
        self.capture_button = QPushButton("Capture")
        self.capture_button.setEnabled(False)
        self.capture_button.clicked.connect(self._on_capture_clicked)
        
        self.auto_capture_button = QPushButton("Auto Capture")
        self.auto_capture_button.setEnabled(False)
        # This will be connected externally to the auto-capture dialog
        
        controls_layout.addWidget(self.tether_button)
        controls_layout.addWidget(self.capture_button)
        controls_layout.addWidget(self.auto_capture_button)
        
        main_layout.addLayout(controls_layout)
        
        # Recent captures area
        captures_group = QGroupBox("Recent Captures")
        captures_layout = QVBoxLayout(captures_group)
        
        self.thumbnails_scroll = QScrollArea()
        self.thumbnails_scroll.setWidgetResizable(True)
        self.thumbnails_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumbnails_scroll.setMinimumHeight(200)
        
        self.thumbnails_container = QWidget()
        self.thumbnails_layout = QHBoxLayout(self.thumbnails_container)
        self.thumbnails_layout.setContentsMargins(5, 5, 5, 5)
        self.thumbnails_layout.setSpacing(10)
        self.thumbnails_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.thumbnails_scroll.setWidget(self.thumbnails_container)
        captures_layout.addWidget(self.thumbnails_scroll)
        
        # No images message
        self.no_images_label = QLabel("No captured images yet. Start tethering and take photos with your camera.")
        self.no_images_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_images_label.setStyleSheet("color: #777;")
        self.thumbnails_layout.addWidget(self.no_images_label)
        
        main_layout.addWidget(captures_group)
    
    def _on_tether_button_clicked(self):
        """Handle tether button clicks."""
        if not self.is_tethering:
            self.start_tethering_signal.emit(self.camera_port)
        else:
            self.stop_tethering_signal.emit(self.camera_port)
    
    def _on_capture_clicked(self):
        """Handle capture button clicks."""
        self.capture_requested.emit(self.camera_port)
    
    def set_tethering_state(self, active: bool, busy: bool = False):
        """Update UI to reflect tethering state."""
        self.is_tethering = active
        
        if active:
            self.tether_button.setText("Stop Tethering")
            self.capture_button.setEnabled(not busy)
            self.auto_capture_button.setEnabled(not busy)
            
            if busy:
                self.status_indicator.setStyleSheet("color: #f39c12; font-size: 16px;")  # Orange for busy
                self.status_label.setText("Busy")
            else:
                self.status_indicator.setStyleSheet("color: #2ecc71; font-size: 16px;")  # Green for active
                self.status_label.setText("Tethered")
        else:
            self.tether_button.setText("Start Tethering")
            self.capture_button.setEnabled(False)
            self.auto_capture_button.setEnabled(False)
            self.status_indicator.setStyleSheet("color: gray; font-size: 16px;")
            self.status_label.setText("Not Tethered")
    
    def set_error_state(self, error_message: str):
        """Set panel to error state with message."""
        self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px;")  # Red for error
        self.status_label.setText("Error")
        self.tether_button.setText("Start Tethering")
        self.capture_button.setEnabled(False)
        self.auto_capture_button.setEnabled(False)
        
        # Show error message
        QMessageBox.warning(self, "Tethering Error", f"Error: {error_message}")
    
    def add_captured_image(self, file_path: str):
        """Add a captured image to the panel."""
        # Remove the "no images" label if it exists
        if self.no_images_label.isVisible():
            self.no_images_label.setVisible(False)
        
        # Create thumbnail widget
        thumbnail = ImageThumbnailWidget(file_path, self.camera_port)
        thumbnail.clicked.connect(self.image_selected.emit)
        
        # Add to the start of the layout
        self.thumbnails_layout.insertWidget(0, thumbnail)
        
        # Add to downloaded files list
        self.downloaded_files.append(file_path)
        
        # Limit the number of thumbnails to the most recent 10
        if self.thumbnails_layout.count() > 10:
            # Remove the oldest thumbnail
            item = self.thumbnails_layout.takeAt(self.thumbnails_layout.count() - 1)
            if item and item.widget():
                item.widget().deleteLater()
    
    def clear_captured_images(self):
        """Clear all captured images from the panel."""
        # Remove all thumbnails
        while self.thumbnails_layout.count() > 0:
            item = self.thumbnails_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        
        # Show the "no images" label
        self.no_images_label.setVisible(True)
        self.thumbnails_layout.addWidget(self.no_images_label)
        
        # Clear downloaded files list
        self.downloaded_files = []


class CameraCaptureView(QFrame):
    """Main widget showing current capture from a tethered camera."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_image_path = None
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Image display
        self.image_label = QLabel("No image selected")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #222; color: white;")
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Info panel
        info_panel = QFrame()
        info_panel.setFrameShape(QFrame.Shape.StyledPanel)
        info_panel.setMaximumHeight(80)
        info_layout = QVBoxLayout(info_panel)
        
        self.filename_label = QLabel("No file selected")
        self.metadata_label = QLabel("")
        
        info_layout.addWidget(self.filename_label)
        info_layout.addWidget(self.metadata_label)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self._on_open_folder_clicked)
        
        self.open_file_button = QPushButton("Open File")
        self.open_file_button.setEnabled(False)
        self.open_file_button.clicked.connect(self._on_open_file_clicked)
        
        button_layout.addWidget(self.open_folder_button)
        button_layout.addWidget(self.open_file_button)
        button_layout.addStretch()
        
        info_layout.addLayout(button_layout)
        
        # Add to main layout
        layout.addWidget(self.image_label, 1)
        layout.addWidget(info_panel)
    
    def load_image(self, file_path: str):
        """Load and display an image file."""
        if not file_path or not os.path.exists(file_path):
            self._show_placeholder()
            return False
        
        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self._show_placeholder()
                return False
            
            # Update current image path
            self.current_image_path = file_path
            
            # Scale pixmap while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.image_label.width(),
                self.image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            # Set the pixmap
            self.image_label.setPixmap(scaled_pixmap)
            
            # Update info
            self.filename_label.setText(os.path.basename(file_path))
            
            # Get file info
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S")
            
            self.metadata_label.setText(f"Size: {file_size:.2f} MB | Modified: {file_time}")
            
            # Enable buttons
            self.open_folder_button.setEnabled(True)
            self.open_file_button.setEnabled(True)
            
            return True
        
        except Exception as e:
            logging.error(f"Error loading image {file_path}: {e}")
            self._show_placeholder()
            return False
    
    def _show_placeholder(self):
        """Show placeholder when no image is available."""
        self.current_image_path = None
        self.image_label.setText("No image selected")
        self.image_label.setPixmap(QPixmap())  # Clear any current image
        self.filename_label.setText("No file selected")
        self.metadata_label.setText("")
        self.open_folder_button.setEnabled(False)
        self.open_file_button.setEnabled(False)
    
    def _on_open_folder_clicked(self):
        """Open the folder containing the current image."""
        if not self.current_image_path:
            return
        
        try:
            folder_path = os.path.dirname(self.current_image_path)
            os.system(f'xdg-open "{folder_path}"')
        except Exception as e:
            logging.error(f"Error opening folder: {e}")
            QMessageBox.warning(self, "Error", f"Could not open folder: {e}")
    
    def _on_open_file_clicked(self):
        """Open the current image file in the default viewer."""
        if not self.current_image_path:
            return
        
        try:
            os.system(f'xdg-open "{self.current_image_path}"')
        except Exception as e:
            logging.error(f"Error opening file: {e}")
            QMessageBox.warning(self, "Error", f"Could not open file: {e}")
    
    def resizeEvent(self, event):
        """Handle resize events to maintain image scaling."""
        if self.current_image_path:
            self.load_image(self.current_image_path)
        super().resizeEvent(event)


class AutoCaptureDialog(QWidget):
    """Dialog for configuring automatic capture settings."""
    
    auto_capture_requested = pyqtSignal(str, float, int)  # Camera port, interval, count
    
    def __init__(self, camera_port: str, camera_name: str, parent=None):
        super().__init__(parent)
        
        self.camera_port = camera_port
        self.camera_name = camera_name
        
        self.setWindowTitle("Auto Capture Settings")
        self.setFixedSize(350, 230)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Camera info
        layout.addWidget(QLabel(f"<b>Camera:</b> {camera_name}"))
        layout.addWidget(QLabel(f"<b>Port:</b> {camera_port}"))
        
        # Interval setting
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Capture Interval (seconds):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setMinimum(1)
        self.interval_spin.setMaximum(3600)
        self.interval_spin.setValue(5)
        interval_layout.addWidget(self.interval_spin)
        layout.addLayout(interval_layout)
        
        # Count setting
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of Captures:"))
        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(1)
        self.count_spin.setMaximum(1000)
        self.count_spin.setValue(10)
        self.count_spin.setSpecialValueText("Unlimited")  # 1 means unlimited
        count_layout.addWidget(self.count_spin)
        layout.addLayout(count_layout)
        
        # Continuous checkbox
        self.continuous_checkbox = QCheckBox("Continuous Capture (until manually stopped)")
        self.continuous_checkbox.toggled.connect(self._on_continuous_toggled)
        layout.addWidget(self.continuous_checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Auto Capture")
        self.start_button.clicked.connect(self._on_start_clicked)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.start_button)
        
        layout.addStretch()
        layout.addLayout(button_layout)
    
    def _on_continuous_toggled(self, checked: bool):
        """Handle continuous checkbox toggle."""
        self.count_spin.setEnabled(not checked)
    
    def _on_start_clicked(self):
        """Handle start button click."""
        interval = self.interval_spin.value()
        
        # If continuous is checked, use 0 for count to indicate unlimited
        if self.continuous_checkbox.isChecked():
            count = 0
        else:
            count = self.count_spin.value()
        
        self.auto_capture_requested.emit(self.camera_port, interval, count)
        self.close()


class TetheredShootingPanel(QSplitter):
    """Main panel for tethered shooting, containing camera panels and image view."""
    
    def __init__(self, tethering_manager=None, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        
        # Set up the tethering manager
        self.tethering_manager = tethering_manager or TetheredShootingManager()
        
        # Connect to tethered events
        self.tethering_manager.tethered_event.connect(self._on_tethered_event)
        
        # Camera panels area (left side)
        self.cameras_scroll = QScrollArea()
        self.cameras_scroll.setWidgetResizable(True)
        self.cameras_scroll.setMinimumWidth(350)
        
        self.cameras_container = QWidget()
        self.cameras_layout = QVBoxLayout(self.cameras_container)
        self.cameras_layout.setContentsMargins(10, 10, 10, 10)
        self.cameras_layout.setSpacing(15)
        self.cameras_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.cameras_scroll.setWidget(self.cameras_container)
        
        # Camera panels dictionary
        self.camera_panels: Dict[str, TetheredCameraPanel] = {}
        
        # Image view area (right side)
        self.image_view = CameraCaptureView()
        
        # Add to splitter
        self.addWidget(self.cameras_scroll)
        self.addWidget(self.image_view)
        
        # Set initial sizes
        self.setSizes([350, 650])
        
        # Auto-capture dialogs
        self.auto_capture_dialogs: Dict[str, AutoCaptureDialog] = {}
    
    def add_camera(self, camera_port: str, camera_name: str):
        """Add a camera to the tethered shooting panel."""
        if camera_port in self.camera_panels:
            logging.warning(f"Camera {camera_port} already exists in tethered panel")
            return
        
        # Create camera panel
        panel = TetheredCameraPanel(camera_port, camera_name)
        
        # Connect signals
        panel.start_tethering_signal.connect(self._on_start_tethering)
        panel.stop_tethering_signal.connect(self._on_stop_tethering)
        panel.capture_requested.connect(self._on_capture_requested)
        panel.image_selected.connect(self.image_view.load_image)
        panel.auto_capture_button.clicked.connect(lambda: self._show_auto_capture_dialog(camera_port))
        
        # Add to layout
        self.cameras_layout.addWidget(panel)
        
        # Store in dictionary
        self.camera_panels[camera_port] = panel
    
    def remove_camera(self, camera_port: str):
        """Remove a camera from the tethered shooting panel."""
        if camera_port not in self.camera_panels:
            return
        
        # Stop tethering if active
        if self.tethering_manager.is_tethering_active(camera_port):
            self.tethering_manager.stop_tethering(camera_port)
        
        # Remove from layout and delete
        panel = self.camera_panels[camera_port]
        self.cameras_layout.removeWidget(panel)
        panel.deleteLater()
        
        # Remove from dictionary
        del self.camera_panels[camera_port]
    
    def _on_start_tethering(self, camera_port: str):
        """Handle start tethering request."""
        panel = self.camera_panels.get(camera_port)
        if not panel:
            return
        
        # Start tethering
        success = self.tethering_manager.start_tethering(camera_port)
        
        if success:
            # Update UI state
            panel.set_tethering_state(True)
            logging.info(f"Started tethering for camera {camera_port}")
        else:
            # Show error
            panel.set_error_state("Failed to start tethering")
            logging.error(f"Failed to start tethering for camera {camera_port}")
    
    def _on_stop_tethering(self, camera_port: str):
        """Handle stop tethering request."""
        panel = self.camera_panels.get(camera_port)
        if not panel:
            return
        
        # Stop tethering
        success = self.tethering_manager.stop_tethering(camera_port)
        
        if success:
            # Update UI state
            panel.set_tethering_state(False)
            logging.info(f"Stopped tethering for camera {camera_port}")
        else:
            # Show error
            panel.set_error_state("Failed to stop tethering")
            logging.error(f"Failed to stop tethering for camera {camera_port}")
    
    def _on_capture_requested(self, camera_port: str):
        """Handle capture request."""
        # For real cameras, this would trigger the camera to take a photo
        # For mock cameras, we can generate a mock capture
        if hasattr(self.tethering_manager, 'capture_mock_image'):
            mock_manager = self.tethering_manager
            success = mock_manager.capture_mock_image(camera_port)
            
            if success:
                logging.info(f"Triggered mock capture for camera {camera_port}")
            else:
                logging.error(f"Failed to trigger mock capture for camera {camera_port}")
                
                # Show error
                panel = self.camera_panels.get(camera_port)
                if panel:
                    panel.set_error_state("Failed to trigger capture")
    
    def _on_tethered_event(self, event: TetheredEvent):
        """Handle tethered events."""
        camera_port = event.camera_port
        panel = self.camera_panels.get(camera_port)
        
        if not panel:
            logging.warning(f"Received event for unknown camera {camera_port}")
            return
        
        if event.event_type == TetheredEvent.EventType.FILE_ADDED:
            # Notification only, file is being added to camera
            logging.info(f"New file detected on camera {camera_port}: {event.data.get('file_path', 'unknown')}")
        
        elif event.event_type == TetheredEvent.EventType.FILE_DOWNLOADED:
            # File has been downloaded, update UI
            file_path = event.data.get('local_file_path')
            if file_path:
                panel.add_captured_image(file_path)
                
                # If this is the first image, auto-load it
                if len(panel.downloaded_files) == 1:
                    self.image_view.load_image(file_path)
        
        elif event.event_type == TetheredEvent.EventType.CAMERA_BUSY:
            # Camera is busy, update UI
            panel.set_tethering_state(True, busy=True)
        
        elif event.event_type == TetheredEvent.EventType.CAMERA_READY:
            # Camera is ready, update UI
            panel.set_tethering_state(True, busy=False)
        
        elif event.event_type == TetheredEvent.EventType.ERROR:
            # Error occurred, update UI
            error_message = event.data.get('error', 'Unknown error')
            panel.set_error_state(error_message)
            logging.error(f"Tethering error for camera {camera_port}: {error_message}")
    
    def _show_auto_capture_dialog(self, camera_port: str):
        """Show the auto-capture dialog for a camera."""
        panel = self.camera_panels.get(camera_port)
        if not panel:
            return
        
        # Create dialog if it doesn't exist
        if camera_port not in self.auto_capture_dialogs:
            dialog = AutoCaptureDialog(camera_port, panel.camera_name)
            dialog.auto_capture_requested.connect(self._on_auto_capture_requested)
            self.auto_capture_dialogs[camera_port] = dialog
        
        # Show dialog
        dialog = self.auto_capture_dialogs[camera_port]
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
    
    def _on_auto_capture_requested(self, camera_port: str, interval: float, count: int):
        """Handle auto-capture request."""
        # Only works with mock cameras for now
        if hasattr(self.tethering_manager, 'start_auto_capture'):
            mock_manager = self.tethering_manager
            success = mock_manager.start_auto_capture(camera_port, interval, count if count > 0 else None)
            
            if success:
                logging.info(f"Started auto-capture for camera {camera_port} with interval {interval}s and count {count}")
            else:
                logging.error(f"Failed to start auto-capture for camera {camera_port}")
                
                # Show error
                panel = self.camera_panels.get(camera_port)
                if panel:
                    panel.set_error_state("Failed to start auto-capture")
    
    def stop_all_tethering(self):
        """Stop tethering for all cameras."""
        self.tethering_manager.stop_all_tethering()
        
        # Update all panels
        for panel in self.camera_panels.values():
            panel.set_tethering_state(False)


# Testing code when run as script
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    logging.basicConfig(level=logging.DEBUG,
                      format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s')
    
    app = QApplication(sys.argv)
    
    # Create mock tethering manager
    manager = MockTetheredShootingManager()
    
    # Create tethered shooting panel
    panel = TetheredShootingPanel(manager)
    panel.setWindowTitle("Tethered Shooting")
    panel.resize(1200, 800)
    
    # Add some mock cameras
    panel.add_camera("usb:mock01", "Canon EOS 5D Mark IV")
    panel.add_camera("usb:mock02", "Sony Alpha a7 III")
    panel.add_camera("usb:mock03", "Nikon Z6")
    
    panel.show()
    
    sys.exit(app.exec())