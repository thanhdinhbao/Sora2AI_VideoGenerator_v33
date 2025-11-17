#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Profile Manager for Sora2 Video Generator - CREDITS SYSTEM
Manages Chrome profiles rotation and daily credits tracking

✅ NEW SORA2 CREDITS SYSTEM:
- Video 10s = 1 credit
- Video 15s = 2 credits  
- Quota limit = 30 credits/day (not 30 videos)
- Smart credit calculation based on duration
"""

import os
import os
import threading
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


def calculate_credits(duration_seconds: int) -> int:
    """
    Calculate credits required based on video duration
    
    Sora2 Credits Rules:
    - 10s video = 1 credit
    - 15s video = 2 credits
    - Future: scale accordingly
    
    Args:
        duration_seconds: Video duration in seconds
        
    Returns:
        Number of credits required
    """
    if duration_seconds <= 10:
        return 1
    elif duration_seconds <= 15:
        return 2
    else:
        # Future-proof: scale for longer videos
        # Assume 10s = 1 credit base rate
        return max(1, (duration_seconds + 9) // 10)


@dataclass
class ProfileInfo:
    """Information about a Chrome profile with credits tracking"""
    profile_id: int  # 1, 2, 3...
    profile_name: str  # "Profile_1", "Profile_2"...
    profile_path: str  # Path to Chrome profile directory
    credits_used_today: int = 0  # ✅ Credits used today (not video count)
    max_credits_per_day: int = 30  # ✅ Daily credit quota (not video count)
    last_used: str = ""  # Last used datetime (ISO format)
    total_credits_used: int = 0  # ✅ Total credits used all time
    total_videos_generated: int = 0  # Total number of videos (for stats)
    is_active: bool = True  # Profile is active and can be used
    
    def can_generate(self, credits_needed: int = 1) -> bool:
        """
        Check if profile has enough credits to generate video
        
        Args:
            credits_needed: Number of credits required for the video
            
        Returns:
            True if profile can generate, False otherwise
        """
        return self.is_active and (self.credits_used_today + credits_needed) <= self.max_credits_per_day
    
    def remaining_credits(self) -> int:
        """Get remaining credits for today"""
        return max(0, self.max_credits_per_day - self.credits_used_today)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ProfileInfo':
        """
        Create from dictionary with backward compatibility
        
        Handles migration from old 'videos_today' field to 'credits_used_today'
        """
        # Backward compatibility: convert old field names
        if 'videos_today' in data and 'credits_used_today' not in data:
            data['credits_used_today'] = data.pop('videos_today')
            logger.info(f"[MIGRATION] Converted videos_today to credits_used_today for {data.get('profile_name')}")
        
        if 'max_videos_per_day' in data and 'max_credits_per_day' not in data:
            data['max_credits_per_day'] = data.pop('max_videos_per_day')
        
        if 'total_videos' in data and 'total_credits_used' not in data:
            data['total_credits_used'] = data.pop('total_videos')
        
        # Set default for new field
        if 'total_videos_generated' not in data:
            data['total_videos_generated'] = 0
        
        return cls(**data)


class ProfileManager:
    """
    Manages multiple Chrome profiles for Sora2 video generation with CREDITS SYSTEM
    
    Features:
    - ✅ Credits-based quota (not video count)
    - ✅ Smart credit calculation (10s=1, 15s=2)
    - Auto-rotation when quota reached
    - Daily quota reset at midnight
    - Profile usage tracking
    - License-based profile limit
    - Auto-create profiles
    """
    
    def __init__(self, 
                 profiles_base_dir: str = None,
                 max_profiles: int = 5,
                 data_file: str = "profile_usage.json"):
        """
        Initialize ProfileManager with Credits System
        
        Args:
            profiles_base_dir: Base directory containing Chrome profiles
            max_profiles: Maximum number of profiles allowed (from license)
            data_file: JSON file to store profile usage data
        """
        # Setup paths
        if profiles_base_dir is None:
            # Default Chrome profile location on Windows
            user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
            self.profiles_base_dir = Path(user_data)
        else:
            self.profiles_base_dir = Path(profiles_base_dir)
        
        # Ensure base directory exists
        self.profiles_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.data_file = Path(__file__).parent / data_file
        self.max_profiles = max_profiles
        
        # Profile storage
        self.profiles: List[ProfileInfo] = []
        self.current_profile_index = 0
        self._lock = threading.Lock()  # Thread safety
        
        # Load existing data
        self._load_profiles()
        
        # Check if we need to reset daily counters
        self._check_daily_reset()
        
        logger.info(f"[PROFILE] ✅ Initialized CREDITS SYSTEM with {len(self.profiles)} profiles")
        logger.info(f"[PROFILE] Max profiles allowed: {self.max_profiles}")
        logger.info(f"[PROFILE] Credits quota: 30 credits/day (10s=1, 15s=2)")
        logger.info(f"[PROFILE] Base directory: {self.profiles_base_dir}")
    
    def _load_profiles(self):
        """Load profile data from JSON file with migration support"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Load profiles with automatic migration
                    for profile_data in data.get('profiles', []):
                        profile = ProfileInfo.from_dict(profile_data)
                        self.profiles.append(profile)
                    
                    # Load current index
                    self.current_profile_index = data.get('current_profile_index', 0)
                    
                    logger.info(f"[PROFILE] Loaded {len(self.profiles)} profiles from {self.data_file}")
            except Exception as e:
                logger.error(f"[PROFILE] Error loading profiles: {e}")
                self.profiles = []
        else:
            logger.info("[PROFILE] No existing profile data found")
            # Try to discover existing profiles
            self._discover_profiles()
    
    def _save_profiles(self):
        """Save profile data to JSON file"""
        try:
            data = {
                'profiles': [p.to_dict() for p in self.profiles],
                'current_profile_index': self.current_profile_index,
                'last_saved': datetime.now().isoformat(),
                'credits_system_version': '2.0'  # Version tracking
            }
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"[PROFILE] Saved {len(self.profiles)} profiles")
        except Exception as e:
            logger.error(f"[PROFILE] Error saving profiles: {e}")
    
    def _discover_profiles(self):
        """Auto-discover Chrome profiles in base directory"""
        if not self.profiles_base_dir.exists():
            logger.warning(f"[PROFILE] Base directory not found: {self.profiles_base_dir}")
            return
        
        discovered = 0
        
        # Look for Profile_1, Profile_2, Profile_3...
        for i in range(1, self.max_profiles + 1):
            profile_name = f"Profile_{i}"
            profile_path = self.profiles_base_dir / profile_name
            
            if profile_path.exists() and profile_path.is_dir():
                # Check if already in list
                if not any(p.profile_name == profile_name for p in self.profiles):
                    profile = ProfileInfo(
                        profile_id=i,
                        profile_name=profile_name,
                        profile_path=str(profile_path),
                        credits_used_today=0,
                        max_credits_per_day=30,
                        last_used="",
                        total_credits_used=0,
                        total_videos_generated=0,
                        is_active=True
                    )
                    self.profiles.append(profile)
                    discovered += 1
                    logger.info(f"[PROFILE] Discovered: {profile_name}")
        
        # Also check for "Default" profile
        default_path = self.profiles_base_dir / "Default"
        if default_path.exists() and default_path.is_dir():
            if not any(p.profile_name == "Default" for p in self.profiles):
                profile = ProfileInfo(
                    profile_id=0,
                    profile_name="Default",
                    profile_path=str(default_path),
                    credits_used_today=0,
                    max_credits_per_day=30,
                    last_used="",
                    total_credits_used=0,
                    total_videos_generated=0,
                    is_active=True
                )
                self.profiles.insert(0, profile)
                discovered += 1
                logger.info(f"[PROFILE] Discovered: Default")
        
        if discovered > 0:
            self._save_profiles()
            logger.info(f"[PROFILE] Auto-discovered {discovered} profiles")
    
    def _check_daily_reset(self):
        """Check if we need to reset daily counters (at midnight)"""
        if not self.profiles:
            return
        
        # Get last used date from any profile
        last_dates = [p.last_used for p in self.profiles if p.last_used]
        if not last_dates:
            return
        
        try:
            # Get most recent usage date
            most_recent = max(datetime.fromisoformat(d) for d in last_dates)
            today = datetime.now().date()
            last_date = most_recent.date()
            
            # If last usage was yesterday or earlier, reset counters
            if last_date < today:
                logger.info(f"[PROFILE] Resetting daily credits (last usage: {last_date})")
                for profile in self.profiles:
                    profile.credits_used_today = 0
                self.current_profile_index = 0  # ← THÊM DÒNG NÀY
                self._save_profiles()
        except Exception as e:
            logger.error(f"[PROFILE] Error checking daily reset: {e}")
    
    # ========================================================================
    # ✅ CREDITS SYSTEM - Core Methods
    # ========================================================================
    
    def get_current_profile(self) -> Optional[ProfileInfo]:
        """Get the currently active profile"""
        if not self.profiles:
            logger.error("[PROFILE] No profiles available!")
            return None
        
        if self.current_profile_index >= len(self.profiles):
            self.current_profile_index = 0
        
        return self.profiles[self.current_profile_index]
    
    def get_next_available_profile(self, duration_seconds: int = 10) -> Optional[ProfileInfo]:
        """
        Get next available profile with enough credits for the video
        
        Args:
            duration_seconds: Video duration to calculate required credits
            
        Returns:
            ProfileInfo if available, None if all profiles exhausted
        """
        with self._lock:  # ✅ THREAD SAFE
            if not self.profiles:
                logger.error("[PROFILE] No profiles configured!")
                return None
            
            credits_needed = calculate_credits(duration_seconds)
            logger.info(f"[PROFILE] Looking for profile with {credits_needed} credits (duration: {duration_seconds}s)")
            
            # Check current profile first
            current = self.get_current_profile()
            if current and current.can_generate(credits_needed):
                return current
            
            # Try to find next available profile
            attempts = len(self.profiles)
            for _ in range(attempts):
                self.current_profile_index = (self.current_profile_index + 1) % len(self.profiles)
                profile = self.profiles[self.current_profile_index]
                
                if profile.can_generate(credits_needed):
                    logger.info(f"[PROFILE] Switched to {profile.profile_name} (Remaining: {profile.remaining_credits()} credits)")
                    self._save_profiles()
                    return profile
            
            # All profiles exhausted
            logger.warning(f"[PROFILE] ❌ All profiles exhausted! Need {credits_needed} credits but no profile available")
            return None
    
    def increment_usage(self, profile: ProfileInfo, duration_seconds: int = 10) -> bool:
        """
        Increment usage counter for a profile after successful generation
        
        Args:
            profile: ProfileInfo to increment
            duration_seconds: Duration of generated video to calculate credits
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:  # ✅ THREAD SAFE
            try:
                credits_used = calculate_credits(duration_seconds)
                
                profile.credits_used_today += credits_used
                profile.total_credits_used += credits_used
                profile.total_videos_generated += 1
                profile.last_used = datetime.now().isoformat()
                
                logger.info(f"[PROFILE] ✅ {profile.profile_name}: Used {credits_used} credits ({duration_seconds}s video)")
                logger.info(f"[PROFILE]    Today: {profile.credits_used_today}/{profile.max_credits_per_day} credits | Videos: {profile.total_videos_generated}")
                
                self._save_profiles()
                return True
            except Exception as e:
                logger.error(f"[PROFILE] Error incrementing usage: {e}")
                return False
    
    def can_generate_video(self, duration_seconds: int = 10) -> Tuple[bool, str]:
        """
        Check if any profile can generate video of given duration
        
        Args:
            duration_seconds: Video duration in seconds
            
        Returns:
            Tuple of (can_generate, message)
        """
        credits_needed = calculate_credits(duration_seconds)
        
        for profile in self.profiles:
            if profile.can_generate(credits_needed):
                return True, f"✅ Can generate {duration_seconds}s video ({credits_needed} credits)"
        
        return False, f"❌ No profile has {credits_needed} credits for {duration_seconds}s video"
    
    # ========================================================================
    # Profile Creation Methods
    # ========================================================================
    
    def create_profile(self, profile_id: int, profile_name: str = None) -> Optional[ProfileInfo]:
        """
        Create a single Chrome profile with full structure
        
        Args:
            profile_id: Profile ID (e.g., 1, 2, 3...)
            profile_name: Optional custom name (default: "Profile_{id}")
        
        Returns:
            ProfileInfo if successful, None otherwise
        """
        try:
            if profile_name is None:
                profile_name = f"Profile_{profile_id}"
            
            profile_path = self.profiles_base_dir / profile_name
            
            # Check if already exists
            if profile_path.exists():
                logger.warning(f"[PROFILE] {profile_name} already exists at {profile_path}")
                existing = self.get_profile_by_name(profile_name)
                if existing:
                    return existing
            
            # Create main profile directory
            profile_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"[PROFILE] Created directory: {profile_path}")
            
            # ====================================================================
            # CREATE CHROME PROFILE STRUCTURE
            # ====================================================================
            
            # 1. Create Default subdirectory (REQUIRED by Chrome)
            default_dir = profile_path / "Default"
            default_dir.mkdir(exist_ok=True)
            
            # 2. Create essential subdirectories
            essential_dirs = [
                "Cache",
                "Code Cache",
                "GPUCache",
                "Service Worker",
                "Local Storage",
                "Session Storage",
                "IndexedDB",
                "Extensions",
                "Storage",
                "Sync Data"
            ]
            
            for dir_name in essential_dirs:
                (default_dir / dir_name).mkdir(exist_ok=True)
            
            logger.info(f"[PROFILE] Created {len(essential_dirs)} subdirectories")
            
            # 3. Create Preferences file (CRITICAL)
            prefs = {
                "profile": {
                    "name": profile_name,
                    "created_by_version": "131.0.6778.86",
                    "is_using_default_name": False,
                    "default_content_setting_values": {
                        "notifications": 2  # Block notifications
                    },
                    "content_settings": {
                        "exceptions": {
                            "notifications": {}
                        }
                    }
                },
                "browser": {
                    "has_seen_welcome_page": True,
                    "check_default_browser": False,
                    "show_home_button": False
                },
                "download": {
                    "prompt_for_download": False,
                    "directory_upgrade": True,
                    "extensions_to_open": ""
                },
                "safebrowsing": {
                    "enabled": True
                },
                "autofill": {
                    "enabled": True
                },
                "translate": {
                    "enabled": False
                },
                "credentials_enable_service": False,
                "profile_network_context_service": {
                    "http_cache_enabled": True
                }
            }
            
            prefs_file = default_dir / "Preferences"
            with open(prefs_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=2)
            
            logger.info(f"[PROFILE] Created Preferences file")
            
            # 4. Create Local State file (in parent directory)
            local_state_file = profile_path / "Local State"
            if not local_state_file.exists():
                local_state = {
                    "profile": {
                        "info_cache": {
                            "Default": {
                                "name": profile_name,
                                "shortcut_name": profile_name,
                                "is_using_default_name": False,
                                "background_apps": False,
                                "gaia_given_name": "",
                                "gaia_name": ""
                            }
                        },
                        "profiles_created": 1,
                        "last_used": "Default"
                    },
                    "browser": {
                        "enabled_labs_experiments": []
                    }
                }
                
                with open(local_state_file, 'w', encoding='utf-8') as f:
                    json.dump(local_state, f, indent=2)
                
                logger.info(f"[PROFILE] Created Local State file")
            
            # 5. Create Secure Preferences (optional but recommended)
            secure_prefs = {
                "profile": {
                    "name": profile_name
                }
            }
            
            secure_prefs_file = default_dir / "Secure Preferences"
            with open(secure_prefs_file, 'w', encoding='utf-8') as f:
                json.dump(secure_prefs, f, indent=2)
            
            # 6. Create empty cookies file
            cookies_file = default_dir / "Cookies"
            cookies_file.touch()
            
            # 7. Create empty History file
            history_file = default_dir / "History"
            history_file.touch()
            
            # 8. Create Bookmarks file
            bookmarks = {
                "roots": {
                    "bookmark_bar": {
                        "children": [],
                        "name": "Bookmarks bar",
                        "type": "folder"
                    },
                    "other": {
                        "children": [],
                        "name": "Other bookmarks",
                        "type": "folder"
                    },
                    "synced": {
                        "children": [],
                        "name": "Mobile bookmarks",
                        "type": "folder"
                    }
                },
                "version": 1
            }
            
            bookmarks_file = default_dir / "Bookmarks"
            with open(bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(bookmarks, f, indent=2)
            
            logger.info(f"[PROFILE] Created Bookmarks file")
            
            # 9. Create First Run file (tells Chrome this is first run)
            first_run_file = profile_path / "First Run"
            first_run_file.touch()
            
            logger.info(f"[PROFILE] ✅ Created complete Chrome profile structure")
            
            # ====================================================================
            # CREATE ProfileInfo OBJECT
            # ====================================================================
            
            profile = ProfileInfo(
                profile_id=profile_id,
                profile_name=profile_name,
                profile_path=str(profile_path),
                credits_used_today=0,
                max_credits_per_day=30,
                last_used="",
                total_credits_used=0,
                total_videos_generated=0,
                is_active=True
            )
            
            # Add to list if not already there
            if not any(p.profile_name == profile_name for p in self.profiles):
                self.profiles.append(profile)
                self._save_profiles()
            
            logger.info(f"[PROFILE] ✅ Profile ready: {profile_name}")
            return profile
            
        except Exception as e:
            logger.error(f"[PROFILE] Failed to create {profile_name}: {e}", exc_info=True)
            return None
    
    def create_multiple_profiles(self, count: int) -> Tuple[List[ProfileInfo], List[str]]:
        """
        Create multiple Chrome profiles WITHOUT overwriting existing ones
        
        ✅ FIX: 
        - Find next available ID instead of starting from 1
        - Skip existing profiles
        - Only create NEW profiles
        
        Args:
            count: Number of NEW profiles to create
        
        Returns:
            Tuple of (created_profiles, errors)
        """
        # Check license limit
        current_count = len(self.profiles)
        if current_count + count > self.max_profiles:
            error_msg = f"Cannot create {count} profiles: Would exceed license limit ({self.max_profiles})"
            logger.error(f"[PROFILE] {error_msg}")
            logger.error(f"[PROFILE] Current: {current_count} | Requested: +{count} | Max: {self.max_profiles}")
            return [], [error_msg]
        
        created = []
        errors = []
        
        # ================================================================
        # ✅ FIND NEXT AVAILABLE IDs (don't start from 1!)
        # ================================================================
        
        # Get all existing profile IDs
        existing_ids = {p.profile_id for p in self.profiles}
        logger.info(f"[PROFILE] Existing profile IDs: {sorted(existing_ids)}")
        
        # Find next available IDs
        next_ids = []
        candidate_id = 1
        
        while len(next_ids) < count:
            if candidate_id not in existing_ids:
                # Check if profile directory exists
                profile_name = f"Profile_{candidate_id}"
                profile_path = self.profiles_base_dir / profile_name
                
                if not profile_path.exists():
                    next_ids.append(candidate_id)
                    logger.info(f"[PROFILE] Found available ID: {candidate_id}")
                else:
                    logger.warning(f"[PROFILE] ID {candidate_id} available but directory exists, skipping")
            
            candidate_id += 1
            
            # Safety: prevent infinite loop
            if candidate_id > 100:
                logger.error(f"[PROFILE] Safety limit reached, only found {len(next_ids)} available IDs")
                break
        
        if len(next_ids) < count:
            error_msg = f"Could only find {len(next_ids)}/{count} available profile slots"
            logger.warning(f"[PROFILE] {error_msg}")
            errors.append(error_msg)
        
        # ================================================================
        # ✅ CREATE NEW PROFILES using available IDs
        # ================================================================
        logger.info(f"[PROFILE] Creating {len(next_ids)} new profiles: IDs {next_ids}")
        
        for profile_id in next_ids:
            try:
                profile = self.create_profile(profile_id)
                if profile:
                    created.append(profile)
                    logger.info(f"[PROFILE] ✅ Created: {profile.profile_name}")
                else:
                    error_msg = f"Profile_{profile_id}: Creation failed"
                    errors.append(error_msg)
                    logger.error(f"[PROFILE] ❌ {error_msg}")
            except Exception as e:
                error_msg = f"Profile_{profile_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[PROFILE] ❌ {error_msg}", exc_info=True)
        
        # ================================================================
        # Summary
        # ================================================================
        logger.info(f"[PROFILE] ✅ Successfully created {len(created)}/{count} profiles")
        if errors:
            logger.warning(f"[PROFILE] ⚠️ {len(errors)} errors occurred")
        
        return created, errors


    def create_profile(self, profile_id: int, profile_name: str = None) -> Optional[ProfileInfo]:
        """
        Create a single Chrome profile with full structure
        
        ✅ FIX: Check if profile already exists BEFORE creating
        
        Args:
            profile_id: Profile ID (e.g., 1, 2, 3...)
            profile_name: Optional custom name (default: "Profile_{id}")
        
        Returns:
            ProfileInfo if successful, None otherwise
        """
        try:
            if profile_name is None:
                profile_name = f"Profile_{profile_id}"
            
            profile_path = self.profiles_base_dir / profile_name
            
            # ================================================================
            # ✅ CHECK IF ALREADY EXISTS IN MEMORY
            # ================================================================
            existing = self.get_profile_by_name(profile_name)
            if existing:
                logger.warning(f"[PROFILE] {profile_name} already exists in memory (ID: {existing.profile_id})")
                return existing
            
            # ================================================================
            # ✅ CHECK IF DIRECTORY EXISTS ON DISK
            # ================================================================
            if profile_path.exists():
                # Directory exists but not in memory - might be discovered profile
                logger.info(f"[PROFILE] {profile_name} directory exists, adding to memory...")
                
                profile = ProfileInfo(
                    profile_id=profile_id,
                    profile_name=profile_name,
                    profile_path=str(profile_path),
                    credits_used_today=0,
                    max_credits_per_day=30,
                    last_used="",
                    total_credits_used=0,
                    total_videos_generated=0,
                    is_active=True
                )
                
                self.profiles.append(profile)
                self._save_profiles()
                
                logger.info(f"[PROFILE] ✅ Added existing profile to memory: {profile_name}")
                return profile
            
            # ================================================================
            # ✅ CREATE NEW PROFILE (directory doesn't exist)
            # ================================================================
            logger.info(f"[PROFILE] Creating new profile: {profile_name} at {profile_path}")
            
            # Create main profile directory
            profile_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"[PROFILE] Created directory: {profile_path}")
            
            # ====================================================================
            # CREATE CHROME PROFILE STRUCTURE
            # ====================================================================
            
            # 1. Create Default subdirectory (REQUIRED by Chrome)
            default_dir = profile_path / "Default"
            default_dir.mkdir(exist_ok=True)
            
            # 2. Create essential subdirectories
            essential_dirs = [
                "Cache",
                "Code Cache",
                "GPUCache",
                "Service Worker",
                "Local Storage",
                "Session Storage",
                "IndexedDB",
                "Extensions",
                "Storage",
                "Sync Data"
            ]
            
            for dir_name in essential_dirs:
                (default_dir / dir_name).mkdir(exist_ok=True)
            
            logger.info(f"[PROFILE] Created {len(essential_dirs)} subdirectories")
            
            # 3. Create Preferences file (CRITICAL)
            prefs = {
                "profile": {
                    "name": profile_name,
                    "created_by_version": "131.0.6778.86",
                    "is_using_default_name": False,
                    "default_content_setting_values": {
                        "notifications": 2
                    },
                    "content_settings": {
                        "exceptions": {
                            "notifications": {}
                        }
                    }
                },
                "browser": {
                    "has_seen_welcome_page": True,
                    "check_default_browser": False,
                    "show_home_button": False
                },
                "download": {
                    "prompt_for_download": False,
                    "directory_upgrade": True,
                    "extensions_to_open": ""
                },
                "safebrowsing": {
                    "enabled": True
                },
                "autofill": {
                    "enabled": True
                },
                "translate": {
                    "enabled": False
                },
                "credentials_enable_service": False,
                "profile_network_context_service": {
                    "http_cache_enabled": True
                }
            }
            
            prefs_file = default_dir / "Preferences"
            with open(prefs_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=2)
            
            logger.info(f"[PROFILE] Created Preferences file")
            
            # 4. Create Local State file
            local_state_file = profile_path / "Local State"
            if not local_state_file.exists():
                local_state = {
                    "profile": {
                        "info_cache": {
                            "Default": {
                                "name": profile_name,
                                "shortcut_name": profile_name,
                                "is_using_default_name": False,
                                "background_apps": False,
                                "gaia_given_name": "",
                                "gaia_name": ""
                            }
                        },
                        "profiles_created": 1,
                        "last_used": "Default"
                    },
                    "browser": {
                        "enabled_labs_experiments": []
                    }
                }
                
                with open(local_state_file, 'w', encoding='utf-8') as f:
                    json.dump(local_state, f, indent=2)
                
                logger.info(f"[PROFILE] Created Local State file")
            
            # 5. Create other essential files
            secure_prefs = {
                "profile": {
                    "name": profile_name
                }
            }
            
            secure_prefs_file = default_dir / "Secure Preferences"
            with open(secure_prefs_file, 'w', encoding='utf-8') as f:
                json.dump(secure_prefs, f, indent=2)
            
            # Empty files
            (default_dir / "Cookies").touch()
            (default_dir / "History").touch()
            
            # Bookmarks
            bookmarks = {
                "roots": {
                    "bookmark_bar": {
                        "children": [],
                        "name": "Bookmarks bar",
                        "type": "folder"
                    },
                    "other": {
                        "children": [],
                        "name": "Other bookmarks",
                        "type": "folder"
                    },
                    "synced": {
                        "children": [],
                        "name": "Mobile bookmarks",
                        "type": "folder"
                    }
                },
                "version": 1
            }
            
            bookmarks_file = default_dir / "Bookmarks"
            with open(bookmarks_file, 'w', encoding='utf-8') as f:
                json.dump(bookmarks, f, indent=2)
            
            # First Run marker
            (profile_path / "First Run").touch()
            
            logger.info(f"[PROFILE] ✅ Created complete Chrome profile structure")
            
            # ====================================================================
            # CREATE ProfileInfo OBJECT
            # ====================================================================
            
            profile = ProfileInfo(
                profile_id=profile_id,
                profile_name=profile_name,
                profile_path=str(profile_path),
                credits_used_today=0,
                max_credits_per_day=30,
                last_used="",
                total_credits_used=0,
                total_videos_generated=0,
                is_active=True
            )
            
            # Add to list
            self.profiles.append(profile)
            self._save_profiles()
            
            logger.info(f"[PROFILE] ✅ Profile ready: {profile_name}")
            return profile
            
        except Exception as e:
            logger.error(f"[PROFILE] Failed to create {profile_name}: {e}", exc_info=True)
            return None
    
    # ========================================================================
    # Profile Management Methods
    # ========================================================================
    
    def get_profile_stats(self) -> Dict:
        """Get statistics about all profiles with credits info"""
        if not self.profiles:
            return {
                'total_profiles': 0,
                'active_profiles': 0,
                'total_credits_quota': 0,
                'credits_used_today': 0,
                'credits_remaining_today': 0,
                'total_videos_all_time': 0,
                'total_credits_all_time': 0,
                'profiles': []
            }
        
        active_profiles = [p for p in self.profiles if p.is_active]
        
        return {
            'total_profiles': len(self.profiles),
            'active_profiles': len(active_profiles),
            'total_credits_quota': sum(p.max_credits_per_day for p in active_profiles),
            'credits_used_today': sum(p.credits_used_today for p in active_profiles),
            'credits_remaining_today': sum(p.remaining_credits() for p in active_profiles),
            'total_videos_all_time': sum(p.total_videos_generated for p in active_profiles),
            'total_credits_all_time': sum(p.total_credits_used for p in active_profiles),
            'profiles': [
                {
                    'name': p.profile_name,
                    'credits_used': p.credits_used_today,
                    'max_credits': p.max_credits_per_day,
                    'remaining': p.remaining_credits(),
                    'total_videos': p.total_videos_generated,
                    'total_credits': p.total_credits_used,
                    'active': p.is_active
                }
                for p in self.profiles
            ]
        }
    
    def set_max_profiles(self, max_profiles: int):
        """
        Update maximum allowed profiles (from license)
        
        Args:
            max_profiles: New maximum number of profiles
        """
        old_max = self.max_profiles
        self.max_profiles = max_profiles
        
        # Deactivate excess profiles if new limit is lower
        if max_profiles < len(self.profiles):
            for i in range(max_profiles, len(self.profiles)):
                self.profiles[i].is_active = False
            logger.warning(f"[PROFILE] Deactivated {len(self.profiles) - max_profiles} profiles due to license limit")
        
        # Reactivate profiles if new limit is higher
        elif max_profiles > old_max:
            for i in range(old_max, min(max_profiles, len(self.profiles))):
                self.profiles[i].is_active = True
            logger.info(f"[PROFILE] Activated {min(max_profiles, len(self.profiles)) - old_max} additional profiles")
        
        self._save_profiles()
    
    def add_profile_manually(self, profile_path: str, profile_name: str = None) -> bool:
        """
        Manually add a profile by path
        
        Args:
            profile_path: Path to Chrome profile directory
            profile_name: Optional custom name
            
        Returns:
            True if successful, False otherwise
        """
        if len(self.profiles) >= self.max_profiles:
            logger.error(f"[PROFILE] Cannot add profile: limit of {self.max_profiles} reached")
            return False
        
        path = Path(profile_path)
        if not path.exists() or not path.is_dir():
            logger.error(f"[PROFILE] Invalid profile path: {profile_path}")
            return False
        
        # Auto-generate name if not provided
        if profile_name is None:
            profile_name = f"Profile_{len(self.profiles) + 1}"
        
        # Check if already exists
        if any(p.profile_name == profile_name for p in self.profiles):
            logger.warning(f"[PROFILE] {profile_name} already exists")
            return False
        
        profile = ProfileInfo(
            profile_id=len(self.profiles) + 1,
            profile_name=profile_name,
            profile_path=str(path),
            credits_used_today=0,
            max_credits_per_day=30,
            last_used="",
            total_credits_used=0,
            total_videos_generated=0,
            is_active=True
        )
        
        self.profiles.append(profile)
        self._save_profiles()
        
        logger.info(f"[PROFILE] Added profile: {profile_name} at {profile_path}")
        return True
    
    def get_profile_by_id(self, profile_id: int) -> Optional[ProfileInfo]:
        """Get profile by ID"""
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        return None
    
    def get_profile_by_name(self, profile_name: str) -> Optional[ProfileInfo]:
        """Get profile by name"""
        for profile in self.profiles:
            if profile.profile_name == profile_name:
                return profile
        return None
    
    def delete_profile(self, profile_name: str, delete_files: bool = False) -> bool:
        """
        Delete a profile from management
        
        Args:
            profile_name: Profile to delete
            delete_files: If True, also delete profile directory
        
        Returns:
            True if successful
        """
        try:
            profile = self.get_profile_by_name(profile_name)
            if not profile:
                logger.warning(f"[PROFILE] Profile not found: {profile_name}")
                return False
            
            # Remove from list
            self.profiles.remove(profile)
            
            # Delete files if requested
            if delete_files:
                import shutil
                profile_path = Path(profile.profile_path)
                if profile_path.exists():
                    shutil.rmtree(profile_path)
                    logger.info(f"[PROFILE] Deleted files: {profile_path}")
            
            self._save_profiles()
            logger.info(f"[PROFILE] Removed profile: {profile_name}")
            return True
            
        except Exception as e:
            logger.error(f"[PROFILE] Delete error: {e}")
            return False
    
    def reset_profile_credits(self, profile_name: str) -> bool:
        """
        Manually reset credits for a profile (admin function)
        
        Args:
            profile_name: Profile name to reset
            
        Returns:
            True if successful
        """
        profile = self.get_profile_by_name(profile_name)
        if profile:
            profile.credits_used_today = 0
            self._save_profiles()
            logger.info(f"[PROFILE] Reset credits for {profile_name}")
            return True
        return False
    
    def reset_all_credits(self) -> int:
        """
        Reset credits for all profiles (admin function)
        
        Returns:
            Number of profiles reset
        """
        count = 0
        for profile in self.profiles:
            profile.credits_used_today = 0
            count += 1
        self._save_profiles()
        logger.info(f"[PROFILE] Reset credits for {count} profiles")
        return count


# ============================================================================
# EXAMPLE USAGE WITH CREDITS SYSTEM
# ============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*70)
    print("PROFILE MANAGER - CREDITS SYSTEM v2.0")
    print("="*70)
    print("✅ Video 10s = 1 credit")
    print("✅ Video 15s = 2 credits")
    print("✅ Quota = 30 credits/day\n")
    
    # Initialize manager
    manager = ProfileManager(
        profiles_base_dir="./chrome_profile",
        max_profiles=3
    )
    
    # Test 1: Create profiles
    print("\n[TEST 1] Creating 3 profiles...")
    created, errors = manager.create_multiple_profiles(3)
    print(f"✅ Created: {len(created)} profiles\n")
    
    # Test 2: Show initial stats
    print("[TEST 2] Initial Statistics")
    print("─"*70)
    stats = manager.get_profile_stats()
    print(f"Total Credits Available: {stats['credits_remaining_today']}")
    print(f"Max Videos (10s): {stats['credits_remaining_today']} videos")
    print(f"Max Videos (15s): {stats['credits_remaining_today'] // 2} videos\n")
    
    # Test 3: Simulate mixed video generation
    print("[TEST 3] Simulating Video Generation")
    print("─"*70)
    
    test_videos = [
        (10, "Short video"),
        (15, "Medium video"),
        (10, "Short video"),
        (15, "Medium video"),
        (10, "Short video"),
    ]
    
    for duration, desc in test_videos:
        credits = calculate_credits(duration)
        profile = manager.get_next_available_profile(duration)
        
        if profile:
            print(f"✅ {desc} ({duration}s, {credits} credits) → {profile.profile_name}")
            print(f"   Remaining: {profile.remaining_credits()} credits")
            manager.increment_usage(profile, duration)
        else:
            print(f"❌ {desc} ({duration}s, {credits} credits) → NO PROFILE AVAILABLE")
    
    # Test 4: Final stats
    print("\n[TEST 4] Final Statistics")
    print("─"*70)
    stats = manager.get_profile_stats()
    print(f"Credits Used Today: {stats['credits_used_today']}/{stats['total_credits_quota']}")
    print(f"Credits Remaining: {stats['credits_remaining_today']}")
    print(f"Total Videos Generated: {stats['total_videos_all_time']}")
    
    print("\n📊 Profile Details:")
    for p in stats['profiles']:
        status = "✅" if p['active'] else "❌"
        print(f"  {status} {p['name']}:")
        print(f"     Credits: {p['credits_used']}/{p['max_credits']} (Remaining: {p['remaining']})")
        print(f"     Videos: {p['total_videos']} total")
    
    print("\n✅ All tests completed!")
    print("─"*70)