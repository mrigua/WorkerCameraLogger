# camera_profiles.py
import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

@dataclass
class CameraProfileSettings:
    """Settings stored within a camera profile."""
    iso: Optional[str] = None
    aperture: Optional[str] = None
    shutter_speed: Optional[str] = None
    
    def is_empty(self) -> bool:
        """Check if this profile has any settings defined."""
        return self.iso is None and self.aperture is None and self.shutter_speed is None

@dataclass
class CameraProfile:
    """Represents a named group of camera settings that can be applied to one or more cameras."""
    name: str
    description: str = ""
    settings: CameraProfileSettings = field(default_factory=CameraProfileSettings)
    
    def to_dict(self) -> Dict:
        """Convert profile to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CameraProfile':
        """Create profile from dictionary after deserialization."""
        # Extract the settings separately to create the nested object structure
        settings_data = data.pop('settings', {})
        settings = CameraProfileSettings(**settings_data)
        
        # Create the profile with the remaining data plus settings object
        return cls(**data, settings=settings)


class ProfileManager:
    """Manages saving, loading, and applying camera profiles."""
    
    def __init__(self, profiles_dir: str = "profiles"):
        """Initialize the profile manager with a directory for storing profiles."""
        self.profiles_dir = profiles_dir
        self.profiles: Dict[str, CameraProfile] = {}  # name -> profile
        
        # Flag to indicate if smart detection is enabled
        self.smart_detection_enabled = True
        
        # Smart profile detector (will be initialized lazily when needed)
        self._smart_detector = None
        
        # Ensure the profiles directory exists
        os.makedirs(self.profiles_dir, exist_ok=True)
        
        # Load existing profiles
        self._load_profiles()
    
    def _load_profiles(self):
        """Load all profile files from the profiles directory."""
        self.profiles = {}
        
        if not os.path.exists(self.profiles_dir):
            return
            
        try:
            for filename in os.listdir(self.profiles_dir):
                if filename.endswith('.json'):
                    path = os.path.join(self.profiles_dir, filename)
                    profile = self._load_profile_from_file(path)
                    if profile:
                        self.profiles[profile.name] = profile
        except Exception as e:
            logging.error(f"Error loading profiles: {e}")
    
    def _load_profile_from_file(self, path: str) -> Optional[CameraProfile]:
        """Load a single profile from a file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return CameraProfile.from_dict(data)
        except Exception as e:
            logging.error(f"Error loading profile from {path}: {e}")
            return None
    
    def save_profile(self, profile: CameraProfile) -> bool:
        """Save a profile to disk and add it to the in-memory collection."""
        try:
            # Sanitize the filename
            filename = profile.name.lower().replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{filename}.json"
            path = os.path.join(self.profiles_dir, filename)
            
            # Write to file
            with open(path, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
            
            # Add/update in memory
            self.profiles[profile.name] = profile
            return True
        except Exception as e:
            logging.error(f"Error saving profile {profile.name}: {e}")
            return False
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile from disk and remove it from the in-memory collection."""
        if profile_name not in self.profiles:
            return False
            
        try:
            # Remove from disk
            filename = profile_name.lower().replace(' ', '_').replace('/', '_').replace('\\', '_')
            filename = f"{filename}.json"
            path = os.path.join(self.profiles_dir, filename)
            
            if os.path.exists(path):
                os.remove(path)
            
            # Remove from memory
            del self.profiles[profile_name]
            return True
        except Exception as e:
            logging.error(f"Error deleting profile {profile_name}: {e}")
            return False
    
    def get_profile(self, profile_name: str) -> Optional[CameraProfile]:
        """Get a profile by name."""
        return self.profiles.get(profile_name)
    
    def get_all_profiles(self) -> List[CameraProfile]:
        """Get all available profiles."""
        return list(self.profiles.values())
    
    def get_profile_names(self) -> List[str]:
        """Get a list of all profile names."""
        return list(self.profiles.keys())
    
    def create_default_profiles(self):
        """Create some default profiles if none exist."""
        if self.profiles:
            # Don't overwrite existing profiles
            return
            
        # Create some sensible defaults for common shooting scenarios
        defaults = [
            CameraProfile(
                name="Outdoor Sunny",
                description="Settings for bright outdoor conditions",
                settings=CameraProfileSettings(
                    iso="100",
                    aperture="f/8",
                    shutter_speed="1/500"
                )
            ),
            CameraProfile(
                name="Indoor Low Light",
                description="Settings for indoor low light conditions",
                settings=CameraProfileSettings(
                    iso="800",
                    aperture="f/2.8",
                    shutter_speed="1/60"
                )
            ),
            CameraProfile(
                name="Action/Sports",
                description="High shutter speed for capturing fast action",
                settings=CameraProfileSettings(
                    iso="400",
                    aperture="f/4",
                    shutter_speed="1/1000"
                )
            ),
            CameraProfile(
                name="Landscape",
                description="Maximum depth of field for landscape photography",
                settings=CameraProfileSettings(
                    iso="100",
                    aperture="f/11",
                    shutter_speed="1/125"
                )
            ),
            CameraProfile(
                name="Portrait",
                description="Shallow depth of field for portrait photography",
                settings=CameraProfileSettings(
                    iso="200",
                    aperture="f/2.8",
                    shutter_speed="1/250"
                )
            )
        ]
        
        # Save each default profile
        for profile in defaults:
            self.save_profile(profile)
        
        logging.info(f"Created {len(defaults)} default profiles")


# --- Smart Profile Detection Methods ---

    def _get_smart_detector(self):
        """Lazily initialize and return the smart profile detector."""
        if self._smart_detector is None:
            try:
                # Import here to avoid circular import issues
                from attached_assets.smart_profile_detection import SmartProfileDetector
                self._smart_detector = SmartProfileDetector(self)
                logging.info("Smart profile detection initialized")
            except ImportError:
                try:
                    from smart_profile_detection import SmartProfileDetector
                    self._smart_detector = SmartProfileDetector(self)
                    logging.info("Smart profile detection initialized")
                except ImportError:
                    logging.error("Failed to import SmartProfileDetector")
                    return None
        return self._smart_detector
    
    def detect_profile(self, camera_info):
        """
        Automatically detect and return the most suitable profile for a camera.
        
        Args:
            camera_info: Camera information object
            
        Returns:
            Tuple of (detected profile or None, confidence level)
        """
        if not self.smart_detection_enabled:
            return None, 0.0
            
        smart_detector = self._get_smart_detector()
        if not smart_detector:
            return None, 0.0
            
        return smart_detector.detect_profile(camera_info, camera_info.port)
    
    def get_suggested_profiles(self, camera_info):
        """
        Get a list of suggested profiles for a camera, ordered by match score.
        
        Args:
            camera_info: Camera information object
            
        Returns:
            List of (profile, confidence) tuples
        """
        if not self.smart_detection_enabled:
            return [(profile, 0.0) for profile in self.get_all_profiles()]
            
        smart_detector = self._get_smart_detector()
        if not smart_detector:
            return [(profile, 0.0) for profile in self.get_all_profiles()]
            
        return smart_detector.get_suggested_profiles(camera_info)
    
    def learn_from_assignment(self, camera_info, profile):
        """
        Learn from a manual profile assignment to improve future detection.
        
        Args:
            camera_info: Camera information object
            profile: The profile that was manually assigned
        """
        if not self.smart_detection_enabled:
            return
            
        smart_detector = self._get_smart_detector()
        if smart_detector:
            smart_detector.learn_from_assignment(camera_info, profile)
    
    def set_smart_detection_enabled(self, enabled):
        """
        Enable or disable smart profile detection.
        
        Args:
            enabled: Boolean indicating whether smart detection should be enabled
        """
        self.smart_detection_enabled = enabled
        logging.info(f"Smart profile detection {'enabled' if enabled else 'disabled'}")

# Global instance
profile_manager = ProfileManager()