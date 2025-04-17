# Multi-Camera Control Application

A PyQt6-based application for controlling and managing multiple DSLR/mirrorless cameras simultaneously.

## Features

- **Multi-Camera Detection**: Automatically detects and connects to multiple cameras
- **Simultaneous Control**: Control all connected cameras at once or individually
- **Live Preview**: View live preview images from all connected cameras
- **Simultaneous Capture**: Trigger photo capture on all cameras at once
- **Adjustable Settings**: Change ISO, aperture, and shutter speed settings
- **Format Selection**: Choose between JPEG, RAW, TIFF and other image formats
- **Organized Image Storage**: Captured images are saved with timestamps and camera identifiers
- **Format Organization**: Optional organization of captures by image format type
- **Format Preferences**: Configure preferences to prioritize certain formats (RAW, JPEG)
- **Camera Profiles**: Save and apply camera settings profiles across multiple cameras
- **Profile Capture Workflow**: Apply a profile to multiple cameras and capture immediately
- **Screenshot Functionality**: Capture application screenshots with customizable save locations

## Requirements

- Python 3.6+
- PyQt6
- Pillow (PIL)
- gphoto2 (command-line tool)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   ```

2. Install dependencies:
   ```
   pip install PyQt6 pillow
   ```

3. Install gphoto2 (system dependency):
   - **Ubuntu/Debian**: `sudo apt install gphoto2`
   - **MacOS**: `brew install gphoto2`
   - **Windows**: Not directly supported, consider using WSL2

## Usage

### Standard Mode

Run the application with:

```
python attached_assets/main.py
```

### Testing Mode (with Mock Cameras)

For testing without physical cameras:

```
python attached_assets/main_offscreen.py
```

This starts the application with 3 virtual cameras for testing the interface and functionality.

### Enhanced Mode (with Format Organization)

For advanced features including format organization:

```
python attached_assets/main_enhanced.py --mock
```

With format organization enabled and RAW format preference:

```
python attached_assets/main_enhanced.py --mock --organize-by-format --format-preference prefer_raw
```

### Profile Capture Demo

To demonstrate the profile capture workflow with mock cameras:

```
python attached_assets/demo_profile_capture.py --organize-by-format --format-preference prefer_raw
```

This script creates a demo profile (if not already present), applies it to mock cameras, and captures images with those settings.

Available command-line options:
- `--mock`: Use mock cameras instead of real hardware
- `--mock-count N`: Specify number of mock cameras to create
- `--offscreen`: Run in offscreen mode (no visible UI)
- `--format FORMAT`: Set default image format (jpeg, raw, tiff)
- `--quality QUALITY`: Set JPEG quality (standard, fine, extra-fine)
- `--organize-by-format`: Enable organization of captures by format type
- `--format-preference PREF`: Set format preference (keep_all, prefer_raw, prefer_jpeg)
- `--prefix PREFIX`: Set default filename prefix
- `--naming-template TEMPLATE`: Set naming template for captured files

## Application Structure

- **camera_manager.py**: Core camera detection and control functionality
- **gui.py**: Basic PyQt6 user interface implementation
- **gui_updated.py**: Enhanced UI with profile and format support
- **worker.py**: Manages background tasks in separate threads
- **logger_setup.py**: Configures application logging
- **mock_camera.py**: Virtual camera implementation for testing
- **main.py**: Basic application entry point
- **main_enhanced.py**: Enhanced version with format organization and CLI options
- **main_offscreen.py**: Entry point for headless/offscreen testing
- **camera_profiles.py**: Profile management system for camera settings
- **camera_format_extension.py**: Format handling implementation
- **format_organizer.py**: Implements format-based directory organization
- **profile_dialogs.py**: UI dialogs for managing camera profiles
- **profile_capture.py**: Manages profile application and capture workflow
- **demo_profile_capture.py**: Demonstration script for profile capture functionality
- **screenshot_utility.py**: Screenshot capture and management functionality

## Camera Workflow

1. **Detection**: Click "Detect Cameras" to find connected cameras
2. **Preview**: Toggle "Show Previews" to see live output from all cameras
3. **Configure**: Adjust camera settings as needed (ISO, aperture, shutter speed)
4. **Capture**: Click "Capture All" to take photos with all cameras simultaneously
5. **Review**: Find your captured images in the "captures" directory

## Camera Settings

The application supports adjusting:
- **ISO**: Camera light sensitivity (100, 200, 400, etc.)
- **Aperture**: Lens opening size (f/1.8, f/2.8, f/4, etc.)
- **Shutter Speed**: Exposure time (1/4000, 1/1000, 1/250, etc.)
- **Image Format**: JPEG, RAW, TIFF, and combined formats (RAW + JPEG)
- **Quality Level**: Standard, Fine, Extra Fine (for JPEG)

## Format Organization

The application provides advanced organization options for image captures:

### Directory Structure

When format organization is enabled, images are organized in the following structure:
```
captures/
  └── YYYY-MM-DD/
      ├── JPEG/
      │   └── capture_[camera]_[timestamp].jpg
      ├── RAW/
      │   └── capture_[camera]_[timestamp].raw
      └── TIFF/
          └── capture_[camera]_[timestamp].tiff
```

### Format Preferences

The application supports different format preference modes:

- **Keep All**: Download all formats produced by the camera (default)
- **Prefer RAW**: Prioritize RAW formats when available
- **Prefer JPEG**: Prioritize JPEG formats when available

These preferences can be set via command-line options or in the UI.

## Camera Profiles

The application supports saving and applying camera profiles to quickly configure multiple cameras with the same settings:

### Profile Features

- **Save Settings**: Store ISO, aperture, and shutter speed combinations as named profiles
- **Apply to Multiple Cameras**: Quickly apply the same profile to multiple cameras
- **Default Profiles**: System includes several built-in profiles for common shooting scenarios
- **Custom Profiles**: Create your own profiles for specific shooting needs
- **Profile Capture**: Apply a profile to multiple cameras and capture immediately

Profiles are stored as JSON files in the `profiles/` directory and can be managed through the Profile menu in the application.

### Profile Capture Workflow

The "Apply Profile and Capture" feature provides a streamlined workflow for photographers:

1. Select a saved profile from the Profile menu
2. Choose which cameras to apply the profile to
3. System applies the profile settings to selected cameras
4. Images are captured automatically from each camera
5. Images are organized according to format preferences

This workflow is ideal for situations like studio photography where a consistent setup across multiple cameras is needed before a shoot.

## Supported Cameras

This application supports most DSLR and mirrorless cameras that work with gphoto2, including:

- Canon EOS series
- Nikon Z/D series
- Sony Alpha series
- Fujifilm X series
- Olympus/OM System cameras
- And many others

## Screenshot Feature

The application includes a one-click screenshot feature allowing you to capture the current state of the application:

- **Quick Screenshot**: Capture the entire application window with a single click
- **Custom Save Locations**: Configure and manage multiple save directories for screenshots
- **Organized Storage**: Screenshots are saved with timestamps and descriptive names
- **Replit Integration**: Automatic detection of Replit environment with appropriate defaults

For detailed information about the screenshot feature, see [SCREENSHOT_FEATURE.md](SCREENSHOT_FEATURE.md).

## Troubleshooting

- **No Cameras Detected**: Ensure your camera is turned on and connected via USB
- **Access Denied**: You may need to run with sudo/admin privileges on some systems
- **Camera Busy**: Close any other applications that might be accessing the camera
- **Camera Locked**: Some cameras may require unlocking in their settings to allow USB control

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Credits

Developed by Replit User
