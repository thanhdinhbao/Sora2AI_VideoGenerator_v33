#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Profile Token Manager - Enhanced with Cookies Support
======================================================
Manages bearer tokens, cookies, and sentinel tokens for profiles
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple  # ✅ THÊM Tuple vào đây

logger = logging.getLogger(__name__)


class ProfileTokenManager:
    """
    Enhanced Profile Token Manager with proper isolation
    
    Features:
    - Auto-extract and save tokens
    - Per-profile token storage
    - Token age tracking
    - Validation and expiration check
    """
    
    def __init__(self, token_file: str = "profile_tokens.json"):
        """
        Initialize Token Manager
        
        Args:
            token_file: Path to JSON file storing tokens
        """
        self.token_file = Path(token_file)
        self.data = self._load_data()
        logger.info(f"[TOKEN MANAGER] Initialized with {len(self.data)} profiles")
    
    def _load_data(self) -> Dict:
        """Load tokens from JSON file"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logger.info(f"[TOKEN MANAGER] Loaded {len(data)} profile tokens")
                return data
            except Exception as e:
                logger.error(f"[TOKEN MANAGER] Load error: {e}")
                return {}
        else:
            logger.info(f"[TOKEN MANAGER] No existing token file, creating new")
            return {}
    
    def _save_data(self) -> bool:
        """Save tokens to JSON file"""
        try:
            # Ensure directory exists
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write with backup
            backup_file = self.token_file.with_suffix('.json.bak')
            
            # Save to temp first
            temp_file = self.token_file.with_suffix('.json.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            
            # Backup old file if exists
            if self.token_file.exists():
                self.token_file.replace(backup_file)
            
            # Move temp to main
            temp_file.replace(self.token_file)
            
            logger.info(f"[TOKEN MANAGER] Saved {len(self.data)} tokens")
            return True
            
        except Exception as e:
            logger.error(f"[TOKEN MANAGER] Save error: {e}")
            return False
    
    def set_token(self, profile_name: str, bearer_token: str, 
                  cookies: Optional[str] = None,
                  sentinel_token: Optional[str] = None) -> bool:
        """
        Set token for profile
        
        Args:
            profile_name: Profile identifier (e.g., "Profile_1", "Default")
            bearer_token: JWT bearer token (must start with 'eyJ')
            cookies: Optional cookie string
            sentinel_token: Optional sentinel token
        
        Returns:
            True if saved successfully
        """
        # Validate token format
        if not bearer_token or len(bearer_token) < 50:
            logger.error(f"[TOKEN MANAGER] Invalid token for {profile_name}: too short")
            return False
        
        if not bearer_token.startswith('eyJ'):
            logger.warning(f"[TOKEN MANAGER] Token for {profile_name} may be invalid (not JWT)")
        
        # Store token data
        self.data[profile_name] = {
            'bearer_token': bearer_token,
            'cookies': cookies,
            'sentinel_token': sentinel_token,
            'extracted_at': time.time(),
            'length': len(bearer_token)
        }
        
        saved = self._save_data()
        
        if saved:
            logger.info(f"[TOKEN MANAGER] ✅ Saved token for {profile_name} ({len(bearer_token)} chars)")
        else:
            logger.error(f"[TOKEN MANAGER] ❌ Failed to save token for {profile_name}")
        
        return saved
    
    def get_token(self, profile_name: str) -> Optional[str]:
        """
        Get bearer token for profile
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            Bearer token string or None
        """
        profile_data = self.data.get(profile_name)
        
        if not profile_data:
            logger.debug(f"[TOKEN MANAGER] No token for {profile_name}")
            return None
        
        # Handle old format (string) vs new format (dict)
        if isinstance(profile_data, str):
            logger.warning(f"[TOKEN MANAGER] Old format detected for {profile_name}, converting")
            # Convert to new format
            self.set_token(profile_name, profile_data)
            return profile_data
        
        elif isinstance(profile_data, dict):
            token = profile_data.get('bearer_token')
            if token:
                age_seconds = time.time() - profile_data.get('extracted_at', 0)
                age_hours = age_seconds / 3600
                logger.debug(f"[TOKEN MANAGER] Token for {profile_name}: {len(token)} chars, {age_hours:.1f}h old")
            return token
        
        return None
    
    def get_all_tokens(self, profile_name: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get all tokens for profile
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            Tuple of (bearer_token, cookies, sentinel_token)
        """
        profile_data = self.data.get(profile_name)
        
        if not profile_data or not isinstance(profile_data, dict):
            return (None, None, None)
        
        return (
            profile_data.get('bearer_token'),
            profile_data.get('cookies'),
            profile_data.get('sentinel_token')
        )
    
    def get_token_age(self, profile_name: str) -> Optional[float]:
        """
        Get token age in seconds
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            Age in seconds or None
        """
        profile_data = self.data.get(profile_name)
        
        if isinstance(profile_data, dict):
            extracted_at = profile_data.get('extracted_at')
            if extracted_at:
                return time.time() - extracted_at
        
        return None
    
    def is_token_expired(self, profile_name: str, max_age_hours: float = 2.0) -> bool:
        """
        Check if token is expired
        
        Args:
            profile_name: Profile identifier
            max_age_hours: Maximum age in hours (default 2 hours)
        
        Returns:
            True if expired or missing
        """
        age_seconds = self.get_token_age(profile_name)
        
        if age_seconds is None:
            return True  # No token = expired
        
        return age_seconds > (max_age_hours * 3600)
    
    def delete_token(self, profile_name: str) -> bool:
        """
        Delete token for profile
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            True if deleted
        """
        if profile_name in self.data:
            del self.data[profile_name]
            logger.info(f"[TOKEN MANAGER] Deleted token for {profile_name}")
            return self._save_data()
        
        return False
    
    def list_profiles(self) -> List[str]:
        """
        List all profiles with tokens
        
        Returns:
            List of profile names
        """
        return list(self.data.keys())
    
    def get_stats(self) -> dict:
        """
        Get token statistics
        
        Returns:
            Dict with total, valid, expired counts
        """
        total = len(self.data)
        valid = 0
        expired = 0
        invalid = 0
        
        for profile_name, profile_data in self.data.items():
            if isinstance(profile_data, dict) and profile_data.get('bearer_token'):
                if self.is_token_expired(profile_name, max_age_hours=2.0):
                    expired += 1
                else:
                    valid += 1
            else:
                invalid += 1
        
        return {
            'total': total,
            'valid': valid,
            'expired': expired,
            'invalid': invalid
        }
    
    def validate_token(self, profile_name: str) -> Tuple[bool, str]:
        """
        Validate token for profile
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            Tuple of (is_valid, reason)
        """
        token = self.get_token(profile_name)
        
        if not token:
            return (False, "Token not found")
        
        if len(token) < 50:
            return (False, "Token too short")
        
        if not token.startswith('eyJ'):
            return (False, "Not a valid JWT token")
        
        if token.count('.') != 2:
            return (False, "Invalid JWT format (must have 2 dots)")
        
        age_seconds = self.get_token_age(profile_name)
        if age_seconds and age_seconds > 7200:  # 2 hours
            return (False, f"Token expired ({age_seconds/3600:.1f} hours old)")
        
        return (True, "Valid")
    
    def get_profile_info(self, profile_name: str) -> Optional[Dict]:
        """
        Get detailed info for profile
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            Dict with token info or None
        """
        profile_data = self.data.get(profile_name)
        
        if not profile_data:
            return None
        
        if isinstance(profile_data, dict):
            token = profile_data.get('bearer_token', '')
            extracted_at = profile_data.get('extracted_at', 0)
            age_seconds = time.time() - extracted_at if extracted_at else None
            
            is_valid, reason = self.validate_token(profile_name)
            
            return {
                'profile_name': profile_name,
                'has_token': bool(token),
                'token_length': len(token) if token else 0,
                'token_preview': f"{token[:20]}...{token[-15:]}" if token and len(token) > 35 else "N/A",
                'extracted_at': extracted_at,
                'age_seconds': age_seconds,
                'age_hours': age_seconds / 3600 if age_seconds else None,
                'is_valid': is_valid,
                'validation_reason': reason,
                'has_cookies': bool(profile_data.get('cookies')),
                'has_sentinel': bool(profile_data.get('sentinel_token'))
            }
        
        return None
    
    def clear_all(self) -> bool:
        """
        Clear all tokens (DANGEROUS)
        
        Returns:
            True if cleared
        """
        self.data = {}
        logger.warning(f"[TOKEN MANAGER] ⚠️ All tokens cleared!")
        return self._save_data()


