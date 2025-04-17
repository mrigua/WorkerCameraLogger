#!/usr/bin/env python3
# smart_profile_detection.py - Smart detection of camera profiles based on camera models and settings

import os
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from datetime import datetime

# Local imports
try:
    from camera_profiles import CameraProfile, ProfileManager, CameraProfileSettings
    from camera_manager import CameraInfo, CameraSettings
except ImportError:
    # Handle import when running from parent directory
    from attached_assets.camera_profiles import CameraProfile, ProfileManager, CameraProfileSettings
    from attached_assets.camera_manager import CameraInfo, CameraSettings


@dataclass
class CameraSignature:
    """Represents a unique signature for camera identification and matching."""
    model: str = ""
    settings_hash: str = ""  # Hash of critical settings to identify a camera setup
    last_seen: datetime = field(default_factory=datetime.now)
    profile_names: List[str] = field(default_factory=list)
    manual_assignment: bool = False  # True if manually assigned
    confidence: float = 0.0  # Confidence level of profile match (0.0-1.0)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "model": self.model,
            "settings_hash": self.settings_hash,
            "last_seen": self.last_seen.isoformat(),
            "profile_names": self.profile_names,
            "manual_assignment": self.manual_assignment,
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CameraSignature':
        """Create from dictionary after deserialization."""
        sig = cls(
            model=data.get("model", ""),
            settings_hash=data.get("settings_hash", ""),
            profile_names=data.get("profile_names", []),
            manual_assignment=data.get("manual_assignment", False),
            confidence=data.get("confidence", 0.0)
        )
        if "last_seen" in data:
            try:
                sig.last_seen = datetime.fromisoformat(data["last_seen"])
            except (ValueError, TypeError):
                sig.last_seen = datetime.now()
        return sig


