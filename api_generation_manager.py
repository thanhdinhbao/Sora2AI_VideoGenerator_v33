#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API GENERATION MANAGER - Thay thế BrowserManager
=================================================
✅ 100% API - NO BROWSER NEEDED
✅ Compatible with SoraAPIClientFull (curl_cffi bypass Cloudflare)
✅ Auto-upload images via API
"""

import os
import time
import logging
from typing import Optional, Dict, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


class APIGenerationManager:
    """
    API Generation Manager - Thay thế BrowserManager hoàn toàn
    
    Chức năng:
    - Generate video qua API (text-to-video & image-to-video)
    - Auto-upload images with curl_cffi bypass
    - Poll status
    - Download video  
    - Delete draft
    
    NO BROWSER NEEDED!
    """
    
    def __init__(self, credential_manager):
        """
        Initialize API Generation Manager
        
        Args:
            credential_manager: CredentialManager instance
        """
        self.credential_manager = credential_manager
        self.api_client_full = None  # ✅ Renamed from api_client
        self.current_account = None
        
        logger.info("[API_MGR] ✅ Initialized")
    
    def set_account(self, account_name: str) -> bool:
        """
        Set active account and load credentials
        
        Args:
            account_name: Account name
            
        Returns:
            True if success
        """
        try:
            logger.info(f"[API_MGR] 📂 Setting account: {account_name}")
            
            # Get credentials
            credentials = self.credential_manager.get_credentials(account_name)
            
            if not credentials:
                logger.error(f"[API_MGR] ❌ No credentials for: {account_name}")
                return False
            
            bearer_token = credentials.get('bearer_token')
            
            if not bearer_token:
                logger.error(f"[API_MGR] ❌ No token for: {account_name}")
                return False
            
            # ✅ Initialize SoraAPIClient (FULL version with curl_cffi)
            from sora_api_client_full import SoraAPIClient
            self.api_client_full = SoraAPIClient(bearer_token)
            self.current_account = account_name
            
            logger.info(f"[API_MGR] ✅ Account set: {account_name}")
            logger.info(f"[API_MGR] ✅ Client ready with curl_cffi bypass")
            return True
        
        except Exception as e:
            logger.error(f"[API_MGR] ❌ Set account error: {e}", exc_info=True)
            return False
    
    def is_ready(self) -> bool:
        """Check if API client is ready"""
        return self.api_client_full is not None
    
    def generate_video(self, 
                      prompt: str,
                      orientation: str = "16:9",
                      duration: int = 5,
                      image_path: str = None,  # ✅ FIXED: Renamed from image_url to image_path
                      download_dir: str = "./downloads",
                      draft_action: str = "delete",
                      post_text: str = "",  # ✅ NEW: Caption for post
                      callback: Optional[Callable] = None) -> Optional[str]:
        """
        Generate video - 100% API with image upload support + AUTO POST
        
        Full workflow: Create → Wait → Download → POST → Delete if post fails
        
        Args:
            prompt: Text prompt
            orientation: "16:9", "9:16", "1:1"
            duration: 5 or 10 seconds
            image_path: Optional LOCAL image file path (will auto-upload via curl_cffi)
            download_dir: Download directory
            draft_action: "delete" or "keep"
            post_text: Caption for post (optional)
            callback: Callback function(message, level)
            
        Returns:
            Video file path or None
        """
        try:
            if not self.is_ready():
                if callback:
                    callback("[API] ❌ No account selected", "err")
                logger.error("[API_MGR] API client not ready")
                return None
            
            if callback:
                callback("="*70, "info")
                callback(f"🚀 API MODE - Account: {self.current_account}", "ok")
                callback("="*70, "info")
            
            # ✅ Map orientation to aspect_ratio
            aspect_ratio_map = {
                "LANDSCAPE": "16:9",
                "PORTRAIT": "9:16", 
                "SQUARE": "1:1",
                "16:9": "16:9",
                "9:16": "9:16",
                "1:1": "1:1",
                "landscape": "16:9",
                "portrait": "9:16"
            }
            aspect_ratio = aspect_ratio_map.get(orientation, "16:9")
            
            # ============================================================
            # STEP 1: CREATE TASK (auto-upload image if provided)
            # ============================================================
            if callback:
                callback("[API] [1/6] 🚀 Creating generation task...", "info")
                callback(f"[API] Prompt: {prompt[:50]}...", "info")
                callback(f"[API] Settings: {aspect_ratio}, {duration}s", "info")
                
                if image_path:
                    callback(f"[API] 🖼️ Image: {os.path.basename(image_path)}", "info")
            
            # ✅ CRITICAL: Use create_task() which handles image upload internally
            task = self.api_client_full.create_task(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration=duration,
                image_url=image_path,  # ✅ Pass as image_url (method will upload if local file)
                callback=callback
            )
            
            if not task:
                if callback:
                    callback("[API] ❌ Failed to create task", "err")
                return None
            
            task_id = task.get('id') or task.get('task_id')
            
            if callback:
                callback(f"[API] ✅ Task ID: {task_id}", "ok")
            
            # ============================================================
            # STEP 2: WAIT FOR COMPLETION
            # ============================================================
            if callback:
                callback("[API] [2/6] ⏳ Waiting for completion...", "info")
                callback("[API]      Estimated: 2-3 minutes", "info")
            
            draft = self.api_client_full.wait_for_completion(
                task_id,
                timeout=600,
                poll_interval=5,
                callback=callback
            )
            
            if not draft:
                if callback:
                    callback("[API] ❌ Generation failed or timeout", "err")
                return None
            
            if callback:
                callback("[API] ✅ Video ready!", "ok")
            
            # ============================================================
            # STEP 3: GET VIDEO URL & GENERATION ID
            # ============================================================
            if callback:
                callback("[API] [3/6] 📦 Getting video info...", "info")
            
            video_url = draft.get('url') or draft.get('video_url')
            generation_id = draft.get('generation_id') or draft.get('id')
            
            # THÊM:
            thumbnail_url = None
            encodings = draft.get('encodings', {})
            if encodings:
                thumbnail_url = encodings.get('thumbnail', {}).get('path')

            # THÊM VÀO LOG:
            if thumbnail_url:
                callback(f"[API] ✅ Thumbnail: {thumbnail_url[:50]}...", "ok")
            
            if not video_url:
                if callback:
                    callback("[API] ❌ No video URL in response", "err")
                return None
            
            if not generation_id:
                if callback:
                    callback("[API] ⚠️ No generation_id found", "warn")
            
            if callback:
                callback(f"[API] ✅ URL: {video_url[:50]}...", "ok")
                callback(f"[API] ✅ Generation ID: {generation_id}", "ok")
            
            # ============================================================
            # STEP 4: DOWNLOAD VIDEO
            # ============================================================
            if callback:
                callback("[API] [4/6] 📥 Downloading video...", "info")
            
            # Ensure download dir exists
            os.makedirs(download_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"sora_api_{timestamp}.mp4"
            filepath = os.path.join(download_dir, filename)
            
            success = self.api_client_full.download_video(
                video_url,
                filepath,
                callback=callback
            )
            
            if not success:
                if callback:
                    callback("[API] ❌ Download failed", "err")
                return None
            
            if callback:
                callback(f"[API] ✅ Saved: {filename}", "ok")
            
            # ============================================================
            # STEP 5: HANDLE DRAFT ACTION
            # ============================================================
            if callback:
                callback("[API] [5/6] 📋 Handling draft action...", "info")
            
            action_success = False
            action_result = None
            
            if draft_action == "post":
                # ========================================================
                # ACTION: POST VIDEO TO PUBLIC
                # ========================================================
                if callback:
                    callback("[API] 📤 Posting video to feed...", "info")
                
                post_result = self.api_client_full.post_video(
                    generation_id=generation_id,
                    post_text=post_text,
                    callback=callback
                )
                
                if post_result:
                    action_success = True
                    action_result = post_result
                    
                    post_info = post_result.get('post', {})
                    post_id = post_info.get('id')
                    permalink = post_info.get('permalink')
                    
                    if callback:
                        callback(f"[API] ✅ Posted! ID: {post_id}", "ok")
                        if permalink:
                            callback(f"[API] 🔗 {permalink}", "info")
                else:
                    if callback:
                        callback("[API] ❌ Post failed", "err")
            
            elif draft_action == "delete":
                # ========================================================
                # ACTION: DELETE DRAFT
                # ========================================================
                if callback:
                    callback("[API] 🗑️ Deleting draft...", "info")
                
                if generation_id:
                    deleted = self.api_client_full.delete_draft(
                        generation_id, 
                        callback=callback
                    )
                    
                    if deleted:
                        action_success = True
                        if callback:
                            callback("[API] ✅ Draft deleted", "ok")
                    else:
                        if callback:
                            callback("[API] ⚠️ Delete failed (video still saved)", "warn")
                else:
                    if callback:
                        callback("[API] ⚠️ No generation_id to delete", "warn")
            
            else:
                # ========================================================
                # ACTION: KEEP DRAFT (DO NOTHING)
                # ========================================================
                if callback:
                    callback("[API] 📌 Keeping draft (no action)", "info")
                action_success = True
            
            # ============================================================
            # FINAL RESULT
            # ============================================================
            if callback:
                callback("="*70, "ok")
                callback("✅ GENERATION COMPLETE!", "ok")
                callback(f"   Action: {draft_action.upper()}", "info")
                callback(f"   Status: {'✅ Success' if action_success else '⚠️ Failed'}", "ok" if action_success else "warn")
                callback("="*70, "ok")
            
            return {
                'success': True,
                'filepath': filepath,
                'thumbnail_url': thumbnail_url,
                'draft_id': generation_id,
                'video_url': video_url,
                'action': draft_action,
                'action_success': action_success,
                'action_result': action_result
            }
            

        except Exception as e:
            logger.error(f"[API_MGR] ❌ Generate error: {e}", exc_info=True)
            if callback:
                callback(f"[API] ❌ Error: {str(e)[:100]}", "err")
            return None
    
    def wait_for_completion(self, 
                          task_id: str, 
                          timeout: int = 600,
                          callback: Optional[Callable] = None) -> Optional[Dict]:
        """
        Wait for task completion - WRAPPER method for compatibility
        
        Args:
            task_id: Task ID
            timeout: Max wait time
            callback: Callback function
            
        Returns:
            Draft dict or None
        """
        try:
            if not self.is_ready():
                if callback:
                    callback("[API] ❌ Not ready", "err")
                return None
            
            return self.api_client_full.wait_for_completion(
                task_id,
                timeout=timeout,
                poll_interval=5,
                callback=callback
            )
        
        except Exception as e:
            logger.error(f"[API_MGR] Wait error: {e}")
            return None
    
    def download_video(self, 
                     video_url: str, 
                     save_path: str,
                     callback: Optional[Callable] = None) -> bool:
        """
        Download video - WRAPPER method for compatibility
        
        Args:
            video_url: Video URL
            save_path: Save path
            callback: Callback function
            
        Returns:
            True if success
        """
        try:
            if not self.is_ready():
                if callback:
                    callback("[API] ❌ Not ready", "err")
                return False
            
            return self.api_client_full.download_video(
                video_url,
                save_path,
                callback=callback
            )
        
        except Exception as e:
            logger.error(f"[API_MGR] Download error: {e}")
            return False
    
    def delete_post(self, 
                   slug: str,
                   callback: Optional[Callable] = None) -> bool:
        """
        Delete post - For published posts
        
        Args:
            slug: Post slug/ID
            callback: Callback function
            
        Returns:
            True if deleted
        """
        try:
            if not self.is_ready():
                if callback:
                    callback("[API] ❌ Not ready", "err")
                return False
            
            return self.api_client_full.delete_post(slug, callback=callback)
        
        except Exception as e:
            logger.error(f"[API_MGR] Delete post error: {e}")
            return False
    
    def delete_draft(self, 
                    draft_id: str,
                    callback: Optional[Callable] = None) -> bool:
        """
        Delete draft - For unpublished drafts
        
        Args:
            draft_id: Draft ID (gen_...)
            callback: Callback function
            
        Returns:
            True if deleted
        """
        try:
            if not self.is_ready():
                if callback:
                    callback("[API] ❌ Not ready", "err")
                return False
            
            return self.api_client_full.delete_draft(draft_id, callback=callback)
        
        except Exception as e:
            logger.error(f"[API_MGR] Delete draft error: {e}")
            return False
    
    def check_account_status(self, callback: Optional[Callable] = None) -> bool:
        """
        Check if current account is valid
        
        Args:
            callback: Callback function
            
        Returns:
            True if valid
        """
        try:
            if not self.is_ready():
                if callback:
                    callback("[API] ❌ No account selected", "err")
                return False
            
            if callback:
                callback("[API] 🔍 Checking account status...", "info")
            
            # ✅ Simple check: Try to get pending tasks
            try:
                tasks = self.api_client_full.get_pending_tasks(callback=callback)
                
                if tasks is not None:
                    if callback:
                        callback(f"[API] ✅ Account '{self.current_account}' is valid", "ok")
                        callback(f"[API] ℹ️ Pending tasks: {len(tasks)}", "info")
                    return True
                else:
                    if callback:
                        callback(f"[API] ❌ Account check failed", "err")
                    return False
            
            except Exception as e:
                logger.error(f"[API_MGR] Check failed: {e}")
                if callback:
                    callback(f"[API] ❌ Check failed: {str(e)[:100]}", "err")
                return False
        
        except Exception as e:
            logger.error(f"[API_MGR] Check status error: {e}")
            return False
    
    def get_account_info(self) -> Dict:
        """
        Get current account info
        
        Returns:
            Dict with account info
        """
        return {
            'account': self.current_account,
            'is_ready': self.is_ready()
        }


# ============================================================================
# COMPATIBILITY WRAPPER - For code that expects BrowserManager interface
# ============================================================================

class BrowserManagerAPIAdapter:
    """
    Adapter để code cũ (dùng BrowserManager) có thể dùng APIGenerationManager
    
    Giúp migrate dần mà không phải sửa hết code ngay
    """
    
    def __init__(self, api_manager: APIGenerationManager):
        """
        Initialize adapter
        
        Args:
            api_manager: APIGenerationManager instance
        """
        self.api_manager = api_manager
        self.driver = None  # Fake driver for compatibility
        
        logger.info("[ADAPTER] BrowserManager compatibility adapter initialized")
    
    def is_logged_in(self) -> bool:
        """Check if ready (compatibility)"""
        return self.api_manager.is_ready()
    
    def enter_prompt(self, prompt: str) -> bool:
        """Compatibility - store prompt"""
        self._pending_prompt = prompt
        return True
    
    def click_generate(self) -> bool:
        """Compatibility - mark as generating"""
        self._is_generating = True
        return True
    
    def wait_for_video(self, timeout: int = 600) -> bool:
        """Compatibility - always return True (API handles waiting)"""
        return True
    
    def download_video(self, save_path: str) -> bool:
        """Compatibility - API handles download"""
        return True


if __name__ == "__main__":
    """Test API Generation Manager"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "="*70)
    print("API GENERATION MANAGER - Test")
    print("="*70)
    
    # Example usage
    from credential_manager import CredentialManager
    
    cred_mgr = CredentialManager()
    api_mgr = APIGenerationManager(cred_mgr)
    
    # Set account
    # api_mgr.set_account("Profile_1")
    
    # Generate video with image
    # video_path = api_mgr.generate_video(
    #     prompt="professional advertisement",
    #     orientation="9:16",
    #     duration=5,
    #     image_path="C:/path/to/image.jpg",  # ✅ Local file - will auto-upload
    #     callback=lambda msg, level: print(f"[{level}] {msg}")
    # )
    
    print("\n✅ API Generation Manager ready!")