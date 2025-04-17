#!/bin/bash
# Script to reset Sony cameras specifically and resolve USB device claim issues
# Usage: ./reset_sony_cameras.sh

echo "=== Sony Camera Connection Reset Utility ==="
echo "This script will attempt to reset your Sony camera connections by:"
echo "  1. Killing specific processes known to conflict with Sony cameras"
echo "  2. Unloading and reloading Sony-specific USB modules"
echo "  3. Resetting Sony camera USB devices"
echo "  4. Clearing stuck PTP sessions"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Note: Some operations require sudo privileges."
  echo "For best results, run this script with sudo."
  echo ""
fi

# Kill Sony-specific processes that might hold onto camera connections
echo "Killing processes that might be accessing Sony cameras..."
PROCESSES=("gvfs-gphoto2-volume-monitor" "gvfsd-gphoto2" "gphoto2" "PTPCamera" "sony-camera-server" "sony-capture-utility")

for process in "${PROCESSES[@]}"; do
  echo "  Attempting to kill $process..."
  killall -9 "$process" 2>/dev/null
  if [ $? -eq 0 ]; then
    echo "    Success: $process terminated."
  else
    echo "    Note: $process was not running."
  fi
done

# Check if we can find any Sony camera devices
echo ""
echo "Looking for connected Sony cameras..."
if command -v lsusb &>/dev/null; then
  # Sony's vendor ID is 054c
  SONY_DEVICES=$(lsusb | grep -i "054c")
  if [ ! -z "$SONY_DEVICES" ]; then
    echo "Found Sony devices:"
    echo "$SONY_DEVICES"
    echo ""
    
    # Get bus and device IDs for Sony devices
    while read -r line; do
      if [[ $line =~ Bus\ ([0-9]+)\ Device\ ([0-9]+) ]]; then
        BUS=$(printf "%03d" ${BASH_REMATCH[1]})
        DEVICE=$(printf "%03d" ${BASH_REMATCH[2]})
        
        echo "Found Sony device at: /dev/bus/usb/$BUS/$DEVICE"
        
        # Attempt to reset this specific device
        if command -v usbreset &>/dev/null && [ "$EUID" -eq 0 ]; then
          echo "  Resetting USB device: /dev/bus/usb/$BUS/$DEVICE"
          usbreset "/dev/bus/usb/$BUS/$DEVICE" 2>/dev/null
        else
          echo "  To reset manually, run: sudo usbreset /dev/bus/usb/$BUS/$DEVICE"
        fi
      fi
    done <<< "$SONY_DEVICES"
  else
    echo "No Sony USB devices detected."
  fi
else
  echo "lsusb command not found. Cannot detect USB devices."
fi

# Sony-specific USB module handling
echo ""
echo "Handling Sony-specific USB modules..."
if [ "$EUID" -eq 0 ]; then
  # Check if the modules are loaded
  if lsmod | grep -q "usbserial"; then
    echo "  Unloading usbserial module..."
    rmmod usbserial 2>/dev/null
    sleep 1
    echo "  Reloading usbserial module..."
    modprobe usbserial 2>/dev/null
  fi
  
  if lsmod | grep -q "usb_storage"; then
    echo "  Unloading usb_storage module..."
    rmmod usb_storage 2>/dev/null
    sleep 1
    echo "  Reloading usb_storage module..."
    modprobe usb_storage 2>/dev/null
  fi
else
  echo "  Note: USB module operations require root privileges."
  echo "  Run with sudo to perform module reload operations."
fi

# Clear PTP sessions - Sony specific approach
echo ""
echo "Clearing PTP sessions for Sony cameras..."
if command -v gphoto2 &>/dev/null; then
  # Running a quick capture command with timeout often clears stuck sessions
  echo "  Attempting to reset PTP session state..."
  timeout 2s gphoto2 --reset 2>/dev/null
  timeout 2s gphoto2 --port usb: --reset 2>/dev/null
  
  echo "  Sending abort capture command to clear any pending operations..."
  gphoto2 --port usb: --set-config actions/cancelremote=1 2>/dev/null
else
  echo "  gphoto2 command not found. Cannot clear PTP sessions."
fi

# Sony cameras often need a specific USB mode
echo ""
echo "=== Sony Camera Settings Check ==="
echo "Ensure your Sony camera has:"
echo "  1. USB Connection set to 'PC Remote' or 'MTP' mode (NOT Mass Storage)"
echo "  2. USB LUN Setting set to 'Multiple' if available in the menu"
echo "  3. Control Priority set to 'PC Remote' if available"
echo ""

echo "=== Sony camera reset complete ==="
echo "Now try using your Sony camera with the Multi-Camera Control application."
echo "If you still have issues:"
echo "  1. Power cycle your camera (turn it off and on)"
echo "  2. Try a different USB port (preferably USB 2.0 instead of 3.0)"
echo "  3. Launch the application with the --auto-reset flag"
echo ""