# ============================================================================
# EXAMPLE USAGE & TESTING
# ============================================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║       Profile Token Manager - Enhanced & Fixed                ║
    ╚═══════════════════════════════════════════════════════════════╝
    
    FEATURES:
    ─────────
    ✅ Per-profile token isolation
    ✅ JWT validation (eyJ prefix, 2 dots, length)
    ✅ Token age tracking
    ✅ Expiration check (default 2 hours)
    ✅ Safe save with backup
    ✅ Old format auto-conversion
    ✅ Detailed profile info
    
    TESTING:
    ────────
    """)
    
    # Initialize manager
    manager = ProfileTokenManager("test_tokens.json")
    
    # Test 1: Set tokens for multiple profiles
    print("\n[TEST 1] Setting tokens for 3 profiles...")
    manager.set_token("Default", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c")
    manager.set_token("Profile_1", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkphbmUgRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.kPH7xZqE1OQuLqc8H8Ng4fKGpBj1pKkY5y7Y0Cv1234")
    manager.set_token("Profile_2", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkJvYiBTbWl0aCIsImlhdCI6MTUxNjIzOTAyMn0.abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234")
    
    # Test 2: Get tokens
    print("\n[TEST 2] Getting tokens...")
    for profile in ["Default", "Profile_1", "Profile_2", "Profile_3"]:
        token = manager.get_token(profile)
        if token:
            print(f"  ✅ {profile}: {token[:20]}...{token[-15:]}")
        else:
            print(f"  ❌ {profile}: No token")
    
    # Test 3: Validate tokens
    print("\n[TEST 3] Validating tokens...")
    for profile in manager.list_profiles():
        is_valid, reason = manager.validate_token(profile)
        print(f"  {profile}: {'✅' if is_valid else '❌'} {reason}")
    
    # Test 4: Get profile info
    print("\n[TEST 4] Profile info...")
    info = manager.get_profile_info("Profile_1")
    if info:
        print(f"""
  Profile: {info['profile_name']}
  Token: {info['token_preview']}
  Length: {info['token_length']} chars
  Age: {info['age_hours']:.2f} hours
  Valid: {info['is_valid']} ({info['validation_reason']})
        """)
    
    # Test 5: Stats
    print("\n[TEST 5] Statistics...")
    stats = manager.get_stats()
    print(f"""
  Total: {stats['total']}
  Valid: {stats['valid']}
  Expired: {stats['expired']}
  Invalid: {stats['invalid']}
    """)
    
    print("\n✅ All tests completed!")
    print(f"📁 Test file created: {manager.token_file}")
    
    # Cleanup
    import os
    if manager.token_file.exists():
        # os.remove(manager.token_file)  # Uncomment to delete test file
        print(f"⚠️  Test file NOT deleted (manual cleanup required)")