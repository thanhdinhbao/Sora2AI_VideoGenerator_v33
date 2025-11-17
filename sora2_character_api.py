#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora2 Character API Client
==========================
API client for creating and managing characters/cameos on Sora2
Implements 7-step character creation flow

Author: Tran Nguyen - Zalo: 0789.535.888
"""

import os
import json
import time
import logging
import requests
from typing import Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class Sora2CharacterAPI:
    """API client for Sora2 character/cameo management"""
    
    BASE_URL = "https://sora.chatgpt.com/backend"
    
    def __init__(self, bearer_token: str, cookies: dict = None, user_agent: str = None):
        """
        Initialize API client
        
        Args:
            bearer_token: Bearer token from Sora
            cookies: Cookies dict from browser (REQUIRED for Cloudflare)
            user_agent: User-Agent string from browser
        """
        self.bearer_token = bearer_token
        self.session = requests.Session()
        
        # ================================================================
        # FIX 1: UPDATE COOKIES (including Cloudflare)
        # ================================================================
        if cookies:
            # Convert dict to CookieJar format
            for name, value in cookies.items():
                self.session.cookies.set(name, value)
            
            logger.info(f"[API] Set {len(cookies)} cookies")
            
            # Check for important cookies
            required_cookies = ['oai-did', 'cf_clearance', '__cf_bm']
            missing = [c for c in required_cookies if c not in cookies]
            if missing:
                logger.warning(f"[API] Missing cookies: {missing}")
        else:
            logger.warning("[API] No cookies provided!")
        
        # ================================================================
        # FIX 2: UPDATE HEADERS (match browser exactly)
        # ================================================================
        headers = {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Authorization': f'Bearer {bearer_token}',
            'Content-Type': 'application/json',
            'Origin': 'https://sora.chatgpt.com',
            'Referer': 'https://sora.chatgpt.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        }
        
        # FIX 3: Add User-Agent
        if user_agent:
            headers['User-Agent'] = user_agent
        else:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36'
        
        # FIX 4: Add Device ID if available
        if cookies and 'oai-did' in cookies:
            headers['oai-device-id'] = cookies['oai-did']
            logger.info(f"[API] Device ID: {cookies['oai-did']}")
        
        self.session.headers.update(headers)
        
        logger.info("[API] API client initialized")
        logger.info(f"[API] Token: {len(bearer_token)} chars")
        logger.info(f"[API] Headers: {len(self.session.headers)}")
        logger.info(f"[API] Cookies: {len(self.session.cookies)}")
    
    def create_character_from_generation(
        self, 
        generation_id: str,
        timestamps: list = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Step 1: Create character from generation - FIXED WITH RETRY
        
        Args:
            generation_id: Generation ID (e.g., 'gen_01k91hv9s0ek9vzryag29vqs8h')
            timestamps: Start/end timestamps [start, end], default [0, 3]
        
        Returns:
            (success, data, error_message)
        """
        if timestamps is None:
            timestamps = [0, 3]
        
        url = f"{self.BASE_URL}/characters/from-generation"
        payload = {
            "generation_id": generation_id,
            "character_id": None,
            "timestamps": timestamps
        }
        
        # ================================================================
        # ADD: Retry logic with exponential backoff
        # ================================================================
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                logger.info("="*60)
                logger.info(f"[API] Creating character (Attempt {attempt+1}/{max_retries})")
                logger.info(f"[API] Generation ID: {generation_id}")
                logger.info("="*60)
                
                # ADD: Random delay to avoid bot detection
                if attempt > 0:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"[API] Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                
                # LOG: Debug request
                logger.info(f"[API] Request URL: {url}")
                logger.info(f"[API] Request payload: {payload}")
                logger.info(f"[API] Cookies count: {len(self.session.cookies)}")
                
                # Check for Cloudflare cookies
                cf_cookies = [c for c in self.session.cookies if 'cf_' in c.lower() or '__cf_' in c.lower()]
                logger.info(f"[API] Cloudflare cookies: {len(cf_cookies)} found")
                
                # Send request
                response = self.session.post(url, json=payload, timeout=30)
                
                logger.info(f"[API] Response status: {response.status_code}")
                logger.info(f"[API] Response headers: {dict(response.headers)}")
                
                # ================================================================
                # CHECK RESPONSE
                # ================================================================
                if response.status_code == 200:
                    data = response.json()
                    cameo_id = data.get('id')
                    status = data.get('status')
                    
                    logger.info(f"[API] Character created - Cameo ID: {cameo_id}, Status: {status}")
                    return True, data, None
                
                elif response.status_code == 403:
                    error_body = response.text[:500]
                    logger.error("[API] HTTP 403 Forbidden")
                    logger.error(f"[API] Response body: {error_body}")
                    
                    # Check if it's Cloudflare challenge
                    if 'DOCTYPE' in error_body or 'cloudflare' in error_body.lower():
                        error_msg = "Cloudflare Challenge detected!"
                        logger.error(f"[API] {error_msg}")
                        
                        if attempt < max_retries - 1:
                            logger.warning(f"[API] Retrying... ({attempt+1}/{max_retries})")
                            continue  # Retry
                        else:
                            return False, None, f"{error_msg} (All retries failed)"
                    else:
                        return False, None, f"HTTP 403: {error_body}"
                
                elif response.status_code == 401:
                    error = "HTTP 401: Token invalid or expired"
                    logger.error(f"[API] {error}")
                    return False, None, error
                
                else:
                    error = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[API] Create character failed: {error}")
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"[API] Retrying... ({attempt+1}/{max_retries})")
                        continue
                    else:
                        return False, None, error
                    
            except requests.exceptions.Timeout:
                error = "Request timeout"
                logger.error(f"[API] {error}")
                
                if attempt < max_retries - 1:
                    continue
                else:
                    return False, None, f"{error} (All retries failed)"
            
            except Exception as e:
                logger.error(f"[API] Create character exception: {e}", exc_info=True)
                
                if attempt < max_retries - 1:
                    continue
                else:
                    return False, None, str(e)
        
        # Should not reach here
        return False, None, "All retries failed"
    
    def check_username_availability(self, username: str) -> Tuple[bool, bool, Optional[str]]:
        """
        Step 2: Check if username is available - FIXED WITH DEVICE ID
        
        Args:
            username: Username to check
        
        Returns:
            (success, is_available, error_message)
        """
        url = f"{self.BASE_URL}/project_y/profile/username/check"
        payload = {"username": username}
        
        try:
            logger.info(f"[API] Checking username: {username}")
            
            # ================================================================
            # FIX: ADD DEVICE ID HEADER
            # ================================================================
            headers = self.session.headers.copy()
            
            # Get device ID from cookies
            device_id = None
            if 'oai-did' in self.session.cookies:
                device_id = self.session.cookies.get('oai-did')
                headers['oai-device-id'] = device_id
                logger.info(f"[API] Device ID: {device_id}")
            else:
                logger.warning("[API] No oai-did cookie found!")
            
            # Add other important headers
            headers['accept'] = '*/*'
            headers['accept-language'] = 'en-US,en;q=0.9'
            
            # Log request details
            logger.info(f"[API] Request URL: {url}")
            logger.info(f"[API] Request payload: {payload}")
            logger.info(f"[API] Headers count: {len(headers)}")
            logger.info(f"[API] Cookies count: {len(self.session.cookies)}")
            
            # ================================================================
            # SEND REQUEST
            # ================================================================
            response = self.session.post(
                url, 
                json=payload, 
                headers=headers,
                timeout=15
            )
            
            logger.info(f"[API] Response status: {response.status_code}")
            
            # ================================================================
            # HANDLE RESPONSE
            # ================================================================
            if response.status_code == 200:
                data = response.json()
                is_available = data.get('available', False)
                
                logger.info(f"[API] Username check - Available: {is_available}")
                return True, is_available, None
            
            elif response.status_code == 403:
                error = "HTTP 403 Forbidden - Authentication failed"
                logger.error(f"[API] {error}")
                logger.error(f"[API] Response body: {response.text[:500]}")
                
                # Try to parse error details
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error = f"403: {error_data['error']}"
                except:
                    pass
                
                return False, False, error
            
            elif response.status_code == 401:
                error = "HTTP 401 Unauthorized - Token invalid or expired"
                logger.error(f"[API] {error}")
                return False, False, error
            
            else:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"[API] Username check failed: {error}")
                return False, False, error
                
        except requests.exceptions.Timeout:
            error = "Request timeout - Network issue"
            logger.error(f"[API] {error}")
            return False, False, error
            
        except requests.exceptions.ConnectionError:
            error = "Connection error - Check internet connection"
            logger.error(f"[API] {error}")
            return False, False, error
            
        except Exception as e:
            logger.error(f"[API] Username check exception: {e}", exc_info=True)
            return False, False, str(e)
    
    def upload_thumbnail(self, image_path: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Step 3: Upload thumbnail image
        
        Args:
            image_path: Path to thumbnail image file
        
        Returns:
            (success, upload_data, error_message)
        """
        if not os.path.exists(image_path):
            return False, None, f"Image file not found: {image_path}"
        
        url = f"{self.BASE_URL}/project_y/file/upload"
        
        try:
            logger.info(f"[API] Uploading thumbnail: {os.path.basename(image_path)}")
            
            # Read image file
            with open(image_path, 'rb') as f:
                files = {'file': (os.path.basename(image_path), f, 'image/jpeg')}
                
                # Remove Content-Type for multipart/form-data
                headers = {
                    'Authorization': f'Bearer {self.bearer_token}',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.post(url, files=files, headers=headers, timeout=60)
            
            if response.status_code == 200:
                data = response.json()
                asset_pointer = data.get('asset_pointer')
                file_id = data.get('file_id')
                
                logger.info(f"[API] Thumbnail uploaded - Asset: {asset_pointer}")
                return True, data, None
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"[API] Upload failed: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"[API] Upload exception: {e}", exc_info=True)
            return False, None, str(e)
    
    def finalize_character(
        self,
        cameo_id: str,
        username: str,
        display_name: str,
        profile_asset_pointer: str
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Step 4: Finalize character creation
        
        Args:
            cameo_id: Cameo ID from step 1
            username: Username for character
            display_name: Display name for character
            profile_asset_pointer: Asset pointer from step 3
        
        Returns:
            (success, character_data, error_message)
        """
        url = f"{self.BASE_URL}/characters/finalize"
        payload = {
            "cameo_id": cameo_id,
            "username": username,
            "display_name": display_name,
            "profile_asset_pointer": profile_asset_pointer,
            "instruction_set": None,
            "safety_instruction_set": None
        }
        
        try:
            logger.info(f"[API] Finalizing character: {username}")
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                character_id = data.get('character', {}).get('character_id')
                
                logger.info(f"[API] Character finalized - ID: {character_id}")
                return True, data, None
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"[API] Finalize failed: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"[API] Finalize exception: {e}", exc_info=True)
            return False, None, str(e)
    
    def get_cameo_info(self, cameo_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Step 5: Get cameo information
        
        Args:
            cameo_id: Cameo ID
        
        Returns:
            (success, cameo_data, error_message)
        """
        url = f"{self.BASE_URL}/project_y/cameos/owned/{cameo_id}"
        
        try:
            logger.info(f"[API] Getting cameo info: {cameo_id}")
            response = self.session.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                logger.info("[API] Cameo info retrieved")
                return True, data, None
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"[API] Get cameo failed: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"[API] Get cameo exception: {e}", exc_info=True)
            return False, None, str(e)
    
    def update_visibility_and_instructions(
        self,
        cameo_id: str,
        visibility: str = "public",
        instruction_text: str = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Step 7: Update cameo visibility and instruction set
        
        Args:
            cameo_id: Cameo ID
            visibility: 'public' or 'private'
            instruction_text: Instruction text for character (optional)
        
        Returns:
            (success, updated_data, error_message)
        """
        url = f"{self.BASE_URL}/project_y/cameos/by_id/{cameo_id}/update_v2"
        
        payload = {"visibility": visibility}
        
        if instruction_text:
            payload["instruction_set"] = {
                "value": [{
                    "type": "text",
                    "value": instruction_text
                }]
            }
        
        try:
            logger.info(f"[API] Updating cameo: {cameo_id} (visibility={visibility})")
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info("[API] Cameo updated")
                return True, data, None
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"[API] Update cameo failed: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"[API] Update cameo exception: {e}", exc_info=True)
            return False, None, str(e)
    
    def create_character_full_flow(
        self,
        generation_id: str,
        username: str,
        display_name: str,
        thumbnail_path: str,
        instruction_text: str = None,
        visibility: str = "public",
        timestamps: list = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Complete character creation flow (all 7 steps)
        
        Args:
            generation_id: Generation ID from Sora2
            username: Desired username
            display_name: Display name
            thumbnail_path: Path to thumbnail image
            instruction_text: Character instructions (optional)
            visibility: 'public' or 'private'
            timestamps: [start, end] timestamps
        
        Returns:
            (success, character_data, error_message)
            
            character_data format:
            {
                'character_id': str,
                'cameo_id': str,
                'username': str,
                'display_name': str,
                'profile_url': str,
                'thumbnail_url': str,
                'visibility': str
            }
        """
        try:
            # Step 1: Create character from generation
            success, step1_data, error = self.create_character_from_generation(
                generation_id, timestamps
            )
            if not success:
                return False, None, f"Step 1 failed: {error}"
            
            cameo_id = step1_data.get('id')
            if not cameo_id:
                return False, None, "Step 1: No cameo_id returned"
            
            # Wait for processing
            logger.info("[API] Waiting for character processing...")
            time.sleep(2)
            
            # Step 2: Check username availability
            success, is_available, error = self.check_username_availability(username)
            if not success:
                return False, None, f"Step 2 failed: {error}"
            
            if not is_available:
                return False, None, f"Username '{username}' is not available"
            
            # Step 3: Upload thumbnail
            success, upload_data, error = self.upload_thumbnail(thumbnail_path)
            if not success:
                return False, None, f"Step 3 failed: {error}"
            
            asset_pointer = upload_data.get('asset_pointer')
            thumbnail_url = upload_data.get('url')
            
            if not asset_pointer:
                return False, None, "Step 3: No asset_pointer returned"
            
            # Step 4: Finalize character
            success, finalize_data, error = self.finalize_character(
                cameo_id, username, display_name, asset_pointer
            )
            if not success:
                return False, None, f"Step 4 failed: {error}"
            
            character_id = finalize_data.get('character', {}).get('character_id')
            profile_url = finalize_data.get('character', {}).get('profile', {}).get('permalink')
            
            if not character_id:
                return False, None, "Step 4: No character_id returned"
            
            # Step 5: Get cameo info (optional, for verification)
            success, cameo_info, error = self.get_cameo_info(cameo_id)
            if not success:
                logger.warning(f"[API] Step 5 warning: {error}")
            
            # Step 7: Update visibility and instructions
            success, update_data, error = self.update_visibility_and_instructions(
                cameo_id, visibility, instruction_text
            )
            if not success:
                logger.warning(f"[API] Step 7 warning: {error}")
            
            # Prepare result
            result = {
                'character_id': character_id,
                'cameo_id': cameo_id,
                'username': username,
                'display_name': display_name,
                'profile_url': profile_url,
                'thumbnail_url': thumbnail_url,
                'visibility': visibility,
                'instruction_text': instruction_text,
                'generation_id': generation_id,
                'created_at': time.time()
            }
            
            logger.info(f"[API] Character created successfully: {username}")
            return True, result, None
            
        except Exception as e:
            logger.error(f"[API] Full flow exception: {e}", exc_info=True)
            return False, None, str(e)


if __name__ == "__main__":
    # Test
    print("Sora2 Character API Client")
    print("=" * 50)
    
    # Example usage
    token = "your_bearer_token_here"
    api = Sora2CharacterAPI(token)
    
    print("\nAPI client initialized")
    print("Ready to create characters!")