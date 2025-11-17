#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UNIFIED TOKEN MANAGER & AUTO MODE SWITCHER
==========================================
Kết hợp:
- TokenManager từ api_test_and_token_manager.py (quản lý token chi tiết)
- AutoModeManager (tự động chuyển Browser ↔ API mode)
- Auto-extract từ browser performance logs

Tích hợp vào: sora2_video_generator_v31.py
"""

import json
import logging
import time
import base64
from pathlib import Path
from typing import Optional, Dict, Tuple, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TokenManager:
    """
    Quản lý Sora API tokens với persistence
    
    Features:
    - Save/load tokens (bearer + cookies + sentinel)
    - Auto-detect JWT expiry
    - Token validation
    - Multi-profile support
    
    Based on: api_test_and_token_manager.py
    """
    
    def __init__(self, token_file: str = "profile_tokens/sora_tokens.json"):
        """
        Initialize TokenManager
        
        Args:
            token_file: JSON file to store tokens
        """
        self.token_file = Path(token_file)
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.tokens = self._load_tokens()
    
    def _load_tokens(self) -> Dict:
        """Load tokens from JSON file"""
        if self.token_file.exists():
            try:
                with open(self.token_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"[TOKEN] Error loading: {e}")
                return {}
        return {}
    
    def _save_tokens(self):
        """Save tokens to JSON file"""
        try:
            with open(self.token_file, 'w', encoding='utf-8') as f:
                json.dump(self.tokens, f, indent=2)
            logger.info(f"[TOKEN] ✅ Saved to {self.token_file}")
        except Exception as e:
            logger.error(f"[TOKEN] ❌ Save error: {e}")
    
    def set_tokens(self, 
                   bearer_token: str, 
                   cookies: str = "", 
                   sentinel_token: str = "",
                   profile_name: str = "default",
                   metadata: Dict = None):
        """
        Store tokens for a profile
        
        Args:
            bearer_token: JWT bearer token (REQUIRED)
            cookies: Cookie string (optional)
            sentinel_token: Sentinel token (optional)
            profile_name: Profile identifier
            metadata: Additional metadata
        """
        # Decode JWT to get expiry
        expiry = self._get_token_expiry(bearer_token)
        
        self.tokens[profile_name] = {
            'bearer_token': bearer_token,
            'cookies': cookies or "",
            'sentinel_token': sentinel_token or "",
            'saved_at': datetime.now().isoformat(),
            'expires_at': expiry.isoformat() if expiry else None,
            'metadata': metadata or {}
        }
        
        self._save_tokens()
        
        logger.info(f"[TOKEN] ✅ Saved for profile: {profile_name}")
        logger.info(f"[TOKEN]    Length: {len(bearer_token)} chars")
        if expiry:
            remaining = expiry - datetime.now()
            hours = remaining.total_seconds() / 3600
            logger.info(f"[TOKEN]    Expires: {expiry.strftime('%Y-%m-%d %H:%M')} ({hours:.1f}h remaining)")
    
    def get_tokens(self, profile_name: str = "default") -> Optional[Tuple[str, str, str]]:
        """
        Get tokens for a profile
        
        Args:
            profile_name: Profile identifier
        
        Returns:
            Tuple of (bearer_token, cookies, sentinel_token) or None if expired
        """
        if profile_name not in self.tokens:
            logger.warning(f"[TOKEN] ⚠️  No tokens for: {profile_name}")
            return None
        
        token_data = self.tokens[profile_name]
        
        # Check expiry
        if token_data.get('expires_at'):
            expiry = datetime.fromisoformat(token_data['expires_at'])
            if datetime.now() >= expiry:
                logger.warning(f"[TOKEN] ⚠️  Expired for: {profile_name}")
                logger.warning(f"[TOKEN]    Expired at: {expiry}")
                return None
        
        return (
            token_data['bearer_token'],
            token_data.get('cookies', ''),
            token_data.get('sentinel_token', '')
        )
    
    def get_bearer_token(self, profile_name: str = "default") -> Optional[str]:
        """
        Get only bearer token (most commonly used)
        
        Returns:
            Bearer token string or None
        """
        tokens = self.get_tokens(profile_name)
        return tokens[0] if tokens else None
    
    def is_valid(self, profile_name: str = "default") -> bool:
        """Check if tokens are valid (exist and not expired)"""
        tokens = self.get_tokens(profile_name)
        return tokens is not None
    
    def clear_tokens(self, profile_name: str = "default"):
        """Clear tokens for a profile"""
        if profile_name in self.tokens:
            del self.tokens[profile_name]
            self._save_tokens()
            logger.info(f"[TOKEN] 🗑️  Cleared for: {profile_name}")
    
    def _get_token_expiry(self, bearer_token: str) -> Optional[datetime]:
        """
        Extract expiry from JWT token
        
        Args:
            bearer_token: JWT token
            
        Returns:
            Expiry datetime or None
        """
        try:
            # JWT format: header.payload.signature
            parts = bearer_token.split('.')
            if len(parts) != 3:
                return None
            
            # Decode payload (add padding if needed)
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)
            
            # Get exp field (Unix timestamp)
            exp = data.get('exp')
            if exp:
                return datetime.fromtimestamp(exp)
        except Exception as e:
            logger.debug(f"[TOKEN] Could not decode JWT: {e}")
        
        return None
    
    def list_profiles(self) -> Dict[str, Dict]:
        """
        List all stored profiles with status
        
        Returns:
            Dict of profile_name -> profile_info
        """
        profiles = {}
        
        for profile_name, data in self.tokens.items():
            saved_at = datetime.fromisoformat(data['saved_at'])
            expires_at = data.get('expires_at')
            
            status = "valid"
            remaining_hours = None
            
            if expires_at:
                exp_dt = datetime.fromisoformat(expires_at)
                if datetime.now() >= exp_dt:
                    status = "expired"
                else:
                    remaining = exp_dt - datetime.now()
                    remaining_hours = remaining.total_seconds() / 3600
            
            profiles[profile_name] = {
                'status': status,
                'saved_at': saved_at,
                'expires_at': datetime.fromisoformat(expires_at) if expires_at else None,
                'remaining_hours': remaining_hours,
                'has_cookies': bool(data.get('cookies')),
                'has_sentinel': bool(data.get('sentinel_token'))
            }
        
        return profiles
    
    def print_profiles(self):
        """Print all profiles (for debugging)"""
        print("\n" + "="*70)
        print("STORED TOKEN PROFILES")
        print("="*70)
        
        profiles = self.list_profiles()
        
        if not profiles:
            print("No profiles stored")
            return
        
        for profile_name, info in profiles.items():
            status_icon = "✅" if info['status'] == "valid" else "❌"
            
            print(f"\n{status_icon} {profile_name}:")
            print(f"   Saved: {info['saved_at'].strftime('%Y-%m-%d %H:%M')}")
            
            if info['status'] == "valid" and info['remaining_hours']:
                print(f"   Valid: {info['remaining_hours']:.1f}h remaining")
            elif info['status'] == "expired":
                print(f"   Status: EXPIRED at {info['expires_at'].strftime('%Y-%m-%d %H:%M')}")
            
            print(f"   Cookies: {'Yes' if info['has_cookies'] else 'No'}")
            print(f"   Sentinel: {'Yes' if info['has_sentinel'] else 'No'}")
        
        print("\n" + "="*70)


class AutoModeManager:
    """
    Quản lý tự động chuyển đổi giữa Browser Mode và API Mode
    
    Workflow:
    1. Check if profile has valid token → API mode
    2. If no token / expired → Browser mode
    3. Auto-switch when token expires
    """
    
    MODE_BROWSER = "browser"
    MODE_API = "api"
    
    def __init__(self, profile_name: str, token_file: str = "profile_tokens/sora_tokens.json"):
        """
        Initialize AutoModeManager
        
        Args:
            profile_name: Profile name (e.g., "Profile_1")
            token_file: Path to tokens file
        """
        self.profile_name = profile_name
        self.token_manager = TokenManager(token_file)
        
        # Determine initial mode
        if self.token_manager.is_valid(profile_name):
            self.current_mode = self.MODE_API
            logger.info(f"[MODE] ✅ {profile_name}: Starting in API mode")
        else:
            self.current_mode = self.MODE_BROWSER
            logger.info(f"[MODE] ℹ️  {profile_name}: Starting in Browser mode")
    
    def get_mode(self) -> str:
        """Get current mode"""
        return self.current_mode
    
    def is_api_mode(self) -> bool:
        """Check if in API mode"""
        return self.current_mode == self.MODE_API
    
    def is_browser_mode(self) -> bool:
        """Check if in Browser mode"""
        return self.current_mode == self.MODE_BROWSER
    
    def switch_to_api_mode(self, bearer_token: str, cookies: str = "", 
                          sentinel_token: str = "", metadata: Dict = None) -> bool:
        """
        Chuyển sang API mode
        
        Args:
            bearer_token: Bearer token (REQUIRED)
            cookies: Cookie string (optional)
            sentinel_token: Sentinel token (optional)
            metadata: Additional metadata
            
        Returns:
            True if switched successfully
        """
        try:
            # Save tokens
            self.token_manager.set_tokens(
                bearer_token, 
                cookies, 
                sentinel_token,
                self.profile_name,
                metadata
            )
            
            self.current_mode = self.MODE_API
            logger.info(f"[MODE] ✅ {self.profile_name}: Switched to API mode")
            return True
            
        except Exception as e:
            logger.error(f"[MODE] ❌ Switch to API error: {e}")
            return False
    
    def switch_to_browser_mode(self, reason: str = "token expired"):
        """
        Chuyển về Browser mode
        
        Args:
            reason: Lý do chuyển
        """
        self.current_mode = self.MODE_BROWSER
        logger.info(f"[MODE] ℹ️  {self.profile_name}: Switched to Browser mode")
        logger.info(f"[MODE]    Reason: {reason}")
    
    def get_bearer_token(self) -> Optional[str]:
        """Get bearer token for current profile"""
        return self.token_manager.get_bearer_token(self.profile_name)
    
    def get_all_tokens(self) -> Optional[Tuple[str, str, str]]:
        """Get all tokens (bearer, cookies, sentinel)"""
        return self.token_manager.get_tokens(self.profile_name)
    
    def handle_api_error(self, status_code: int, error_message: str = ""):
        """
        Xử lý lỗi API và tự động fallback
        
        Args:
            status_code: HTTP status code
            error_message: Error message
        """
        if status_code == 401:
            logger.warning(f"[MODE] ⚠️  401 Unauthorized - Token expired")
            self.token_manager.clear_tokens(self.profile_name)
            self.switch_to_browser_mode("token expired (401)")
            
        elif status_code == 403:
            logger.warning(f"[MODE] ⚠️  403 Forbidden - May need browser login")
            # Don't clear token immediately, might be temporary
            
        elif status_code >= 500:
            logger.warning(f"[MODE] ⚠️  Server error: {status_code}")
            # Server issues, keep token




# ============================================================================
# USAGE EXAMPLES
# ============================================================================

if __name__ == "__main__":
    """Example usage"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*70)
    print("UNIFIED TOKEN MANAGER & AUTO MODE SWITCHER")
    print("="*70)
    
    # Example 1: Check existing profiles
    token_mgr = TokenManager()
    token_mgr.print_profiles()
    
    # Example 2: Initialize mode manager for a profile
    profile = "Profile_1"
    mode_mgr = AutoModeManager(profile)
    
    print(f"\nProfile: {profile}")
    print(f"Current mode: {mode_mgr.get_mode()}")
    
    if mode_mgr.is_api_mode():
        token = mode_mgr.get_bearer_token()
        print(f"✅ API mode - Token: {token[:30]}..." if token else "❌ No token")
    else:
        print(f"ℹ️  Browser mode - Need to extract token")
    
    print("\n" + "="*70)
    print("\nUsage in your app:")
    print("  1. from unified_token_manager import AutoModeManager, auto_extract_token_from_browser")
    print("  2. mode_mgr = AutoModeManager('Profile_1')")
    print("  3. if mode_mgr.is_api_mode(): use_api() else: use_browser()")
    print("  4. After browser login: auto_extract_token_from_browser(driver, 'Profile_1')")