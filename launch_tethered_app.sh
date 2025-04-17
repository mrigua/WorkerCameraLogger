#!/bin/bash
# Easy launcher for the tethered shooting app with auto-reset option
# Usage: ./launch_tethered_app.sh [--auto-reset] [--mock] [--organize-by-format] [--format-preference prefer_raw|prefer_jpeg|keep_all]

echo "=== Tethered Shooting Application Launcher ==="
echo "Preparing to launch the application..."
echo ""

# Build the command options
CMD_OPTIONS=""

# Check for auto-reset flag
if [[ "$*" == *"--auto-reset"* ]]; then
  echo "Auto-reset enabled: The application will attempt to reset cameras on startup."
  CMD_OPTIONS="$CMD_OPTIONS --auto-reset"
  
  # Run the reset script before starting
  echo "Running camera reset script before starting..."
  ./reset_cameras.sh
  echo ""
fi

# Check for Sony cameras
if lsusb 2>/dev/null | grep -q "054c"; then
  echo "Sony camera detected!"
  echo "Running Sony-specific reset script..."
  ./reset_sony_cameras.sh
  echo ""
fi

# Check for mock flag
if [[ "$*" == *"--mock"* ]]; then
  echo "Mock mode enabled: Using virtual cameras for testing."
  CMD_OPTIONS="$CMD_OPTIONS --mock"
fi

# Check for format organization
if [[ "$*" == *"--organize-by-format"* ]]; then
  echo "Format organization enabled: Captures will be organized by format type."
  CMD_OPTIONS="$CMD_OPTIONS --organize-by-format"
fi

# Check for format preference
if [[ "$*" == *"--format-preference"* ]]; then
  # Extract preference value
  PREF=$(echo "$*" | grep -o "\--format-preference [^ ]*" | cut -d " " -f2)
  if [ ! -z "$PREF" ]; then
    echo "Format preference set to: $PREF"
    CMD_OPTIONS="$CMD_OPTIONS --format-preference $PREF"
  fi
fi

# Check for auto-capture flag
if [[ "$*" == *"--auto-capture"* ]]; then
  echo "Auto-capture enabled: The application will automatically capture images at intervals."
  CMD_OPTIONS="$CMD_OPTIONS --auto-capture"
fi

# Add any other arguments
for arg in "$@"; do
  if [[ "$arg" != "--auto-reset" && "$arg" != "--mock" && "$arg" != "--organize-by-format" && "$arg" != "--format-preference"* && "$arg" != "--auto-capture" ]]; then
    CMD_OPTIONS="$CMD_OPTIONS $arg"
  fi
done

echo "Launching the Tethered Shooting application..."
echo "Command: python attached_assets/demo_tethered_shooting.py $CMD_OPTIONS"
echo ""
echo "Press Ctrl+C to exit the application."
echo "========================================================="
echo ""

# Start the application
python attached_assets/demo_tethered_shooting.py $CMD_OPTIONS