class SmartProfileDetector:
    """
    Detects and manages camera profiles based on camera models and settings.
    
    Features:
    - Auto-detection of suitable profiles when a camera is connected
    - Learning from user profile assignments
    - Fast profile suggestions based on camera model and current settings
    - Confidence-based ranking of potential profile matches
    """
    
    def __init__(self, 
                 profile_manager: ProfileManager,
                 signatures_dir: str = "profiles/signatures",
                 confidence_threshold: float = 0.7):
        """
        Initialize the smart profile detector.
        
        Args:
            profile_manager: The profile manager instance to use for profile retrieval and application
            signatures_dir: Directory to store camera signatures
            confidence_threshold: Minimum confidence threshold for automatic profile application
        """
        self.profile_manager = profile_manager
        self.signatures_dir = signatures_dir
        self.confidence_threshold = confidence_threshold
        
        # Dictionary of camera signatures by camera ID (port or unique identifier)
        self.camera_signatures: Dict[str, CameraSignature] = {}
        
        # Ensure the signatures directory exists
        os.makedirs(self.signatures_dir, exist_ok=True)
        
        # Load previously saved signatures
        self._load_signatures()
    
    def _create_settings_hash(self, camera_info: CameraInfo) -> str:
        """
        Create a hash string from camera settings that uniquely identifies its setup.
        
        Args:
            camera_info: The camera information object
            
        Returns:
            A hash string representing the camera's key settings
        """
        settings = camera_info.settings
        hash_components = []
        
        # Add any distinguishing settings to the hash
        # This can be expanded with more settings as needed
        if settings.iso:
            hash_components.append(f"iso:{settings.iso}")
        if settings.aperture:
            hash_components.append(f"ap:{settings.aperture}")
        if settings.shutter_speed:
            hash_components.append(f"ss:{settings.shutter_speed}")
            
        # You can add more identifying factors here
        
        # Sort to ensure consistent hashing regardless of order
        hash_components.sort()
        return "|".join(hash_components)
    
    def _load_signatures(self):
        """Load all camera signatures from the signatures directory."""
        self.camera_signatures = {}
        
        if not os.path.exists(self.signatures_dir):
            logging.info(f"Creating signatures directory at {self.signatures_dir}")
            os.makedirs(self.signatures_dir, exist_ok=True)
            return
            
        for filename in os.listdir(self.signatures_dir):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(self.signatures_dir, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    # The filename without extension is the camera ID
                    camera_id = os.path.splitext(filename)[0]
                    
                    # Create signature from data
                    signature = CameraSignature.from_dict(data)
                    self.camera_signatures[camera_id] = signature
                    
                    logging.debug(f"Loaded camera signature for {camera_id}: {signature.model}")
                except Exception as e:
                    logging.error(f"Error loading camera signature from {filename}: {e}")
    
    def _save_signature(self, camera_id: str, signature: CameraSignature):
        """
        Save a camera signature to disk.
        
        Args:
            camera_id: The camera identifier
            signature: The signature to save
        """
        try:
            # Update the last seen timestamp
            signature.last_seen = datetime.now()
            
            # Prepare the file path
            filename = f"{camera_id}.json"
            filepath = os.path.join(self.signatures_dir, filename)
            
            # Convert to dictionary and save as JSON
            with open(filepath, 'w') as f:
                json.dump(signature.to_dict(), f, indent=2)
                
            logging.debug(f"Saved camera signature for {camera_id}: {signature.model}")
        except Exception as e:
            logging.error(f"Error saving camera signature for {camera_id}: {e}")
    
    def detect_profile(self, camera_info: CameraInfo, camera_id: str) -> Tuple[Optional[CameraProfile], float]:
        """
        Detect and return the best matching profile for a camera.
        
        Args:
            camera_info: The camera information object
            camera_id: The unique identifier for the camera (typically the port)
            
        Returns:
            Tuple of (best matching profile or None, confidence level)
        """
        # Get or create camera signature
        signature = self._get_or_create_signature(camera_info, camera_id)
        
        # If we have a manual assignment with high confidence, return it immediately
        if signature.manual_assignment and signature.profile_names and signature.confidence > 0.9:
            profile_name = signature.profile_names[0]
            profile = self.profile_manager.get_profile(profile_name)
            if profile:
                logging.info(f"Using manually assigned profile '{profile_name}' for {camera_info.model}")
                return profile, signature.confidence
        
        # Otherwise, find the best matching profile
        return self._find_best_profile_match(camera_info, signature)
    
    def _get_or_create_signature(self, camera_info: CameraInfo, camera_id: str) -> CameraSignature:
        """
        Get an existing camera signature or create a new one.
        
        Args:
            camera_info: The camera information object
            camera_id: The unique identifier for the camera
            
        Returns:
            The camera signature (existing or newly created)
        """
        # Create a settings hash
        settings_hash = self._create_settings_hash(camera_info)
        
        # Check if we already have a signature for this camera
        if camera_id in self.camera_signatures:
            # Update the existing signature with current info
            signature = self.camera_signatures[camera_id]
            signature.model = camera_info.model
            signature.settings_hash = settings_hash
            signature.last_seen = datetime.now()
            return signature
        
        # Create a new signature
        signature = CameraSignature(
            model=camera_info.model,
            settings_hash=settings_hash
        )
        self.camera_signatures[camera_id] = signature
        
        # Save the new signature
        self._save_signature(camera_id, signature)
        
        return signature
    
    def _find_best_profile_match(self, camera_info: CameraInfo, signature: CameraSignature) -> Tuple[Optional[CameraProfile], float]:
        """
        Find the best matching profile for a camera.
        
        Args:
            camera_info: The camera information object
            signature: The camera signature
            
        Returns:
            Tuple of (best matching profile or None, confidence level)
        """
        # Get all available profiles
        profiles = self.profile_manager.get_all_profiles()
        if not profiles:
            logging.warning("No profiles available for matching")
            return None, 0.0
        
        # Calculate match scores for each profile
        scored_profiles = []
        for profile in profiles:
            score = self._calculate_profile_match_score(camera_info, profile)
            scored_profiles.append((profile, score))
        
        # Sort by score in descending order
        scored_profiles.sort(key=lambda x: x[1], reverse=True)
        
        # Get the best match
        best_profile, best_score = scored_profiles[0] if scored_profiles else (None, 0.0)
        
        # Only return if the confidence is above threshold
        if best_score >= self.confidence_threshold:
            # Update signature with this profile if it's a good match
            if best_profile and best_profile.name not in signature.profile_names:
                signature.profile_names.insert(0, best_profile.name)
                signature.confidence = best_score
                self._save_signature(camera_info.port, signature)
                
            logging.info(f"Auto-detected profile '{best_profile.name}' for {camera_info.model} with {best_score:.2f} confidence")
            return best_profile, best_score
        
        logging.debug(f"No suitable profile found for {camera_info.model} (best score: {best_score:.2f})")
        return None, best_score
    
    def _calculate_profile_match_score(self, camera_info: CameraInfo, profile: CameraProfile) -> float:
        """
        Calculate how well a profile matches a camera's characteristics.
        
        Args:
            camera_info: The camera information object
            profile: The profile to evaluate
            
        Returns:
            A score between 0.0 and 1.0, where 1.0 is a perfect match
        """
        score = 0.0
        total_factors = 0
        
        # Check camera model match (worth 30% of total score)
        model_match_score = self._calculate_model_match_score(camera_info.model, profile.name)
        score += model_match_score * 0.3
        total_factors += 0.3
        
        # Check settings match (worth 70% of total score)
        settings_match_score = self._calculate_settings_match_score(camera_info.settings, profile.settings)
        score += settings_match_score * 0.7
        total_factors += 0.7
        
        # Normalize score
        if total_factors > 0:
            score = score / total_factors
        
        return score
    
    def _calculate_model_match_score(self, camera_model: str, profile_name: str) -> float:
        """
        Calculate a match score based on how well the camera model matches the profile name.
        
        Args:
            camera_model: The camera model string
            profile_name: The profile name
            
        Returns:
            A score between 0.0 and 1.0
        """
        # Normalize strings for comparison
        camera_model = camera_model.lower().replace(' ', '')
        profile_name = profile_name.lower().replace(' ', '')
        
        # Extract common brand names to check for
        common_brands = {'sony', 'canon', 'nikon', 'fuji', 'panasonic', 'olympus', 'pentax', 'leica'}
        found_brands = set()
        
        for brand in common_brands:
            if brand in camera_model:
                found_brands.add(brand)
            if brand in profile_name:
                found_brands.add(brand)
        
        # Brand match bonus
        brand_match_score = 0.0
        for brand in found_brands:
            if brand in camera_model and brand in profile_name:
                brand_match_score = 0.5
                break
        
        # Model number match (e.g., "RX100", "5D", etc.)
        model_number_match_score = 0.0
        
        # Extract model numbers using regex pattern for alphanumeric sequences
        camera_model_numbers = re.findall(r'([a-z]+\d+|\d+[a-z]*)', camera_model)
        profile_model_numbers = re.findall(r'([a-z]+\d+|\d+[a-z]*)', profile_name)
        
        # Check for overlapping model numbers
        common_numbers = set(camera_model_numbers) & set(profile_model_numbers)
        if common_numbers:
            model_number_match_score = 0.5
            
        # Combine scores
        return brand_match_score + model_number_match_score
    
    def _calculate_settings_match_score(self, camera_settings: CameraSettings, profile_settings: CameraProfileSettings) -> float:
        """
        Calculate a match score based on how well the camera settings match the profile settings.
        
        Args:
            camera_settings: The current camera settings
            profile_settings: The profile settings
            
        Returns:
            A score between 0.0 and 1.0
        """
        score = 0.0
        factors = 0
        
        # Check ISO match
        if profile_settings.iso is not None and camera_settings.iso is not None:
            # Exact match
            if profile_settings.iso == camera_settings.iso:
                score += 1.0
            # Close match (within the same general range)
            elif self._are_iso_values_similar(profile_settings.iso, camera_settings.iso):
                score += 0.5
            factors += 1
            
        # Check aperture match
        if profile_settings.aperture is not None and camera_settings.aperture is not None:
            # Exact match
            if profile_settings.aperture == camera_settings.aperture:
                score += 1.0
            # Close match (within one stop)
            elif self._are_aperture_values_similar(profile_settings.aperture, camera_settings.aperture):
                score += 0.5
            factors += 1
            
        # Check shutter speed match
        if profile_settings.shutter_speed is not None and camera_settings.shutter_speed is not None:
            # Exact match
            if profile_settings.shutter_speed == camera_settings.shutter_speed:
                score += 1.0
            # Close match (within one stop)
            elif self._are_shutter_speed_values_similar(profile_settings.shutter_speed, camera_settings.shutter_speed):
                score += 0.5
            factors += 1
            
        # Normalize score
        if factors > 0:
            score = score / factors
            
        return score
    
    def _are_iso_values_similar(self, iso1: str, iso2: str) -> bool:
        """
        Check if two ISO values are similar (within the same range).
        
        Args:
            iso1: First ISO value
            iso2: Second ISO value
            
        Returns:
            True if similar, False otherwise
        """
        try:
            # Extract numeric part of ISO values
            num1 = int(''.join(filter(str.isdigit, iso1)))
            num2 = int(''.join(filter(str.isdigit, iso2)))
            
            # Check if they are within the same general range (within one stop)
            return abs(num1 / num2) < 2.0 if num2 != 0 else False
        except (ValueError, ZeroDivisionError):
            return False
    
    def _are_aperture_values_similar(self, ap1: str, ap2: str) -> bool:
        """
        Check if two aperture values are similar (within one stop).
        
        Args:
            ap1: First aperture value
            ap2: Second aperture value
            
        Returns:
            True if similar, False otherwise
        """
        try:
            # Extract numeric part of aperture values (e.g., '2.8' from 'f/2.8')
            num1 = float(''.join(c for c in ap1 if c.isdigit() or c == '.'))
            num2 = float(''.join(c for c in ap2 if c.isdigit() or c == '.'))
            
            # Check if they are within one stop
            stop_difference = abs(log2(num1 / num2)) if num2 != 0 else float('inf')
            return stop_difference < 1.0
        except (ValueError, ZeroDivisionError):
            return False
    
    def _are_shutter_speed_values_similar(self, ss1: str, ss2: str) -> bool:
        """
        Check if two shutter speed values are similar (within one stop).
        
        Args:
            ss1: First shutter speed value
            ss2: Second shutter speed value
            
        Returns:
            True if similar, False otherwise
        """
        try:
            # Convert shutter speeds to seconds
            sec1 = self._shutter_speed_to_seconds(ss1)
            sec2 = self._shutter_speed_to_seconds(ss2)
            
            # Check if they are within one stop
            stop_difference = abs(log2(sec1 / sec2)) if sec2 != 0 else float('inf')
            return stop_difference < 1.0
        except (ValueError, ZeroDivisionError):
            return False
    
    def _shutter_speed_to_seconds(self, shutter_speed: str) -> float:
        """
        Convert shutter speed string to seconds.
        
        Args:
            shutter_speed: Shutter speed as string (e.g., "1/250", "30", "2")
            
        Returns:
            Shutter speed in seconds
        """
        try:
            if '/' in shutter_speed:
                # Fraction format (e.g., "1/250")
                numerator, denominator = shutter_speed.split('/')
                return float(numerator) / float(denominator)
            else:
                # Direct seconds format (e.g., "30", "2")
                return float(shutter_speed)
        except (ValueError, ZeroDivisionError):
            # Default to 1 second if we can't parse
            return 1.0
    
    def learn_from_assignment(self, camera_info: CameraInfo, profile: CameraProfile):
        """
        Learn from a manual profile assignment.
        
        Args:
            camera_info: The camera information object
            profile: The profile that was manually assigned
        """
        camera_id = camera_info.port
        
        # Get or create the camera signature
        signature = self._get_or_create_signature(camera_info, camera_id)
        
        # Update with the manual assignment
        if profile.name not in signature.profile_names:
            signature.profile_names.insert(0, profile.name)
        elif signature.profile_names[0] != profile.name:
            # Move to the first position if it's already in the list
            signature.profile_names.remove(profile.name)
            signature.profile_names.insert(0, profile.name)
            
        signature.manual_assignment = True
        signature.confidence = 1.0  # High confidence for manual assignments
        
        # Save the updated signature
        self._save_signature(camera_id, signature)
        
        logging.info(f"Learned manual profile assignment: '{profile.name}' for {camera_info.model}")
    
    def get_suggested_profiles(self, camera_info: CameraInfo) -> List[Tuple[CameraProfile, float]]:
        """
        Get a list of suggested profiles for a camera, sorted by match score.
        
        Args:
            camera_info: The camera information object
            
        Returns:
            List of (profile, score) tuples sorted by descending score
        """
        # Get all available profiles
        profiles = self.profile_manager.get_all_profiles()
        if not profiles:
            return []
        
        # Calculate match scores for each profile
        scored_profiles = []
        for profile in profiles:
            score = self._calculate_profile_match_score(camera_info, profile)
            scored_profiles.append((profile, score))
        
        # Sort by score in descending order
        scored_profiles.sort(key=lambda x: x[1], reverse=True)
        
        return scored_profiles

# Helper function for aperture and shutter speed calculations
def log2(x):
    """Calculate log base 2 of x."""
    import math
    return math.log(x, 2) if x > 0 else 0