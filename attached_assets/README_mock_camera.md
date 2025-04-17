# Mock Camera Module

This module provides a virtual camera implementation for testing the multi-camera control application without physical camera hardware.

## Overview

The mock camera system simulates the presence of DSLR/mirrorless cameras by:

1. Creating virtual camera objects with realistic properties
2. Generating sample images with overlaid camera metadata
3. Simulating camera operations like setting changes and image capture
4. Providing preview image functionality

## Usage

### Basic Usage

To use the mock camera system in a standalone way:

```python
from mock_camera import MockCameraManager

# Create a manager with 3 virtual cameras
manager = MockCameraManager(num_cameras=3)

# Get the available mock cameras
mock_cameras = manager.get_mock_cameras()

# Capture an image from a specific camera
port = list(mock_cameras.keys())[0]  # Get first camera port
success, filepath, error = manager.capture_mock_image(
    port=port,
    save_path="./captures",
    filename_prefix="test"
)

# Get a preview image from a camera
success, image_data, error = manager.get_preview_image(port=port)

# Change a camera setting
manager.set_camera_setting(port=port, setting_type="iso", value="400")
```

### Integration with Main Application

The `main_offscreen.py` module shows how to integrate the mock cameras with the full application by patching the `CameraManager` class to use mock implementations.

## Mock Camera Features

Each mock camera has:

- Unique camera model name
- Unique port identifier (usb:mock01, usb:mock02, etc.)
- Configurable ISO settings (100, 200, 400, 800, 1600, 3200)
- Configurable aperture settings (f/1.8 through f/16)
- Configurable shutter speed settings (1/4000 through 1/8)

## Image Generation

Mock images are generated with:

- Random background colors
- Camera model and settings overlay
- Timestamp information
- Random geometric elements to make each capture unique
- "MOCK CAPTURE" indicator to identify test images

## Preview Generation

Preview images are smaller (640x480) and include:

- Current camera model and settings
- "LIVE PREVIEW" indicator
- A timestamp that updates with each preview request

## Simulated Delays

To better simulate real-world conditions, operations include realistic delays:

- Camera detection: ~1 second
- Image capture: 0.5-1.5 seconds
- Preview capture: 0.2-0.5 seconds
- Setting changes: 0.1-0.3 seconds

## Extending the Mock System

You can extend the mock system by:

1. Adding more camera models to the available choices
2. Implementing more realistic image generation with camera-specific looks
3. Adding simulated failures to test error handling
4. Adding more camera-specific settings beyond ISO, aperture, and shutter speed