# Multi-Camera Control Application User Guide

This comprehensive guide will help you get started with the Multi-Camera Control application and make the most of its features.

## Getting Started

### System Requirements

- Operating system: Linux, macOS, or Windows (with WSL2)
- Python 3.6 or higher
- At least one camera supported by gphoto2
- USB port for camera connection

### Application Modes

The application can be run in several modes to suit your needs:

1. **Standard Mode**: Basic functionality with real cameras
   ```
   python attached_assets/main.py
   ```

2. **Enhanced Mode**: Full feature set including format organization
   ```
   python attached_assets/main_enhanced.py
   ```

3. **Mock Mode**: Testing mode with virtual cameras (add `--mock` to any command)
   ```
   python attached_assets/main_enhanced.py --mock
   ```

4. **Minimalist Mode**: Cleaner interface with modern styling
   ```
   python attached_assets/main_enhanced.py --mock --minimalist-ui
   ```

5. **Tethered Mode**: Dedicated mode for tethered shooting
   ```
   python attached_assets/main_tethered.py --mock
   ```

### First Launch

1. Connect your camera(s) to your computer via USB
2. Turn on the camera(s)
3. Launch the application in your preferred mode
4. Click "Detect Cameras" to find connected devices
5. Your cameras should appear in the left panel

## Core Features

### Camera Detection

- Click the "Detect Cameras" button to scan for connected cameras
- Each detected camera will appear in the left panel
- If a camera is connected but not detected, try:
  - Turning the camera off and on
  - Unplugging and reconnecting the USB cable
  - Selecting "Reset All Cameras" from the File menu

### Camera Settings

For each connected camera, you can adjust:

- **ISO**: Controls light sensitivity (lower for bright conditions, higher for low light)
- **Aperture**: Controls depth of field (lower f-number for blur, higher for sharpness)
- **Shutter Speed**: Controls exposure time (faster for action, slower for low light)
- **Format**: Choose between JPEG, RAW, TIFF, or combined formats
- **Quality**: For JPEG, select Standard, Fine, or Extra Fine quality

### Taking Photos

- **Individual Capture**: Click the "Capture" button for a specific camera
- **Capture All**: Click the "Capture All" button to take photos with all cameras
- **Timed Capture**: Set up a timed capture sequence for specific intervals

### Live Preview

- Toggle "Show Previews" to see a live view from each camera
- Preview quality varies by camera model and connection speed
- Live preview may impact battery life on some camera models

## Advanced Features

### Camera Profiles

Profiles let you save and quickly apply specific camera settings:

1. **Creating a Profile**:
   - Set up your camera settings as desired
   - Select "Save Profile" from the Profile menu
   - Enter a name and description for the profile

2. **Using a Profile**:
   - Select "Apply Profile" from the Profile menu
   - Choose the profile to apply
   - Select which cameras should receive the profile settings

3. **Profile Capture**:
   - Select "Apply Profile and Capture" from the Profile menu
   - Choose the profile and target cameras
   - The system will apply settings and immediately capture images

### Format Organization

Enable format-based organization to sort images by type:

1. **Enabling Organization**:
   - Launch with `--organize-by-format` option or
   - Check "Organize by Format" in the Format menu

2. **Format Preferences**:
   - **Keep All**: Download all formats produced by the camera
   - **Prefer RAW**: Prioritize RAW formats when available
   - **Prefer JPEG**: Prioritize JPEG formats when available

### Tethered Shooting

Tethered shooting provides direct download of images as they are captured:

1. **Starting Tethered Mode**:
   - Launch the tethered application or
   - Select "Start Tethered Shooting" for a specific camera

2. **Auto-Capture**:
   - Set an interval for automatic captures
   - Click "Start Auto-Capture" to begin the sequence
   - Images are downloaded automatically as they are taken

3. **Browse Images**:
   - View downloaded images in the tethered panel
   - Click on thumbnails to view larger previews
   - Sort by time or filename using the view options

### Screenshot Feature

Capture the application state for documentation or troubleshooting:

1. **Taking Screenshots**:
   - Click the "Screenshot" button in the toolbar
   - View confirmation in the status bar
   - Find saved screenshots in the configured location

2. **Configuring Screenshots**:
   - Select "Configure Screenshot Settings..." from the Screenshot menu
   - Add or modify save locations
   - Select your preferred default save directory

For more details on the screenshot feature, see [SCREENSHOT_FEATURE.md](SCREENSHOT_FEATURE.md).

## Troubleshooting

### Common Issues

#### Camera Not Detected

- Ensure the camera is turned on and in PC connection mode
- Try a different USB port or cable
- Select "Reset All Cameras" from the File menu
- For Sony cameras, see the USB_DEVICE_CLAIM_FIX.md file

#### Camera Shows "Busy" Status

- Close any other applications that might be accessing the camera
- Turn the camera off and on, then detect again
- Try the reset script: `./reset_cameras.sh`

#### Preview Not Working

- Some cameras don't support live preview via USB
- Check if your camera model supports the PTP picture transfer protocol
- Try a different USB cable (preferably the one that came with the camera)

#### Failed Captures

- Ensure the camera has enough battery power
- Check that there is enough free space on the memory card
- Make sure the camera is not in sleep mode

### Log Files

The application creates detailed log files that can help diagnose issues:

- **Main log**: `multi_camera_app.log` in the application directory
- **Profile capture log**: `profile_capture_demo.log` for profile operations
- **Camera connection issues**: Check the log for "USB device busy" messages

## Command Line Options

The application supports numerous command-line options:

- `--mock`: Use virtual cameras instead of real hardware
- `--mock-count N`: Create N mock cameras (default: 3)
- `--offscreen`: Run without displaying a window (for testing)
- `--format FORMAT`: Set default image format (jpeg, raw, tiff)
- `--organize-by-format`: Enable organization by format type
- `--format-preference PREF`: Set format preference mode
- `--prefix PREFIX`: Set a custom filename prefix for captures
- `--classic-ui`: Use the original UI design instead of minimalist
- `--auto-reset`: Automatically reset camera connections at startup

## Additional Resources

- **README.md**: Primary project documentation
- **SCREENSHOT_FEATURE.md**: Details on the screenshot functionality
- **USB_DEVICE_CLAIM_FIX.md**: Help for Sony camera connection issues

## Keyboard Shortcuts

The application supports several keyboard shortcuts:

- **Ctrl+D**: Detect cameras
- **Ctrl+C**: Capture with selected camera
- **Ctrl+A**: Capture with all cameras
- **Ctrl+P**: Toggle preview mode
- **Ctrl+S**: Take a screenshot
- **F1**: Show help
- **Esc**: Close dialogs

---

For technical support or feature requests, please contact the developer.