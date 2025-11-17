#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora API Client - Enhanced with Better Token Extraction
Trần Nguyên - Zalo: 0789.535.888
"""

import requests
import json
import logging
import time
import re
from typing import Optional, Dict, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SoraAPIClient:
    """
    Pure API client for Sora - no browser needed
    
    Usage:
        client = SoraAPIClient(bearer_token, cookies, sentinel_token)
        result = client.post_video(generation_id, prompt_text)
    """
    
    def __init__(self, 
                 bearer_token: str = None,
                 cookies: str = None,
                 sentinel_token: str = None):
        """
        Initialize Sora API Client
        
        Args:
            bearer_token: JWT token from Authorization header
            cookies: Full cookie string
            sentinel_token: openai-sentinel-chat-requirements-token
        """
        self.bearer_token = bearer_token
        self.cookies = cookies
        self.sentinel_token = sentinel_token
        
        self.base_url = "https://sora.chatgpt.com"
        self.api_base = f"{self.base_url}/backend/project_y"
        
        # Setup session
        self.session = requests.Session()
        self._update_session_headers()
    
    def _update_session_headers(self):
        """Update session with authentication headers - ENHANCED FOR CLOUDFLARE"""
        
        # ✅ CRITICAL: Full headers set matching real Chrome browser
        headers = {
            # Content & Accept
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,vi;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            
            # User Agent (latest Chrome)
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            
            # Origin & Referer (CRITICAL for Cloudflare)
            'Origin': 'https://sora.chatgpt.com',
            'Referer': 'https://sora.chatgpt.com/',
            
            # Security headers (Chrome fingerprint)
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            
            # Fetch metadata (CORS)
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            
            # Priority
            'Priority': 'u=1, i',
            
            # Cache
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
        }
        
        # Add authorization if available
        if self.bearer_token:
            headers['Authorization'] = f'Bearer {self.bearer_token}'
        
        # Add sentinel token if available
        if self.sentinel_token:
            headers['openai-sentinel-chat-requirements-token'] = self.sentinel_token
        
        # Update session headers
        self.session.headers.update(headers)
        
        # Parse and add cookies
        if self.cookies:
            cookie_dict = {}
            for cookie in self.cookies.split(';'):
                if '=' in cookie:
                    key, value = cookie.strip().split('=', 1)
                    cookie_dict[key] = value
            
            for key, value in cookie_dict.items():
                self.session.cookies.set(key, value)
        
        logger.debug(f"[API] Session configured with {len(headers)} headers and {len(self.session.cookies)} cookies")
    
    def post_video(self, 
                   generation_id: str, 
                   post_text: str = "") -> Optional[Dict]:
        """
        POST video to public (publish)
        
        Args:
            generation_id: Generation ID (e.g., "gen_01k7hvc77deessd4cwwhfst6wy")
            post_text: Optional text caption for the post
        
        Returns:
            Dict with post info if successful, None otherwise
        """
        try:
            endpoint = f"{self.api_base}/post"
            
            payload = {
                "attachments_to_create": [
                    {
                        "generation_id": generation_id,
                        "kind": "sora"
                    }
                ],
                "post_text": post_text
            }
            
            logger.info(f"[API] Posting video: {generation_id[:30]}...")
            logger.debug(f"POST {endpoint}")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                endpoint,
                json=payload,
                timeout=30
            )
            
            logger.info(f"[API] Response status: {response.status_code}")
            
            # Check for Cloudflare challenge
            if response.status_code == 403:
                logger.error(f"[API] ❌ 403 Forbidden - Cloudflare protection detected")
                
                # Check if it's Cloudflare challenge page
                if "Just a moment" in response.text or "cf-browser-verification" in response.text:
                    logger.error("[API] 🚫 Cloudflare challenge page detected!")
                    logger.error("[API] 💡 Possible solutions:")
                    logger.error("       • Token may have expired - extract new token")
                    logger.error("       • Need fresh cookies from browser")
                    logger.error("       • May need to solve CAPTCHA first")
                else:
                    logger.error(f"[API] Response preview: {response.text[:300]}")
                
                return None
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"[API] ✅ Video posted successfully!")
                
                # Extract useful info
                post_info = {
                    'post_id': data['post']['id'],
                    'permalink': data['post']['permalink'],
                    'posted_at': data['post']['posted_at'],
                    'video_url': data['post']['attachments'][0]['url'] if data['post']['attachments'] else None
                }
                
                logger.info(f"   Post ID: {post_info['post_id']}")
                logger.info(f"   Link: {post_info['permalink']}")
                
                return post_info
            
            else:
                logger.error(f"[API] ❌ Post failed: {response.status_code}")
                logger.error(f"   Response: {response.text[:500]}")
                return None
        
        except Exception as e:
            logger.error(f"[API] Post video error: {e}", exc_info=True)
            return None
    
    def delete_draft(self, draft_id: str) -> bool:
        """
        Delete draft by ID
        
        Args:
            draft_id: Draft ID to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            endpoint = f"{self.api_base}/draft/{draft_id}"
            
            logger.info(f"[API] Deleting draft: {draft_id}")
            
            response = self.session.delete(endpoint, timeout=30)
            
            if response.status_code in [200, 204]:
                logger.info(f"[API] ✅ Draft deleted: {draft_id}")
                return True
            else:
                logger.error(f"[API] ❌ Delete failed: {response.status_code}")
                logger.error(f"   Response: {response.text[:500]}")
                return False
        
        except Exception as e:
            logger.error(f"[API] Delete draft error: {e}", exc_info=True)
            return False
    
    def get_video_status(self, generation_id: str) -> Optional[Dict]:
        """
        Get video generation status
        
        Args:
            generation_id: Generation ID
        
        Returns:
            Dict with status info if successful, None otherwise
        """
        try:
            endpoint = f"{self.api_base}/generation/{generation_id}"
            
            response = self.session.get(endpoint, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logger.error(f"[API] Get status failed: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"[API] Get video status error: {e}", exc_info=True)
            return None
    
    def test_connection(self) -> bool:
        """
        Test if API connection works
        
        Returns:
            True if authenticated, False otherwise
        """
        try:
            # Try to access pending endpoint (lighter than drafts)
            endpoint = f"{self.base_url}/backend/nrl/pending"
            
            logger.info("[API] Testing connection...")
            
            response = self.session.get(endpoint, timeout=10)
            
            logger.info(f"[API] Test response: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("[API] ✅ Connection successful")
                return True
            elif response.status_code == 401:
                logger.warning("[API] ⚠️ Unauthorized - token invalid or expired")
                return False
            elif response.status_code == 403:
                logger.warning("[API] ⚠️ 403 Forbidden - Cloudflare blocking")
                if "Just a moment" in response.text:
                    logger.warning("[API] 💡 Cloudflare challenge detected - need fresh cookies")
                return False
            else:
                logger.warning(f"[API] ⚠️ Test failed: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"[API] Test error: {e}")
            return False
    
    @staticmethod
    def extract_tokens_from_browser(driver) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        🔥 ENHANCED: Extract bearer token, cookies, and sentinel token from browser
        
        Uses multiple methods to find the auth token:
        1. Auth0 SPA localStorage (primary method for Sora)
        2. All localStorage keys (scan for JWT)
        3. SessionStorage
        4. Network interception (if available)
        
        Args:
            driver: Selenium WebDriver instance
        
        Returns:
            Tuple of (bearer_token, cookies_string, sentinel_token)
        """
        try:
            logger.info("[EXTRACT] Starting token extraction from browser...")
            
            # ================================================================
            # METHOD 1: Extract Bearer Token from localStorage (Auth0 SPA)
            # ================================================================
            bearer_token = driver.execute_script("""
                console.log('[TOKEN] Searching for bearer token...');
                
                // Method 1: Auth0 SPA key pattern (most common for Sora)
                // Key format: @@auth0spajs@@::CLIENT_ID::AUDIENCE::openid profile email
                try {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        
                        // Look for Auth0 SPA keys
                        if (key && key.startsWith('@@auth0spajs@@')) {
                            console.log('[TOKEN] Found Auth0 key:', key);
                            
                            const value = localStorage.getItem(key);
                            if (value) {
                                try {
                                    const parsed = JSON.parse(value);
                                    
                                    // Check for access_token
                                    if (parsed.body && parsed.body.access_token) {
                                        const token = parsed.body.access_token;
                                        console.log('[TOKEN] ✅ Found access_token in Auth0 body');
                                        return token;
                                    }
                                    
                                    // Check for id_token
                                    if (parsed.body && parsed.body.id_token) {
                                        const token = parsed.body.id_token;
                                        console.log('[TOKEN] ✅ Found id_token in Auth0 body');
                                        return token;
                                    }
                                } catch(e) {
                                    console.log('[TOKEN] Failed to parse Auth0 value:', e);
                                }
                            }
                        }
                    }
                } catch(e) {
                    console.error('[TOKEN] Auth0 search error:', e);
                }
                
                // Method 2: Scan ALL localStorage for JWT tokens
                console.log('[TOKEN] Scanning all localStorage keys...');
                try {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        const value = localStorage.getItem(key);
                        
                        if (value && typeof value === 'string') {
                            // Direct JWT token (starts with eyJ)
                            if (value.startsWith('eyJ') && value.length > 100) {
                                console.log('[TOKEN] ✅ Found JWT in key:', key);
                                return value;
                            }
                            
                            // Try parsing as JSON
                            try {
                                const parsed = JSON.parse(value);
                                
                                // Look for token fields
                                const tokenFields = ['token', 'access_token', 'id_token', 'auth_token', 'bearer_token'];
                                for (const field of tokenFields) {
                                    if (parsed[field] && typeof parsed[field] === 'string' && parsed[field].startsWith('eyJ')) {
                                        console.log('[TOKEN] ✅ Found token in field:', field);
                                        return parsed[field];
                                    }
                                }
                            } catch(e) {
                                // Not JSON, skip
                            }
                        }
                    }
                } catch(e) {
                    console.error('[TOKEN] Full scan error:', e);
                }
                
                // Method 3: SessionStorage
                console.log('[TOKEN] Checking sessionStorage...');
                try {
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        const value = sessionStorage.getItem(key);
                        
                        if (value && value.startsWith('eyJ')) {
                            console.log('[TOKEN] ✅ Found JWT in sessionStorage:', key);
                            return value;
                        }
                    }
                } catch(e) {
                    console.error('[TOKEN] SessionStorage error:', e);
                }
                
                // Method 4: Check window object
                console.log('[TOKEN] Checking window object...');
                if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                    try {
                        const props = JSON.stringify(window.__NEXT_DATA__.props);
                        const match = props.match(/"(?:access_token|token)"\\s*:\\s*"(eyJ[^"]+)"/);
                        if (match) {
                            console.log('[TOKEN] ✅ Found token in __NEXT_DATA__');
                            return match[1];
                        }
                    } catch(e) {}
                }
                
                console.log('[TOKEN] ❌ No bearer token found');
                return null;
            """)
            
            # ================================================================
            # METHOD 2: Extract Sentinel Token
            # ================================================================
            sentinel_token = driver.execute_script("""
                console.log('[SENTINEL] Searching for sentinel token...');
                
                // Look in localStorage
                try {
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && key.toLowerCase().includes('sentinel')) {
                            const value = localStorage.getItem(key);
                            console.log('[SENTINEL] ✅ Found in localStorage:', key);
                            return value;
                        }
                    }
                } catch(e) {}
                
                // Look in window object
                if (window.sentinelToken) {
                    console.log('[SENTINEL] ✅ Found in window.sentinelToken');
                    return window.sentinelToken;
                }
                
                console.log('[SENTINEL] ❌ Not found (optional)');
                return null;
            """)
            
            # ================================================================
            # METHOD 3: Get Cookies
            # ================================================================
            cookies = driver.get_cookies()
            cookies_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
            
            # ================================================================
            # RESULTS
            # ================================================================
            logger.info(f"[EXTRACT] Results:")
            logger.info(f"  Bearer token: {'✅ Found' if bearer_token else '❌ Not found'}")
            if bearer_token:
                logger.info(f"    Length: {len(bearer_token)} chars")
                logger.info(f"    Preview: {bearer_token[:30]}...{bearer_token[-20:]}")
            
            logger.info(f"  Sentinel token: {'✅ Found' if sentinel_token else '⚠️ Not found (optional)'}")
            logger.info(f"  Cookies: {len(cookies)} cookies")
            
            # Validate bearer token
            if bearer_token:
                # Check if it's a valid JWT
                if not bearer_token.startswith('eyJ'):
                    logger.warning(f"[EXTRACT] ⚠️ Token doesn't look like JWT: {bearer_token[:30]}")
                    
                # Check token parts (JWT has 3 parts separated by dots)
                parts = bearer_token.count('.')
                if parts != 2:
                    logger.warning(f"[EXTRACT] ⚠️ JWT should have 3 parts, found {parts + 1}")
            
            return bearer_token, cookies_string, sentinel_token
        
        except Exception as e:
            logger.error(f"[EXTRACT] Token extraction error: {e}", exc_info=True)
            return None, None, None
    
    @staticmethod
    def extract_token_from_network(driver, timeout: int = 30) -> Optional[str]:
        """
        🆕 Extract bearer token by intercepting network requests
        
        This is a fallback method when localStorage doesn't work.
        Monitors network traffic for Authorization headers.
        
        Args:
            driver: Selenium WebDriver
            timeout: Max time to wait for token (seconds)
        
        Returns:
            Bearer token if found, None otherwise
        """
        try:
            logger.info("[NETWORK] Monitoring network for bearer token...")
            
            # Inject network monitoring script
            driver.execute_script("""
                window._capturedToken = null;
                
                // Intercept fetch
                const originalFetch = window.fetch;
                window.fetch = function(...args) {
                    // Capture Authorization header if present
                    if (args[1] && args[1].headers) {
                        const headers = args[1].headers;
                        if (headers.Authorization || headers.authorization) {
                            const token = headers.Authorization || headers.authorization;
                            if (token.startsWith('Bearer ')) {
                                window._capturedToken = token.substring(7);
                                console.log('[NETWORK] ✅ Captured token from fetch');
                            }
                        }
                    }
                    return originalFetch.apply(this, args);
                };
                
                // Intercept XMLHttpRequest
                const originalOpen = XMLHttpRequest.prototype.open;
                const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;
                
                XMLHttpRequest.prototype.setRequestHeader = function(header, value) {
                    if (header.toLowerCase() === 'authorization' && value.startsWith('Bearer ')) {
                        window._capturedToken = value.substring(7);
                        console.log('[NETWORK] ✅ Captured token from XHR');
                    }
                    return originalSetRequestHeader.apply(this, arguments);
                };
                
                console.log('[NETWORK] Monitor installed');
            """)
            
            # Wait for token to be captured
            start_time = time.time()
            while time.time() - start_time < timeout:
                token = driver.execute_script("return window._capturedToken;")
                
                if token:
                    logger.info(f"[NETWORK] ✅ Token captured! ({len(token)} chars)")
                    return token
                
                time.sleep(1)
            
            logger.warning("[NETWORK] ⚠️ Timeout - no token captured")
            return None
            
        except Exception as e:
            logger.error(f"[NETWORK] Monitor error: {e}")
            return None


# ============================================================================
# EXAMPLE USAGE
# ============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║         Sora API Client - Enhanced Token Extraction              ║
    ╚════════════════════════════════════════════════════════════════════╝
    
    USAGE 1: Extract tokens from browser
    ─────────────────────────────────────
    from selenium import webdriver
    
    driver = webdriver.Chrome()
    driver.get("https://sora.chatgpt.com")
    # ... login manually ...
    
    bearer, cookies, sentinel = SoraAPIClient.extract_tokens_from_browser(driver)
    
    
    USAGE 2: Use API client
    ────────────────────────
    client = SoraAPIClient(
        bearer_token=bearer,
        cookies=cookies,
        sentinel_token=sentinel
    )
    
    # Test connection
    if client.test_connection():
        print("✅ API Ready")
    
    # Post video
    result = client.post_video(
        generation_id="gen_01k7hvc...",
        post_text="My awesome video"
    )
    
    if result:
        print(f"📤 Video posted: {result['permalink']}")
    
    
    USAGE 3: Network fallback
    ──────────────────────────
    # If localStorage doesn't work, try network monitor
    token = SoraAPIClient.extract_token_from_network(driver, timeout=30)
    """)