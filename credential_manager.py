#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CREDENTIAL MANAGER - Giống ManixAI
===================================
Lưu credentials (token + cookies) và auto-refresh khi cần

Flow:
1. Add Account (1 lần) → Mở browser headless → Extract credentials → Save
2. Mọi lần sau → Load credentials → Use API 100%
"""

import json
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CredentialManager:
    """
    Manage Sora credentials (like ManixAI)
    
    Features:
    - Save/load credentials per profile
    - Auto-refresh when token expires
    - Headless browser for credential fetch
    """
    
    def __init__(self, credentials_dir: str = "./credentials"):
        """
        Initialize credential manager
        
        Args:
            credentials_dir: Directory to store credentials
        """
        self.credentials_dir = Path(credentials_dir)
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        
        self.profiles = {}
        self._load_all_profiles()
        
        logger.info(f"[CRED] Manager initialized")
        logger.info(f"[CRED] Directory: {self.credentials_dir}")
        logger.info(f"[CRED] Loaded {len(self.profiles)} profiles")
    
    def _load_all_profiles(self):
        """Load all saved profiles"""
        try:
            for file in self.credentials_dir.glob("*.json"):
                profile_name = file.stem
                with open(file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.profiles[profile_name] = data
                    logger.debug(f"[CRED] Loaded profile: {profile_name}")
        
        except Exception as e:
            logger.error(f"[CRED] Load profiles error: {e}")
    
    def add_account(self, profile_name: str, bearer_token: str, cookies: str = "", callback=None) -> bool:
        """
        Add new account with provided credentials
        
        Args:
            profile_name: Profile name
            bearer_token: JWT token (từ step1 + test_extract)
            cookies: Cookie string
            callback: Callback function
            
        Returns:
            True if success
        """
        try:
            if callback:
                callback(f"[CRED] Adding account: {profile_name}", "info")
            
            credentials = {
                'bearer_token': bearer_token,
                'cookies': cookies,
                'fetched_at': datetime.now().isoformat()
            }
            
            # Save credentials
            self._save_profile(profile_name, credentials)
            
            if callback:
                callback(f"[CRED] ✅ Account added: {profile_name}", "ok")
            
            return True
        
        except Exception as e:
            logger.error(f"[CRED] Add account error: {e}", exc_info=True)
            if callback:
                callback(f"[CRED] ❌ Error: {str(e)[:100]}", "err")
            return False

    def list_profiles(self) -> list:
        """List all saved profiles"""
        return list(self.profiles.keys())

    def remove_profile(self, profile_name: str) -> bool:
        """Remove profile"""
        try:
            file_path = self.credentials_dir / f"{profile_name}.json"
            
            if file_path.exists():
                file_path.unlink()
            
            if profile_name in self.profiles:
                del self.profiles[profile_name]
            
            logger.info(f"[CRED] ✅ Removed profile: {profile_name}")
            return True
        
        except Exception as e:
            logger.error(f"[CRED] Remove profile error: {e}")
            return False

    def get_credentials(self, profile_name: str) -> Optional[Dict]:
        """
        Get credentials for a profile
        
        Args:
            profile_name: Profile name
            
        Returns:
            Dict with credentials or None
        """
        try:
            if profile_name in self.profiles:
                return self.profiles[profile_name]
            
            # Try to load from file if not in memory
            file_path = self.credentials_dir / f"{profile_name}.json"
            
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    credentials = json.load(f)
                    self.profiles[profile_name] = credentials
                    return credentials
            
            logger.warning(f"[CRED] No credentials found for: {profile_name}")
            return None
        
        except Exception as e:
            logger.error(f"[CRED] Get credentials error: {e}", exc_info=True)
            return None

    def _save_profile(self, profile_name: str, credentials: Dict) -> bool:
        """
        Save profile credentials to file
        
        Args:
            profile_name: Profile name
            credentials: Credentials dict
            
        Returns:
            True if success
        """
        try:
            file_path = self.credentials_dir / f"{profile_name}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(credentials, f, indent=2)
            
            # Update in-memory cache
            self.profiles[profile_name] = credentials
            
            logger.info(f"[CRED] ✅ Saved profile: {profile_name}")
            return True
        
        except Exception as e:
            logger.error(f"[CRED] Save profile error: {e}", exc_info=True)
            return False

# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """Example usage"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Initialize manager
    cred_mgr = CredentialManager()
    
    print("\n" + "="*70)
    print("CREDENTIAL MANAGER - Like ManixAI")
    print("="*70)
    
    # List profiles
    profiles = cred_mgr.list_profiles()
    print(f"\nProfiles: {profiles}")
    
    # Add new account
    # success = cred_mgr.add_account("my_profile", callback=print)
    
    # Get credentials
    # creds = cred_mgr.get_credentials("my_profile")
    # if creds:
    #     print(f"Token: {creds['bearer_token'][:30]}...")
