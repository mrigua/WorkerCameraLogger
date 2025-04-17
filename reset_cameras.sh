#!/bin/bash
# Script to reset cameras and resolve USB device claim issues
# Usage: ./reset_cameras.sh

echo "=== Camera Connection Reset Utility ==="
echo "This script will attempt to reset your camera connections by:"
echo "  1. Killing any processes that might be accessing the cameras"
echo "  2. Resetting USB devices"
echo "  3. Clearing any stuck PTP sessions"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Note: Some operations may require sudo privileges."
  echo "If this script doesn't fix the issue, try running it with sudo."
  echo ""
fi

# Kill common processes that might hold onto camera connections
echo "Killing processes that might be accessing cameras..."
PROCESSES=("gvfs-gphoto2-volume-monitor" "gvfsd-gphoto2" "gphoto2" "PTPCamera")

for process in "${PROCESSES[@]}"; do
  echo "  Attempting to kill $process..."
  killall -9 "$process" 2>/dev/null
  if [ $? -eq 0 ]; then
    echo "    Success: $process terminated."
  else
    echo "    Note: $process was not running."
  fi
done

# Check if we can find any camera devices
echo ""
echo "Looking for connected cameras..."
if command -v gphoto2 &>/dev/null; then
  CAMERAS=$(gphoto2 --auto-detect 2>/dev/null)
  if [ $? -eq 0 ]; then
    echo "$CAMERAS"
    echo ""
    echo "Found potential cameras. Attempting to reset..."
  else
    echo "No cameras detected or gphoto2 error occurred."
    echo ""
  fi
else
  echo "gphoto2 command not found. Cannot detect cameras."
  echo ""
fi

# Reset USB devices
if command -v lsusb &>/dev/null; then
  echo "Resetting USB devices that might be cameras..."
  
  # Find devices that might be cameras (common vendor IDs)
  # Canon: 04a9, Nikon: 04b0, Sony: 054c, Fujifilm: 04cb, Olympus: 07b4
  CAMERA_VENDORS=("04a9" "04b0" "054c" "04cb" "07b4")
  FOUND=0
  
  for vendor in "${CAMERA_VENDORS[@]}"; do
    DEVICES=$(lsusb | grep -i "$vendor")
    if [ ! -z "$DEVICES" ]; then
      echo "$DEVICES"
      FOUND=1
      
      # Get bus and device IDs
      while read -r line; do
        if [[ $line =~ Bus\ ([0-9]+)\ Device\ ([0-9]+) ]]; then
          BUS=$(printf "%03d" ${BASH_REMATCH[1]})
          DEVICE=$(printf "%03d" ${BASH_REMATCH[2]})
          
          if command -v usbreset &>/dev/null && [ "$EUID" -eq 0 ]; then
            echo "  Resetting USB device: /dev/bus/usb/$BUS/$DEVICE"
            usbreset "/dev/bus/usb/$BUS/$DEVICE" 2>/dev/null
          else
            echo "  Found potential camera at: /dev/bus/usb/$BUS/$DEVICE"
            echo "  To reset it manually, run: sudo usbreset /dev/bus/usb/$BUS/$DEVICE"
          fi
        fi
      done <<< "$DEVICES"
    fi
  done
  
  if [ $FOUND -eq 0 ]; then
    echo "No camera USB devices detected."
  fi
else
  echo "lsusb command not found. Cannot detect USB devices."
fi

echo ""
echo "=== Camera reset complete ==="
echo "Now try using your camera with the Multi-Camera Control application."
echo "If you still have issues, try the following:"
echo "  1. Disconnect and reconnect your camera"
echo "  2. Restart the Multi-Camera Control application with --auto-reset flag"
echo "  3. For Sony cameras, try the sony-specific reset script: ./reset_sony_cameras.sh"
echo ""