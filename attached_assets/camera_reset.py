# camera_reset.py
# Utility script to help address "Could not claim the USB device" errors with Sony cameras
import subprocess
import logging
import time
import os
import sys

def kill_competing_processes():
    """Kill any processes that might be interfering with camera access."""
    logging.info("Attempting to kill competing processes that might access cameras...")
    
    # List of common processes that can interfere with gphoto2
    interfering_processes = [
        "gvfs-gphoto2-volume-monitor",
        "gvfsd-gphoto2",
        "gphoto2",
        "PTPCamera"  # Mac process
    ]
    
    for process_name in interfering_processes:
        try:
            logging.info(f"Attempting to kill process: {process_name}")
            subprocess.run(["killall", "-9", process_name], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           check=False)  # Don't raise exception if process not found
        except Exception as e:
            logging.warning(f"Error killing process {process_name}: {e}")
    
    # Give system time to release resources
    time.sleep(1)
    logging.info("Competing processes kill attempt completed")

def reset_usb_device(device_port):
    """
    Reset a specific USB device to clear any hung states.
    
    Args:
        device_port: The port identifier (e.g., 'usb:001,003')
    
    Returns:
        Boolean indicating success
    """
    if not device_port.startswith('usb:'):
        logging.warning(f"Cannot reset non-USB device: {device_port}")
        return False
    
    try:
        # Extract bus and device numbers
        _, location = device_port.split(':', 1)
        if ',' in location:
            bus, device = location.split(',', 1)
            bus = bus.strip()
            device = device.strip()
            
            logging.info(f"Attempting to reset USB device at bus {bus}, device {device}")
            
            # Method 1: Using usbreset (if available)
            try:
                subprocess.run(["usbreset", f"/dev/bus/usb/{bus}/{device}"], 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE,
                              check=False,
                              timeout=5)
            except (subprocess.SubprocessError, FileNotFoundError):
                logging.debug("usbreset not available, trying alternative method")

            # Method 2: Using libusb - explicitly unbind/rebind the driver
            sys_path = f"/sys/bus/usb/devices/{bus}-{device}"
            if os.path.exists(sys_path):
                try:
                    # Unbind
                    with open(f"{sys_path}/driver/unbind", "w") as f:
                        f.write(f"{bus}-{device}")
                    time.sleep(1)
                    # Rebind
                    with open("/sys/bus/usb/drivers/usb/bind", "w") as f:
                        f.write(f"{bus}-{device}")
                    logging.info(f"Successfully reset USB device at {device_port}")
                    return True
                except (IOError, PermissionError) as e:
                    logging.warning(f"Failed to reset USB device {device_port} via sysfs: {e}")
            
            time.sleep(2)  # Give the system time to reset and re-enumerate the device
            return True
        else:
            logging.warning(f"Invalid USB port format: {device_port}")
            return False
    except Exception as e:
        logging.error(f"Error resetting USB device {device_port}: {e}")
        return False

def reset_all_cameras(status_signal=None, progress_signal=None, **kwargs):
    """
    Detect all cameras with gphoto2 and attempt to reset each one.
    
    Args:
        status_signal: Optional signal to emit status updates
        progress_signal: Optional signal to emit progress updates
        **kwargs: Additional keyword arguments (for compatibility with Worker)
    
    Returns:
        Boolean indicating success
    """
    try:
        # First kill potentially interfering processes
        kill_competing_processes()
        
        if status_signal:
            status_signal.emit("Detecting connected cameras...")
        
        # Then detect cameras
        result = subprocess.run(["gphoto2", "--auto-detect"], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           text=True,
                           check=False)
        
        # Parse output to find camera ports
        lines = result.stdout.strip().split('\n')
        ports = []
        
        # Skip the header line
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 2 and parts[-1].startswith("usb:"):
                ports.append(parts[-1])
        
        if status_signal:
            status_signal.emit(f"Found {len(ports)} cameras to reset")
            
        # Reset each detected camera
        for i, port in enumerate(ports):
            if status_signal:
                status_signal.emit(f"Resetting camera at {port}...")
                
            reset_usb_device(port)
            
            if progress_signal and ports:
                # Update progress percentage
                progress = int(((i + 1) / len(ports)) * 100)
                progress_signal.emit(progress)
                
        if status_signal:
            status_signal.emit("Camera reset complete")
            
        return True
    except Exception as e:
        error_msg = f"Error in reset_all_cameras: {e}"
        logging.error(error_msg)
        if status_signal:
            status_signal.emit(f"Error: {error_msg}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        # Reset specific device
        reset_usb_device(sys.argv[1])
    else:
        # Reset all cameras and kill competing processes
        kill_competing_processes()
        reset_all_cameras(status_signal=None, progress_signal=None)