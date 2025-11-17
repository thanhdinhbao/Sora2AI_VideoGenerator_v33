#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SORA API CLIENT - COMPLETE & FIXED VERSION
===========================================
✅ All methods from original file
✅ Fixed wait_for_completion() logic
✅ Fixed polling and status checking
✅ Better error handling
"""

import json
import logging
import time
from typing import Optional, Dict, List, Any
from pathlib import Path
import uuid

from curl_cffi import requests

logger = logging.getLogger(__name__)


class SoraAPIClient:
    """
    Complete Sora API Client - Full feature set
    """
    
    # Base URLs
    SORA_BASE = "https://sora.chatgpt.com"
    BACKEND_PREFIX = "/backend"
    
    # Browser impersonation
    IMPERSONATE = "chrome136"
    
    def __init__(self, bearer_token: str, device_id: str = None):
        """
        Initialize API client
        
        Args:
            bearer_token: JWT bearer token
            device_id: OAI-Device-Id (auto-generate if None)
        """
        self.bearer_token = bearer_token
        self.device_id = device_id or str(uuid.uuid4())
        
        # Create session with curl_cffi + impersonation
        self.session = requests.Session(impersonate=self.IMPERSONATE)
        
        logger.info(f"[API] ✅ Client initialized")
        logger.info(f"[API]    Token: {len(bearer_token)} chars")
        logger.info(f"[API]    Device: {self.device_id}")
    
    def _get_endpoint_url(self, path: str) -> str:
        """Build full endpoint URL"""
        return f"{self.SORA_BASE}{self.BACKEND_PREFIX}{path}"
    
    def _build_headers(self, extra: Dict = None) -> Dict:
        """Build request headers"""
        headers = {
            'authorization': f'Bearer {self.bearer_token}',
            'content-type': 'application/json',
            'accept': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'origin': 'https://sora.chatgpt.com',
            'referer': 'https://sora.chatgpt.com/',
            'oai-device-id': self.device_id,
        }
        
        if extra:
            headers.update(extra)
        
        return headers
    
    # ========================================================================
    # IMAGE UPLOAD
    # ========================================================================
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """
        ✅ Upload image using curl subprocess
        
        Args:
            image_path: Path to local image file
            
        Returns:
            media_id if success, None if failed
        """
        try:
            import subprocess
            
            url = self._get_endpoint_url("/uploads")
            
            logger.info(f"[API] 📤 Uploading: {image_path}")
            
            # ============================================================
            # Validate file
            # ============================================================
            path = Path(image_path)
            if not path.exists():
                logger.error(f"[API] ❌ File not found: {image_path}")
                return None
            
            filename = path.name
            
            logger.info(f"[API] 📊 File: {filename}")
            logger.info(f"[API] 🚀 Using curl command (subprocess)...")
            
            # ============================================================
            # Build curl command
            # ============================================================
            cmd = [
                "curl", "-X", "POST",
                url,
                "-H", f"Authorization: Bearer {self.bearer_token}",
                "-H", f"OAI-Device-Id: {self.device_id}",
                "-H", "Accept: */*",
                "-H", "Origin: https://sora.chatgpt.com",
                "-H", "Referer: https://sora.chatgpt.com/profile",
                "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "-F", f"file=@{image_path}",
                "-F", f"file_name={filename}",
            ]
            
            # ============================================================
            # Run curl command
            # ============================================================
            logger.info(f"[API] 🚀 Running curl...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            logger.info(f"[API] 📥 Exit code: {result.returncode}")
            
            # ============================================================
            # Handle response
            # ============================================================
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    media_id = data.get('id')
                    
                    if not media_id:
                        logger.error(f"[API] ❌ No 'id' in response")
                        logger.error(f"[API] Response: {data}")
                        return None
                    
                    logger.info(f"[API] ✅ Upload success!")
                    logger.info(f"[API]    Media ID: {media_id}")
                    logger.info(f"[API]    Type: {data.get('type', 'N/A')}")
                    logger.info(f"[API]    Size: {data.get('width', 0)}x{data.get('height', 0)}")
                    
                    return media_id
                
                except json.JSONDecodeError as e:
                    logger.error(f"[API] ❌ JSON parse failed: {e}")
                    logger.error(f"[API] Raw output: {result.stdout[:500]}")
                    return None
            
            else:
                logger.error(f"[API] ❌ Curl command failed")
                logger.error(f"[API] STDOUT: {result.stdout[:500]}")
                logger.error(f"[API] STDERR: {result.stderr[:500]}")
                return None
        
        except FileNotFoundError:
            logger.error(f"[API] ❌ File not found: {image_path}")
            return None
        
        except subprocess.TimeoutExpired:
            logger.error(f"[API] ❌ Upload timeout (60s)")
            return None
        
        except Exception as e:
            logger.error(f"[API] ❌ Upload error: {e}", exc_info=True)
            return None
    
    # ========================================================================
    # TASK CREATION
    # ========================================================================
    
    def _calculate_n_frames(self, duration: int) -> int:
        """
        Calculate n_frames based on duration
        
        Sora 2 n_frames mapping:
        - 10s = 300 frames
        - 15s = 450 frames
        
        Args:
            duration: Video duration in seconds (10 or 15)
            
        Returns:
            Number of frames
        """
        if duration == 15:
            return 450
        else:
            return 300  # Default to 10s
    
    def create_task(self,
                   prompt: str,
                   aspect_ratio: str = "16:9",
                   duration: int = 5,
                   image_url: str = None,
                   callback=None) -> Optional[Dict]:
        """
        ✅ CREATE GENERATION TASK
        
        Endpoint: POST /backend/nf/create
        
        Args:
            prompt: Text prompt
            aspect_ratio: "16:9", "9:16", "1:1"
            duration: 5 or 10 seconds
            image_url: Optional image path (local file)
            callback: Callback function
            
        Returns:
            Task dict with task_id, or None if failed
        """
        try:
            if callback:
                callback("[API] 🚀 Creating generation task...", "info")
            
            url = self._get_endpoint_url("/nf/create")
            
            # Build payload
            orientation_map = {
                "16:9": "landscape",
                "9:16": "portrait",
                "1:1": "square"
            }

            payload = {
                "kind": "video",
                "prompt": prompt,
                "title": None,
                "orientation": orientation_map.get(aspect_ratio, "landscape"),
                "size": "small",
                "n_frames": self._calculate_n_frames(duration),  # ✅ FIX: Dùng helper function
                "inpaint_items": [],
                "remix_target_id": None,
                "metadata": None,
                "cameo_ids": None,
                "cameo_replacements": None,
                "model": "sy_8",
                "style_id": None,
                "audio_caption": None,
                "audio_transcript": None,
                "video_caption": None,
                "storyboard_id": None
            }

            # Handle image upload
            if image_url:
                if not image_url.startswith('http'):
                    # Local file → upload
                    logger.info(f"[API] Image detected, uploading first...")
                    media_id = self.upload_image(image_url)
                    
                    if media_id:
                        payload["inpaint_items"] = [{
                            "kind": "upload",
                            "upload_id": media_id
                        }]
                        logger.info(f"[API] ✅ Image uploaded: {media_id}")
                    else:
                        logger.warning(f"[API] ⚠️ Image upload failed, continue without image")
                        if callback:
                            callback("[API] ⚠️ Image upload failed", "warn")
                else:
                    # Remote URL (not implemented yet)
                    logger.warning(f"[API] Remote URL not supported yet")
            
            logger.info(f"[API] POST {url}")
            logger.debug(f"[API] Payload: {json.dumps(payload, indent=2)}")
            
            # Make request
            response = self.session.post(
                url,
                json=payload,
                headers=self._build_headers(),
                timeout=30
            )
            
            logger.info(f"[API] Response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                
                # Ensure data is dict
                if isinstance(data, str):
                    logger.error(f"[API] ❌ Response is string, not dict")
                    return None
                
                task_id = data.get('id') or data.get('task_id')
                
                if not task_id:
                    logger.error(f"[API] ❌ No task_id in response")
                    return None
                
                if callback:
                    callback(f"[API] ✅ Task created: {task_id}", "ok")
                
                logger.info(f"[API] ✅ Task ID: {task_id}")
                return data
            
            elif response.status_code == 403:
                logger.error(f"[API] ❌ 403 Forbidden")
                if callback:
                    callback("[API] ❌ Token invalid or expired", "err")
                return None
            
            else:
                logger.error(f"[API] ❌ Create failed: {response.status_code}")
                try:
                    logger.error(f"[API] Response: {response.text[:500]}")
                except:
                    pass
                return None
        
        except Exception as e:
            logger.error(f"[API] Create task error: {e}", exc_info=True)
            if callback:
                callback(f"[API] ❌ Error: {str(e)}", "err")
            return None
    
    # ========================================================================
    # STATUS CHECKING
    # ========================================================================
    
    def get_pending_tasks(self, callback=None) -> Optional[List[Dict]]:
        """
        ✅ GET PENDING TASKS
        
        Endpoint: POST /backend/nf/pending
        
        Returns:
            List of pending tasks
        """
        try:
            url = self._get_endpoint_url("/nf/pending")
            
            response = self.session.post(
                url,
                json={},
                headers=self._build_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                tasks = data if isinstance(data, list) else []
                logger.debug(f"[API] Pending tasks: {len(tasks)}")
                return tasks
            
            else:
                logger.debug(f"[API] Get pending failed: {response.status_code}")
                return None
        
        except Exception as e:
            logger.debug(f"[API] Get pending error: {e}")
            return None
    
    def check_task_status(self, task_id: str, callback=None) -> Optional[Dict]:
        """
        ✅ CHECK TASK STATUS (SINGLE CHECK)
        
        Endpoint: GET /backend/nf/check?task_id={task_id}
        
        Args:
            task_id: Task ID
            callback: Callback function
            
        Returns:
            Task status dict
        """
        try:
            url = self._get_endpoint_url(f"/nf/check?task_id={task_id}")
            
            response = self.session.get(
                url,
                headers=self._build_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                logger.debug(f"[API] Task {task_id[:20]}...: {status}")
                return data
            
            else:
                logger.debug(f"[API] Check task failed: {response.status_code}")
                return None
        
        except Exception as e:
            logger.debug(f"[API] Check task error: {e}")
            return None
    
    def get_drafts(self, callback=None) -> Optional[List[Dict]]:
        """
        ✅ GET DRAFTS (completed videos)
        
        Endpoint: GET /backend/project_y/profile/drafts
        
        Returns:
            List of draft videos
        """
        try:
            url = self._get_endpoint_url("/project_y/profile/drafts")
            
            response = self.session.get(
                url,
                headers=self._build_headers(),
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle different response formats
                if isinstance(data, dict):
                    drafts = data.get('items', []) or data.get('drafts', [])
                elif isinstance(data, list):
                    drafts = data
                else:
                    drafts = []
                
                logger.debug(f"[API] Drafts: {len(drafts)}")
                return drafts
            
            else:
                logger.debug(f"[API] Get drafts failed: {response.status_code}")
                return None
        
        except Exception as e:
            logger.debug(f"[API] Get drafts error: {e}")
            return None
    
    # ========================================================================
    # 🔥 FIXED: WAIT FOR COMPLETION
    # ========================================================================
    
    def wait_for_completion(self,
                           task_id: str,
                           timeout: int = 600,
                           poll_interval: int = 3,
                           callback=None) -> Optional[Dict]:
        """
        ✅ WAIT FOR TASK COMPLETION - FIXED VERSION
        
        Logic:
        1. Poll /pending endpoint every 3s
        2. Check task status in response
        3. When completed, get draft from /drafts
        4. Return draft with video_url
        
        Args:
            task_id: Task ID
            timeout: Max wait time (seconds)
            poll_interval: Check interval (seconds)
            callback: Callback function
            
        Returns:
            Draft dict with video_url, or None
        """
        try:
            if callback:
                callback(f"[API] ⏳ Waiting for completion (timeout: {timeout}s)...", "info")
            
            start_time = time.time()
            last_log_time = 0
            last_progress = 0
            
            while time.time() - start_time < timeout:
                elapsed = int(time.time() - start_time)
                
                # ============================================================
                # STEP 1: Check pending tasks
                # ============================================================
                try:
                    pending_tasks = self.get_pending_tasks(callback=None)
                    
                    if pending_tasks:
                        # Find our task
                        our_task = None
                        for task in pending_tasks:
                            if task.get('id') == task_id or task.get('task_id') == task_id:
                                our_task = task
                                break
                        
                        if our_task:
                            status = our_task.get('status', 'unknown')
                            progress = our_task.get('progress_pct', 0)
                            
                            # Log progress if changed
                            if progress != last_progress and progress > 0:
                                if callback:
                                    callback(f"[API] 📊 Progress: {progress*100:.1f}%", "info")
                                logger.info(f"[API] Progress: {progress*100:.1f}%")
                                last_progress = progress
                            
                            # Check if failed or violation
                            if status == 'failed':
                                failure_reason = our_task.get('failure_reason', 'Unknown')
                                reason_str = our_task.get('reason_str', '')
                                
                                # Check violation
                                if 'violation' in failure_reason.lower() or 'violation' in reason_str.lower():
                                    logger.warning(f"[API] ⚠️ Content violation: {failure_reason}")
                                    if callback:
                                        callback(f"[API] ⚠️ Violation - stopping", "warn")
                                    return None
                                
                                logger.error(f"[API] ❌ Task failed: {failure_reason}")
                                if callback:
                                    callback(f"[API] ❌ Failed: {failure_reason}", "err")
                                return None
                            
                            # Still processing
                            if elapsed - last_log_time >= 30:
                                logger.info(f"[API] Processing... {elapsed}s / {timeout}s")
                                last_log_time = elapsed
                
                except Exception as e:
                    logger.debug(f"[API] Pending check error: {e}")
                
                # ============================================================
                # STEP 2: Check drafts (video completed?)
                # ============================================================
                try:
                    drafts = self.get_drafts(callback=None)
                    
                    if drafts:
                        # Find matching draft - IMPROVED MATCHING
                        for draft in drafts:
                            # Get draft identifiers
                            draft_id = draft.get('id')
                            generation_id = draft.get('generation_id')
                            draft_task_id = draft.get('task_id')
                            kind = draft.get('kind')
                            
                            # ✅ CHECK VIOLATION FIRST
                            if kind == 'sora_content_violation':
                                # Match task_id
                                if draft_task_id == task_id or draft_id == task_id or generation_id == task_id:
                                    reason_str = draft.get('reason_str', 'Content violation')
                                    logger.warning(f"[API] ⚠️ Violation: {reason_str}")
                                    if callback:
                                        callback(f"[API] ⚠️ Violation detected", "warn")
                                    return None
                            
                            # ✅ CHECK: Must be sora_draft
                            if kind != 'sora_draft':
                                continue
                            
                            # ✅ CHECK: Match task_id with generation_id or task_id
                            is_match = False
                            if generation_id == task_id:
                                is_match = True
                            elif draft_task_id == task_id:
                                is_match = True
                            elif draft_id == task_id:
                                is_match = True
                            
                            if is_match:
                                # ✅ CHECK VIOLATION FIRST
                                reason_str = draft.get('reason_str', '')
                                if 'violation' in reason_str.lower():
                                    logger.warning(f"[API] ⚠️ Content violation detected")
                                    if callback:
                                        callback(f"[API] ⚠️ Violation - stopping", "warn")
                                    return None
                                
                                # ✅ FOUND! Get video URL
                                video_url = (draft.get('downloadable_url') or 
                                           draft.get('url') or 
                                           draft.get('video_url'))
                                
                                if video_url:
                                    logger.info(f"[API] ✅ Video completed!")
                                    logger.info(f"[API]    Draft ID: {draft_id}")
                                    logger.info(f"[API]    Generation ID: {generation_id}")
                                    logger.info(f"[API]    Video URL: {video_url[:80]}...")
                                    
                                    if callback:
                                        callback(f"[API] ✅ Video ready!", "ok")
                                    
                                    return draft
                                else:
                                    logger.debug(f"[API] Draft found but no video URL yet")
                        
                        # Check for error drafts
                        for draft in drafts:
                            if draft.get('kind') == 'sora_error':
                                generation_id = draft.get('generation_id')
                                if generation_id == task_id:
                                    error_reason = draft.get('error_reason', 'Unknown error')
                                    logger.error(f"[API] ❌ Generation failed: {error_reason}")
                                    if callback:
                                        callback(f"[API] ❌ Failed: {error_reason}", "err")
                                    return None
                
                except Exception as e:
                    logger.debug(f"[API] Drafts check error: {e}")
                
                # ============================================================
                # STEP 3: Periodic status log
                # ============================================================
                if elapsed - last_log_time >= 30:
                    if callback:
                        status_msg = f"[API] ⏳ Processing... {elapsed}s / {timeout}s"
                        if last_progress > 0:
                            status_msg += f" | Progress: {last_progress*100:.0f}%"
                        callback(status_msg, "info")
                    
                    last_log_time = elapsed
                
                # Wait before next check
                time.sleep(poll_interval)
            
            # ============================================================
            # TIMEOUT
            # ============================================================
            logger.error(f"[API] ⏱️ Timeout after {timeout}s")
            if callback:
                callback(f"[API] ⏱️ Timeout after {timeout}s", "err")
            
            return None
        
        except Exception as e:
            logger.error(f"[API] Wait error: {e}", exc_info=True)
            if callback:
                callback(f"[API] ❌ Error: {str(e)[:200]}", "err")
            return None
    
    # ========================================================================
    # DOWNLOAD & DELETE
    # ========================================================================
    
    def download_video(self,
                      video_url: str,
                      save_path: str,
                      callback=None) -> bool:
        """
        ✅ DOWNLOAD VIDEO
        
        Args:
            video_url: Video URL
            save_path: Path to save
            callback: Callback function
            
        Returns:
            True if success
        """
        try:
            if callback:
                callback(f"[API] 📥 Downloading video...", "info")
            
            logger.info(f"[API] Downloading: {video_url[:80]}...")
            
            response = self.session.get(
                video_url,
                stream=True,
                timeout=600
            )
            
            if response.status_code != 200:
                logger.error(f"[API] Download failed: {response.status_code}")
                return False
            
            # Write to file
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            if callback:
                callback(f"[API] ✅ Saved: {Path(save_path).name}", "ok")
            
            logger.info(f"[API] ✅ Downloaded: {save_path}")
            return True
        
        except Exception as e:
            logger.error(f"[API] Download error: {e}", exc_info=True)
            if callback:
                callback(f"[API] ❌ Download failed", "err")
            return False
    
    def delete_draft(self, draft_id: str, callback=None) -> bool:
        """
        Delete draft by ID - FIXED with generation_id + response validation
        """
        if not draft_id:
            logger.error("[DELETE] ❌ No draft_id")
            return False
        
        if not self.bearer_token:
            logger.error("[DELETE] ❌ No bearer token")
            return False
        
        try:
            if callback:
                callback(f"[DELETE] 🗑️ Deleting: {draft_id}", "info")
            
            # ✅ IMPORTANT: Check if draft_id is generation_id format
            # generation_id: 32 hex chars (e.g., 690dc096...)
            # draft_id: gen_xxx format (e.g., gen_01k9...)
            
            # If it's gen_xxx format, we need to get generation_id
            if draft_id.startswith('gen_'):
                logger.warning(f"[DELETE] ⚠️ Got draft_id format: {draft_id}")
                logger.warning(f"[DELETE] Need generation_id instead!")
                
                # Try to get generation_id from drafts list
                drafts = self.get_drafts(callback=None)
                generation_id = None
                
                if drafts:
                    for draft in drafts:
                        if draft.get('id') == draft_id:
                            generation_id = draft.get('generation_id')
                            # 🔍 DEBUG
                            print(f"DEBUG - Draft keys: {draft.keys()}")
                            print(f"DEBUG - id: {draft.get('id')}")
                            print(f"DEBUG - generation_id: {draft.get('generation_id')}")
                            print(f"DEBUG - slug: {draft.get('slug')}")
                            
                            logger.info(f"[DELETE] ✅ Found generation_id: {generation_id}")
                            break
                
                if not generation_id:
                    logger.error(f"[DELETE] ❌ Cannot find generation_id for {draft_id}")
                    if callback:
                        callback("[DELETE] ❌ Invalid draft_id format", "err")
                    return False
                
                # Use generation_id instead
                draft_id = generation_id
            
            logger.info(f"[DELETE] Final ID to delete: {draft_id}")
            # ✅ THÊM: Tạo session mới cho delete request
            delete_session = requests.Session(impersonate=self.IMPERSONATE)
            
            # Setup headers
            headers = {
                'accept': '*/*',
                'accept-language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
                'authorization': f'Bearer {self.bearer_token}',
                'oai-device-id': self.device_id,
                'origin': 'https://sora.chatgpt.com',
                'referer': f'https://sora.chatgpt.com/d/{draft_id}',
                'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            delete_url = f'https://sora.chatgpt.com/backend/project_y/profile/drafts/{draft_id}'
            
            logger.info(f"[DELETE] DELETE {delete_url}")
            
            # ✅ USE curl_cffi session (bypass Cloudflare)
            response = delete_session.delete(  # ✅ Dùng session mới
                delete_url,
                headers=headers,
                timeout=30
            )
            
            status_code = response.status_code
            logger.info(f"[DELETE] HTTP {status_code}")
            
            # ✅ CHECK response body, not just status code
            try:
                response_data = response.json()
                logger.info(f"[DELETE] Response: {response_data}")
                
                # Check for error in response
                if response_data.get('status') == 'error':
                    error_msg = response_data.get('message', 'Unknown error')
                    logger.error(f"[DELETE] ❌ API error: {error_msg}")
                    if callback:
                        callback(f"[DELETE] ❌ {error_msg}", "err")
                    return False
            
            except:
                # Not JSON or empty response = success for 200/204
                pass
            
            # Check status code
            if status_code in [200, 204]:
                logger.info(f"[DELETE] ✅ Draft deleted completely!")
                if callback:
                    callback(f"[DELETE] ✅ Deleted", "ok")
                return True
            
            elif status_code == 404:
                logger.warning(f"[DELETE] ⚠️ Draft not found (already deleted?)")
                if callback:
                    callback(f"[DELETE] ⚠️ Not found", "warn")
                return True  # Consider as success
            
            else:
                logger.error(f"[DELETE] ❌ Failed: HTTP {status_code}")
                logger.error(f"[DELETE] Body: {response.text[:500]}")
                if callback:
                    callback(f"[DELETE] ❌ HTTP {status_code}", "err")
                return False
        
        except Exception as e:
            logger.error(f"[DELETE] ❌ Error: {e}", exc_info=True)
            if callback:
                callback(f"[DELETE] ❌ {str(e)[:100]}", "err")
            return False
    
    def post_video(self, generation_id: str, post_text: str = "", callback=None) -> Optional[Dict]:
        """
        ✅ POST VIDEO TO FEED
        
        Endpoint: POST /backend/project_y/post
        
        Args:
            generation_id: Generation ID (e.g., "gen_...")
            post_text: Caption text (optional)
            callback: Callback function
            
        Returns:
            Post data dict or None if failed
        """
        try:
            url = self._get_endpoint_url("/project_y/post")
            
            if callback:
                callback(f"[POST] 📤 Posting video...", "info")
            
            logger.info(f"[POST] Generation ID: {generation_id}")
            logger.info(f"[POST] Text: {post_text[:50]}..." if post_text else "[POST] No caption")
            
            # Build payload
            payload = {
                "attachments_to_create": [
                    {
                        "generation_id": generation_id,
                        "kind": "sora"
                    }
                ],
                "post_text": post_text
            }
            
            # Make request
            response = self.session.post(
                url,
                json=payload,
                headers=self._build_headers(),
                timeout=30
            )
            
            logger.info(f"[POST] Response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                post_info = data.get('post', {})
                post_id = post_info.get('id')
                permalink = post_info.get('permalink')
                
                logger.info(f"[POST] ✅ Video posted!")
                logger.info(f"[POST]    Post ID: {post_id}")
                logger.info(f"[POST]    Permalink: {permalink}")
                
                if callback:
                    callback(f"[POST] ✅ Posted! ID: {post_id}", "ok")
                
                return data
            
            elif response.status_code == 400:
                logger.error(f"[POST] ❌ Bad Request (400)")
                try:
                    error_data = response.json()
                    logger.error(f"[POST] Error: {json.dumps(error_data, indent=2)}")
                except:
                    logger.error(f"[POST] Response: {response.text[:500]}")
                
                if callback:
                    callback(f"[POST] ❌ Bad Request", "err")
                return None
            
            elif response.status_code == 403:
                logger.error(f"[POST] ❌ Forbidden (403)")
                if callback:
                    callback(f"[POST] ❌ Forbidden", "err")
                return None
            
            elif response.status_code == 404:
                logger.error(f"[POST] ❌ Not Found (404)")
                if callback:
                    callback(f"[POST] ❌ Generation not found", "err")
                return None
            
            else:
                logger.error(f"[POST] ❌ Failed: HTTP {response.status_code}")
                try:
                    logger.error(f"[POST] Response: {response.text[:500]}")
                except:
                    pass
                
                if callback:
                    callback(f"[POST] ❌ HTTP {response.status_code}", "err")
                return None
        
        except Exception as e:
            logger.error(f"[POST] ❌ Error: {e}", exc_info=True)
            if callback:
                callback(f"[POST] ❌ {str(e)[:100]}", "err")
            return None
    
    def delete_post(self, slug: str, callback=None) -> bool:
        """
        ✅ DELETE POST (by slug)
        
        Endpoint: DELETE /backend/project_y/post/{slug}
        
        Args:
            slug: Post slug (e.g., "s_...")
            callback: Callback function
            
        Returns:
            True if deleted
        """
        try:
            url = self._get_endpoint_url(f"/project_y/post/{slug}")
            
            logger.info(f"[API] DELETE {url}")
            
            response = self.session.delete(
                url,
                headers=self._build_headers(),
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                if callback:
                    callback(f"[API] ✅ Deleted: {slug}", "ok")
                logger.info(f"[API] ✅ Deleted")
                return True
            
            else:
                logger.warning(f"[API] Delete failed: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"[API] Delete error: {e}")
            return False


# ============================================================================
# ONE-SHOT FUNCTION
# ============================================================================

def generate_video_full_api(bearer_token: str,
                            prompt: str,
                            aspect_ratio: str = "16:9",
                            duration: int = 5,
                            image_path: str = None,
                            save_dir: str = "./downloads",
                            delete_after: bool = True,
                            callback=None) -> Optional[str]:
    """
    ✅ GENERATE VIDEO - 100% API (NO BROWSER!)
    
    Args:
        bearer_token: Bearer token
        prompt: Text prompt
        aspect_ratio: "16:9", "9:16", "1:1"
        duration: 5 or 10 seconds
        image_path: Optional local image file
        save_dir: Save directory
        delete_after: Delete draft after download
        callback: Callback function
        
    Returns:
        Video file path or None
    """
    try:
        # Initialize client
        client = SoraAPIClient(bearer_token)
        
        # Step 1: Create task
        if callback:
            callback("[1/4] Creating task...", "info")
        
        task = client.create_task(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration=duration,
            image_url=image_path,
            callback=callback
        )
        
        if not task:
            return None
        
        task_id = task.get('id') or task.get('task_id')
        
        # Step 2: Wait for completion
        if callback:
            callback("[2/4] Waiting for completion...", "info")
        
        draft = client.wait_for_completion(task_id, timeout=600, callback=callback)
        
        if not draft:
            return None
        
        # Step 3: Get video URL
        video_url = draft.get('url') or draft.get('video_url') or draft.get('downloadable_url')
        draft_id = draft.get('id')
        
        if not video_url:
            if callback:
                callback("[API] ❌ No video URL in draft", "err")
            return None
        
        # Step 4: Download
        if callback:
            callback("[3/4] Downloading video...", "info")
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"sora_api_{timestamp}.mp4"
        save_path = Path(save_dir) / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        success = client.download_video(video_url, str(save_path), callback)
        
        if not success:
            return None
        
        # Step 5: Delete draft
        if delete_after and draft_id:
            if callback:
                callback("[4/4] Cleaning up...", "info")
            client.delete_draft(draft_id, callback)
        
        return str(save_path)
    
    except Exception as e:
        logger.error(f"[API] Generate full error: {e}", exc_info=True)
        if callback:
            callback(f"[API] ❌ Error: {str(e)}", "err")
        return None


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    """Example usage"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Example token (replace with real token)
    bearer_token = "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE5MzQ0ZTY1..."
    
    print("\n" + "="*70)
    print("SORA API CLIENT - COMPLETE & FIXED")
    print("="*70)
    
    # Test 1: Text-to-video
    print("\n[TEST 1] Text-to-video")
    video_path = generate_video_full_api(
        bearer_token=bearer_token,
        prompt="A beautiful sunset over the ocean",
        aspect_ratio="16:9",
        duration=5,
        callback=lambda msg, level: print(f"[{level.upper()}] {msg}")
    )
    
    if video_path:
        print(f"\n✅ SUCCESS! Video: {video_path}")
    else:
        print(f"\n❌ FAILED")
    
    # Test 2: Image-to-video
    print("\n[TEST 2] Image-to-video")
    video_path = generate_video_full_api(
        bearer_token=bearer_token,
        prompt="Professional advertisement",
        aspect_ratio="9:16",
        duration=5,
        image_path="path/to/your/image.jpg",
        callback=lambda msg, level: print(f"[{level.upper()}] {msg}")
    )
    
    if video_path:
        print(f"\n✅ SUCCESS! Video: {video_path}")
    else:
        print(f"\n❌ FAILED")