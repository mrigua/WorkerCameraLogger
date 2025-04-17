# camera_manager.py
import subprocess
import logging
import time
import re
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# --- Configuration ---
GPHOTO2_CMD = "gphoto2"
CONNECTION_RETRIES = 3
CONNECTION_RETRY_DELAY = 2 # seconds
CAPTURE_RETRIES = 2
CAPTURE_RETRY_DELAY = 1 # seconds

# --- Data Classes ---
@dataclass
class CameraSettings:
    iso: Optional[str] = None
    aperture: Optional[str] = None
    shutter_speed: Optional[str] = None # Use underscore here
    iso_choices: List[str] = field(default_factory=list)
    aperture_choices: List[str] = field(default_factory=list)
    shutter_speed_choices: List[str] = field(default_factory=list) # Use underscore here

@dataclass
class CameraInfo:
    model: str
    port: str
    status: str = "Disconnected"
    settings: CameraSettings = field(default_factory=CameraSettings)
    last_error: Optional[str] = None

# --- Camera Manager ---
class CameraManager:
    def __init__(self):
        self.cameras: Dict[str, CameraInfo] = {} # port -> CameraInfo
        self.config_names = {
            "iso": ["iso", "iso speed", "iso sensitivity", "isonumber"],
            "aperture": ["aperture", "f-number", "fnumber"],
            "shutterspeed": ["shutterspeed", "shutter speed", "exptime", "exposure time"]
        }
        self._resolved_config_names: Dict[str, Dict[str, str]] = {}

    def _run_gphoto_command(self, args: List[str], port: Optional[str] = None, retries: int = 0, delay: int = 1, timeout: int = 45) -> Tuple[bool, str, str]:
        """Runs a gphoto2 command and returns (success, stdout, stderr)."""
        command = [GPHOTO2_CMD]
        if port:
            command.extend(["--port", port])
        command.extend(args)

        full_cmd_str = ' '.join(command)
        logging.debug(f"Running command: {full_cmd_str}")
        stdout, stderr = "", ""

        for attempt in range(retries + 1):
            try:
                process = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True, errors='ignore', check=False, timeout=timeout
                )
                stdout = process.stdout.strip()
                stderr = process.stderr.strip()

                # Check for explicit failure conditions first
                is_capture_cmd = "--capture-image-and-download" in args or "--capture-image" in args
                command_failed = False
                error_reason = ""

                if process.returncode != 0:
                    command_failed = True
                    error_reason = f"Exit code {process.returncode}"
                # Even if retcode is 0, check stderr for critical errors on capture
                elif is_capture_cmd and ("ERROR: Could not capture" in stderr or "PTP I/O Error" in stderr):
                     command_failed = True
                     error_reason = "Capture error reported in stderr"
                     logging.warning(f"Command success (retcode 0) but critical error found in stderr: {stderr}")
                # Add other critical stderr checks if needed

                if not command_failed:
                    logging.debug(f"Command successful (stdout): {stdout[:150]}...")
                    return True, stdout, stderr

                # Handle specific retryable errors IF command failed
                if "Could not claim the USB device" in stderr or \
                   "Could not lock the device" in stderr or \
                   "PTP I/O Error" in stderr or \
                   "Camera is busy" in stderr or \
                   "Timeout reading from or writing to the port" in stderr:
                    log_msg_base = f"Attempt {attempt+1}/{retries+1}: Device busy/claim/IO/Timeout error ({error_reason}) for port {port}."
                    if attempt < retries:
                         logging.warning(f"{log_msg_base} Retrying in {delay}s... Stderr: {stderr}")
                         time.sleep(delay)
                         continue # Retry
                    else:
                         logging.error(f"{log_msg_base} No retries left. Stderr: {stderr}")
                         return False, stdout, stderr # Failed after retries

                # Handle non-retryable command failure (specific errors)
                elif "Unknown port" in stderr or "Could not find the requested device" in stderr:
                    logging.error(f"Command failed (port/device not found - {error_reason}) for port {port}: {stderr}")
                    return False, stdout, stderr

                # Handle generic non-retryable command failure
                else:
                    logging.error(f"Command failed ({error_reason}) for port {port}: {stderr}")
                    return False, stdout, stderr # Failed for other reasons

            except subprocess.TimeoutExpired:
                 logging.error(f"Subprocess timed out after {timeout}s for port {port}: {full_cmd_str}")
                 stderr = "Subprocess timed out"
                 if attempt < retries:
                     logging.info(f"Retrying after subprocess timeout...")
                     time.sleep(delay); continue
                 return False, "", stderr
            except Exception as e:
                logging.exception(f"Exception running command for port {port}: {e}")
                return False, "", str(e)

        logging.error(f"Command failed after {retries + 1} attempts for port {port}. Last error: {stderr}")
        return False, stdout, stderr

    def _parse_auto_detect(self, output: str) -> Dict[str, str]:
        """Parses the output of `gphoto2 --auto-detect`."""
        cameras = {}
        lines = output.splitlines()
        model_line_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("Model") and "Port" in line:
                model_line_index = i
                break
        if model_line_index == -1 or model_line_index + 2 >= len(lines): return cameras

        for line in lines[model_line_index + 2:]:
            line = line.strip()
            if not line: continue
            parts = line.split()
            port = ""
            model = ""
            if len(parts) >= 2 and parts[-1].startswith("usb:"):
                 port = parts[-1]; model = " ".join(parts[:-1]).strip()
            if port.startswith("usb:") and model: cameras[port] = model
        return cameras

    def detect_cameras(self, status_signal=None, progress_signal=None, **kwargs) -> Dict[str, CameraInfo]:
        """Detects connected cameras and updates internal state."""
        logging.info("Detecting cameras...")
        if status_signal: status_signal.emit("Detecting cameras...")
        success, stdout, stderr = self._run_gphoto_command(["--auto-detect"], retries=CONNECTION_RETRIES, delay=CONNECTION_RETRY_DELAY, timeout=15)
        detected_ports_models = {}
        if success:
            detected_ports_models = self._parse_auto_detect(stdout)
            logging.info(f"Detected cameras: {detected_ports_models}")
        else:
            logging.error(f"Camera detection failed: {stderr}")
            if status_signal: status_signal.emit(f"Error detecting cameras: {stderr}")

        current_ports = set(self.cameras.keys())
        newly_detected_ports = set(detected_ports_models.keys())

        for port in current_ports - newly_detected_ports:
            if port in self.cameras and self.cameras[port].status != "Disconnected":
                logging.info(f"Camera at port {port} ({self.cameras[port].model}) seems disconnected.")
                self.cameras[port].status = "Disconnected"
                self.cameras[port].last_error = "Not detected in last scan"
                if port in self._resolved_config_names: del self._resolved_config_names[port]

        processed_ports = set()
        for port, model in detected_ports_models.items():
            should_fetch_details = False
            if port not in self.cameras:
                logging.info(f"Found new camera: {model} at {port}")
                self.cameras[port] = CameraInfo(model=model, port=port, status="Connecting...")
                should_fetch_details = True
            elif self.cameras[port].status in ["Disconnected", "Error"]:
                 logging.info(f"Reconnecting camera: {model} at {port} (Previous status: {self.cameras[port].status})")
                 self.cameras[port].model = model; self.cameras[port].status = "Connecting..."
                 self.cameras[port].last_error = None; should_fetch_details = True
            else: self.cameras[port].model = model

            if should_fetch_details:
                 if status_signal: status_signal.emit(f"Connecting to {model} ({port})...")
                 self.fetch_camera_details(port, status_signal=status_signal)
            elif self.cameras[port].status not in ["Error", "Capturing...", "Applying Settings...", "Fetching Settings...", "Connecting..."]:
                 self.cameras[port].status = "Connected"
            processed_ports.add(port)

        if status_signal: status_signal.emit("Detection complete.")
        return self.cameras.copy()

    def _find_config_name(self, port: str, generic_name: str, available_configs: List[str]) -> Optional[str]:
        """Tries to find the actual gphoto2 config name for a generic setting."""
        if not port or not generic_name: return None
        generic_key = generic_name.lower()
        if port in self._resolved_config_names and generic_key in self._resolved_config_names[port]:
            return self._resolved_config_names[port][generic_key]
        possible_names = self.config_names.get(generic_key, [])
        if not possible_names: return None

        for known_name in possible_names: # Exact match on simple name
            for config in available_configs:
                 if config.split('/')[-1].lower() == known_name.lower():
                     self._cache_resolved_name(port, generic_name, config); return config
        for known_name in possible_names: # Exact match on full name
             for config in available_configs:
                 if config.lower() == known_name.lower():
                      self._cache_resolved_name(port, generic_name, config); return config
        logging.warning(f"Could not find config name for '{generic_name}' (tried {possible_names}) on port {port}")
        return None

    def _cache_resolved_name(self, port:str, generic_name:str, actual_name:str):
         """Caches the resolved gphoto name for a generic name and port."""
         if port not in self._resolved_config_names: self._resolved_config_names[port] = {}
         self._resolved_config_names[port][generic_name.lower()] = actual_name
         logging.info(f"Resolved config name for '{generic_name}' on {port} to '{actual_name}'")

    def _get_all_config_names(self, port: str) -> List[str]:
        """Gets a list of all configuration keys for the camera."""
        success, stdout, stderr = self._run_gphoto_command(["--list-config"], port=port, retries=1, timeout=45)
        if not success: logging.error(f"Failed to list config for {port}: {stderr}"); return []
        keys = re.findall(r'^([/\w\d.-]+)\s+Label:', stdout, re.MULTILINE)
        section_keys = re.findall(r'^(/[/\w\d.-]+)$', stdout, re.MULTILINE)
        all_found_keys = list(set(keys + section_keys))
        logging.debug(f"Available config names extracted for {port}: {all_found_keys}")
        return all_found_keys

    def fetch_camera_details(self, port: str, status_signal=None, **kwargs):
        """Fetches settings and choices for a specific camera."""
        if port not in self.cameras: logging.error(f"Attempted to fetch details for unknown port: {port}"); return
        cam_info = self.cameras[port]
        if cam_info.status not in ["Connecting...", "Error"]: logging.debug(f"Skipping fetch details for {port}, status is {cam_info.status}"); return

        cam_info.status = "Fetching Settings..."
        if status_signal: status_signal.emit(f"Fetching settings for {cam_info.model}...")
        available_configs = self._get_all_config_names(port)
        if not available_configs:
             cam_info.status = "Error"; cam_info.last_error = "Failed to list configuration."
             if status_signal: status_signal.emit(f"Error fetching settings for {cam_info.model}: {cam_info.last_error}")
             return

        settings_to_fetch = ["iso", "aperture", "shutterspeed"]
        found_settings = {}; fetch_failed = False
        for setting_type in settings_to_fetch:
            actual_config_name = self._find_config_name(port, setting_type, available_configs)
            dataclass_attr_name = "shutter_speed" if setting_type == "shutterspeed" else setting_type
            if actual_config_name:
                value, choices = self._get_config_value_and_choices(port, actual_config_name)
                if value == "Error" or value == "Parse Error":
                     fetch_failed = True; setattr(cam_info.settings, dataclass_attr_name, value)
                     setattr(cam_info.settings, f"{dataclass_attr_name}_choices", []); found_settings[dataclass_attr_name] = value
                     logging.error(f"Failed to get/parse config '{actual_config_name}' for {port}")
                else:
                    setattr(cam_info.settings, dataclass_attr_name, value)
                    setattr(cam_info.settings, f"{dataclass_attr_name}_choices", choices); found_settings[dataclass_attr_name] = value
            else:
                setattr(cam_info.settings, dataclass_attr_name, "N/A")
                setattr(cam_info.settings, f"{dataclass_attr_name}_choices", []); found_settings[dataclass_attr_name] = "N/A"

        if fetch_failed:
             cam_info.status = "Error"; cam_info.last_error = "Failed to get one or more settings."
             logging.error(f"Setting fetch failed for {cam_info.model} ({port}).")
             if status_signal: status_signal.emit(f"Error fetching settings for {cam_info.model}: {cam_info.last_error}")
        else:
            cam_info.status = "Connected"; cam_info.last_error = None
            logging.info(f"Fetched settings for {cam_info.model} ({port}): ISO={found_settings.get('iso', '?')}, Aperture={found_settings.get('aperture', '?')}, Shutter={found_settings.get('shutter_speed', '?')}")
            if status_signal: status_signal.emit(f"{cam_info.model} connected.")

    def _get_config_value_and_choices(self, port: str, config_name: str) -> Tuple[Optional[str], List[str]]:
        """Gets the current value and available choices for a config setting."""
        success, stdout, stderr = self._run_gphoto_command(["--get-config", config_name], port=port, retries=1, timeout=15)
        if not success: logging.error(f"Failed to get config '{config_name}' for {port}: {stderr}"); return "Error", []

        current_value = "Unknown"; choices = []
        try:
            lines = stdout.splitlines(); current_value_raw = None
            for i, line in enumerate(lines):
                line_strip = line.strip(); line_lower = line_strip.lower()
                if line_lower.startswith("current:"):
                    current_value_raw = line.split(":", 1)[1].strip(); current_value = current_value_raw
                elif line_lower.startswith("choice:"):
                    parts = line_strip.split(maxsplit=2)
                    if len(parts) == 3: choice_val = parts[2].strip()
                    elif len(parts) == 2 and not parts[1].isdigit(): choice_val = parts[1].strip()
                    else: choice_val = None
                    if choice_val is not None and choice_val not in choices: choices.append(choice_val)

            if choices and current_value_raw is not None:
                 if current_value_raw in choices: current_value = current_value_raw # Value reported directly
                 else:
                     try: # Try as index
                         current_index = int(current_value_raw)
                         if 0 <= current_index < len(choices): current_value = choices[current_index]
                         else: current_value = current_value_raw # Index out of range, keep raw
                     except (ValueError, TypeError): current_value = current_value_raw # Not index, keep raw
            # No specific handling needed if no choices found, current_value keeps raw value
        except Exception as e:
            logging.error(f"Error parsing config output for {config_name} on {port}: {e}\nOutput:\n{stdout}")
            return "Parse Error", []

        logging.debug(f"Config '{config_name}' on {port}: Value='{current_value}', Choices={choices}")
        return current_value, choices

    def set_camera_setting(self, port: str, setting_type: str, value: str, status_signal=None, **kwargs) -> bool:
        """Sets a specific setting on a camera."""
        if port not in self.cameras: logging.error(f"Cannot set setting for unknown port {port}"); return False
        cam_info = self.cameras[port]
        actual_config_name = self._resolved_config_names.get(port, {}).get(setting_type.lower())
        if not actual_config_name:
            logging.error(f"Cannot set setting '{setting_type}', config name not resolved for port {port}")
            cam_info.last_error = f"Cannot resolve config for {setting_type}"; return False

        logging.info(f"Setting {setting_type} ({actual_config_name}) to '{value}' on {port}")
        if status_signal: status_signal.emit(f"Setting {setting_type} to {value} on {cam_info.model}...")
        cam_info.status = "Applying Settings..."
        config_arg = f"{actual_config_name}={value}"
        success, stdout, stderr = self._run_gphoto_command(["--set-config", config_arg], port=port, retries=1, delay=CAPTURE_RETRY_DELAY, timeout=20)
        dataclass_attr_name = "shutter_speed" if setting_type == "shutterspeed" else setting_type

        if success:
            logging.info(f"Successfully set {setting_type} to {value} on {port}")
            setattr(cam_info.settings, dataclass_attr_name, value)
            cam_info.status = "Connected"; cam_info.last_error = None
            if status_signal: status_signal.emit(f"{setting_type} set to {value} on {cam_info.model}")
            return True
        else:
            logging.error(f"Failed to set {setting_type} to {value} on {port}: {stderr}")
            cam_info.status = "Error"; cam_info.last_error = f"Failed to set {setting_type}: {stderr}"
            if status_signal: status_signal.emit(f"Error setting {setting_type} on {cam_info.model}: {stderr}")
            return False

    def capture_image(self, port: str, save_dir: str = ".", prefix: str = "", status_signal=None, progress_signal=None, **kwargs) -> Optional[str]:
        """Captures an image from a single camera and downloads it."""
        if port not in self.cameras: logging.error(f"Capture called for unknown port: {port}"); return None
        cam_info = self.cameras[port]

        logging.info(f"Initiating capture for {cam_info.model} ({port})...")
        cam_info.status = "Capturing..."
        if status_signal: status_signal.emit(f"Capturing on {cam_info.model}...")

        # Create filename with optional prefix
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_model = re.sub(r'[\\/*?:"<>|\s]+', "_", cam_info.model).strip('_')
        safe_port = port.replace(':', '-').replace(',', '_')
        # --- Filename generation with prefix ---
        base_name = f"{timestamp}_{safe_model}_{safe_port}"
        # Sanitize prefix slightly (remove leading/trailing spaces/underscores)
        safe_prefix = prefix.strip().strip('_')
        filename = f"{safe_prefix}_{base_name}.jpg" if safe_prefix else f"{base_name}.jpg"
        # --- End filename generation ---
        filepath = os.path.abspath(os.path.join(save_dir, filename))

        try: os.makedirs(os.path.dirname(filepath), exist_ok=True)
        except OSError as e:
             logging.error(f"Failed to create save directory '{os.path.dirname(filepath)}': {e}")
             cam_info.status = "Error"; cam_info.last_error = f"Failed to create save directory: {e}"
             if status_signal: status_signal.emit(f"Capture FAILED on {cam_info.model}: Directory error")
             return None

        capture_args = ["--capture-image-and-download", "--filename", filepath, "--force-overwrite"]
        success, stdout, stderr = self._run_gphoto_command(capture_args, port=port, retries=CAPTURE_RETRIES, delay=CAPTURE_RETRY_DELAY, timeout=60)

        capture_success = False
        if success and os.path.exists(filepath) and os.path.getsize(filepath) > 0:
             if "Saving file as" in stdout or "Downloading image to" in stdout or "New file is in location" in stdout: capture_success = True
             elif not stderr or "delete" in stderr.lower(): capture_success = True # Optimistic

        if capture_success:
            logging.info(f"Successfully captured image from {port} to {filepath}")
            cam_info.status = "Connected"; cam_info.last_error = None
            if status_signal: status_signal.emit(f"Captured image from {cam_info.model}")
            return filepath
        else:
            error_msg = stderr
            if not error_msg and not success: error_msg = "Unknown capture error (command failed)"
            elif success and not os.path.exists(filepath): error_msg = "Command succeeded but file not found."
            elif success and os.path.exists(filepath) and os.path.getsize(filepath) == 0: error_msg = "Command succeeded but file is empty."
            elif "Timeout reading from or writing to the port" in stderr: error_msg = "PTP Timeout during capture/download."
            elif "Could not capture" in stderr: error_msg = "Capture error reported by camera/gphoto2." # Specific check

            logging.error(f"Failed to capture image from {port}: {error_msg}\nStdout: {stdout}")
            cam_info.status = "Error"; cam_info.last_error = f"Capture failed: {error_msg}"
            if status_signal: status_signal.emit(f"Capture FAILED on {cam_info.model}: {error_msg}")
            if os.path.exists(filepath):
                try: os.remove(filepath); logging.info(f"Removed potentially incomplete file: {filepath}")
                except OSError as e: logging.warning(f"Could not remove potentially incomplete file {filepath}: {e}")
            return None

    def capture_preview(self, port: str, status_signal=None, **kwargs) -> Optional[bytes]:
         """Captures a preview frame (as bytes). Can be slow!"""
         if port not in self.cameras: return None
         cam_info = self.cameras[port]
         if cam_info.status not in ["Connected"]: logging.debug(f"Skipping preview for {port}, status is {cam_info.status}"); return None

         logging.debug(f"Capturing preview for {cam_info.model} ({port})...")
         command = [GPHOTO2_CMD, "--port", port, "--capture-preview", "--stdout"]
         preview_data = None
         try:
             process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10)
             stderr_text = process.stderr.decode('utf-8', errors='ignore').strip()
             if process.returncode == 0 and process.stdout:
                 logging.debug(f"Preview captured successfully for {port} ({len(process.stdout)} bytes)")
                 preview_data = process.stdout
             else: logging.warning(f"Failed to capture preview for {port} (retcode {process.returncode}). Stderr: {stderr_text}")
         except subprocess.TimeoutExpired: logging.warning(f"Preview command timed out for port {port}")
         except Exception as e: logging.exception(f"Exception capturing preview for port {port}: {e}")
         return preview_data

    def get_camera_status(self, port: str) -> str:
        """Gets the current status string of a camera."""
        return self.cameras.get(port, CameraInfo("Unknown", port, "Disconnected")).status

    def get_connected_cameras(self) -> List[CameraInfo]:
        """Returns a list of cameras currently believed to be connected and ready."""
        return [cam for cam in self.cameras.values() if cam.status == "Connected"]