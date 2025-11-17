#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CONCURRENT VIDEO GENERATION - 2 WORKERS
========================================

Tối ưu: 2 videos song song thay vì tuần tự
Khi worker nào xong → Lấy video mới từ queue ngay
"""

import threading
import queue
import os
import time
import logging
from typing import Optional, Callable, List, Dict

logger = logging.getLogger(__name__)


class ConcurrentGenerationManager:
    """
    Quản lý 2 workers song song
    """
    
    def __init__(self, 
                 api_manager,
                 profile_manager,
                 max_workers: int = 2,
                 callback: Optional[Callable] = None,
                 ui_refresh_callback: Optional[Callable] = None):
        """
        Args:
            api_manager: APIGenerationManager
            profile_manager: ProfileManager
            max_workers: Số workers (1 hoặc 2)
            callback: Callback function (msg, level)
            ui_refresh_callback: UI refresh callback (prompt_data)
        """
        self.api_manager = api_manager
        self.profile_manager = profile_manager
        self.max_workers = max_workers
        self.callback = callback
        self.ui_refresh_callback = ui_refresh_callback
        
        # Queue
        self.prompt_queue = queue.Queue()
        
        # Workers
        self.workers = []
        self.is_running = False
        self.stop_requested = False
        
        # Stats
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'in_progress': 0
        }
        self.stats_lock = threading.Lock()
    
    def start(self, prompt_list: List[Dict]):
        """Bắt đầu generation"""
        if self.is_running:
            return False
        
        # Reset
        self.is_running = True
        self.stop_requested = False
        self.stats = {
            'total': len(prompt_list),
            'completed': 0,
            'failed': 0,
            'in_progress': 0
        }
        
        # Add to queue
        for prompt_data in prompt_list:
            self.prompt_queue.put(prompt_data)
        
        if self.callback:
            self.callback("="*70, "info")
            self.callback(f"🚀 {self.max_workers} WORKERS MODE", "ok")
            self.callback(f"   Queue: {len(prompt_list)} videos", "info")
            self.callback("="*70, "info")
        
        # Start workers
        for i in range(self.max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i+1,),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        return True
    
    def _worker_loop(self, worker_id: int):
        """Worker loop"""
        logger.info(f"[Worker-{worker_id}] Started")
        
        while not self.stop_requested:
            try:
                # Lấy prompt từ queue
                try:
                    prompt_data = self.prompt_queue.get(timeout=1)
                except queue.Empty:
                    if self.prompt_queue.empty():
                        break
                    continue
                
                # Update stats
                with self.stats_lock:
                    self.stats['in_progress'] += 1
                
                # Log
                if self.callback:
                    self.callback(
                        f"[Worker-{worker_id}] 🎬 {prompt_data['prompt'][:40]}...",
                        "info"
                    )
                
                # Update status to Processing
                prompt_data['status'] = 'Processing'
                
                # Trigger UI refresh for Processing status
                if hasattr(self, 'ui_refresh_callback') and self.ui_refresh_callback:
                    try:
                        self.ui_refresh_callback(prompt_data)
                    except Exception as e:
                        logger.debug(f"UI refresh error (Processing): {e}")
                
                # GENERATE
                success = self._generate_video(worker_id, prompt_data)
                
                # Update stats
                with self.stats_lock:
                    self.stats['in_progress'] -= 1
                    if success:
                        self.stats['completed'] += 1
                    else:
                        self.stats['failed'] += 1
                
                # Done
                self.prompt_queue.task_done()
                
                # Log progress
                if self.callback:
                    ok = self.stats['completed']
                    fail = self.stats['failed']
                    total = self.stats['total']
                    self.callback(
                        f"[PROGRESS] ✅ {ok} | ❌ {fail} | 📊 {ok+fail}/{total}",
                        "ok"
                    )
            
            except Exception as e:
                logger.error(f"[Worker-{worker_id}] Error: {e}")
                with self.stats_lock:
                    self.stats['in_progress'] -= 1
                    self.stats['failed'] += 1
                try:
                    self.prompt_queue.task_done()
                except:
                    pass
        
        logger.info(f"[Worker-{worker_id}] Stopped")
    
    def _generate_video(self, worker_id: int, prompt_data: Dict) -> bool:
        """Generate 1 video"""
        try:
            # Extract params
            prompt = prompt_data['prompt']
            orientation = prompt_data.get('orientation', 'landscape')
            duration_str = prompt_data.get('duration', '10s')
            duration = int(duration_str.replace('s', ''))  # Parse "10s" → 10, "15s" → 15
            image_path = prompt_data.get('image_path')
            download_dir = prompt_data.get('download_dir', './downloads')
            draft_action = prompt_data.get('draft_action', 'delete')
            
            # Map orientation: landscape → 16:9, portrait → 9:16
            if orientation.lower() in ['portrait', '9:16']:
                aspect_ratio = "9:16"
            else:
                aspect_ratio = "16:9"  # Default landscape
            
            # GET PROFILE
            from profile_manager import calculate_credits
            credits = calculate_credits(duration)
            
            # ✅ FIX: Lấy profile từ API Manager's current account
            profile = None
            
            if self.api_manager and self.api_manager.current_account:
                profile = self.profile_manager.get_profile_by_name(
                    self.api_manager.current_account
                )
                
                if profile:
                    # Kiểm tra đủ credits không
                    if not profile.can_generate(credits):
                        if self.callback:
                            self.callback(
                                f"[Worker-{worker_id}] ⚠️ {profile.profile_name} hết credits",
                                "warn"
                            )
                        profile = None
            
            # Không có profile hoặc profile hết credits → Tìm profile mới
            if not profile:
                profile = self.profile_manager.get_next_available_profile(credits)
                
                if profile:
                    # ✅ CRITICAL: PHẢI reload token cho profile mới
                    if self.api_manager:
                        old_account = self.api_manager.current_account
                        
                        # GỌI set_account() để RELOAD TOKEN MỚI
                        success = self.api_manager.set_account(profile.profile_name)
                        
                        if success:
                            if self.callback:
                                self.callback(
                                    f"[Worker-{worker_id}] 🔄 Switched: {old_account} → {profile.profile_name} (Token reloaded)",
                                    "ok"
                                )
                        else:
                            if self.callback:
                                self.callback(
                                    f"[Worker-{worker_id}] ⚠️ Failed to reload token for {profile.profile_name}",
                                    "warn"
                                )
                            # Fallback về profile cũ
                            return False
            
            if not profile:
                if self.callback:
                    self.callback(f"[Worker-{worker_id}] ❌ Tất cả profiles đã hết credits!", "err")
                return False
            
            # RESERVE CREDIT
            self.profile_manager.increment_usage(profile, duration)
            
            if self.callback:
                self.callback(
                    f"[Worker-{worker_id}] 👤 {profile.profile_name} "
                    f"({profile.remaining_credits()} left)",
                    "info"
                )
            
            # GENERATE
            def worker_cb(msg, level):
                if self.callback:
                    self.callback(f"[W{worker_id}] {msg}", level)
            
            result = self.api_manager.generate_video(
                prompt=prompt,
                orientation=aspect_ratio,
                duration=duration,
                image_path=image_path,
                download_dir=download_dir,
                draft_action=draft_action,
                callback=worker_cb
            )
            
            # CHECK RESULT
            if result and isinstance(result, dict) and result.get('success'):
                if self.callback:
                    self.callback(f"[Worker-{worker_id}] ✅ Done!", "ok")
                
                # Download thumbnail
                thumbnail_path = None
                thumbnail_url = result.get('thumbnail_url')
                if thumbnail_url:
                    try:
                        import requests
                        thumbnail_filename = f"thumb_{int(time.time())}_{worker_id}.jpg"
                        thumbnail_path = os.path.join(download_dir, thumbnail_filename)
                        resp = requests.get(thumbnail_url, timeout=10)
                        if resp.status_code == 200:
                            with open(thumbnail_path, 'wb') as f:
                                f.write(resp.content)
                            if self.callback:
                                self.callback(f"[Worker-{worker_id}] 🖼️ Thumbnail saved", "ok")
                    except Exception as e:
                        logger.error(f"Thumbnail download error: {e}")
                
                # Update UI data
                prompt_data['status'] = 'Success'
                prompt_data['video_data'] = {
                    'status': 'Success',
                    'path': result.get('filepath'),
                    'thumbnail_path': thumbnail_path,
                    'draft_id': result.get('draft_id'),
                    'orientation': orientation  # ✅ THÊM ORIENTATION
                }
                
                # Trigger UI refresh
                if hasattr(self, 'ui_refresh_callback') and self.ui_refresh_callback:
                    try:
                        self.ui_refresh_callback(prompt_data)
                    except Exception as e:
                        logger.debug(f"UI refresh error: {e}")
                
                return True
            else:
                if self.callback:
                    self.callback(f"[Worker-{worker_id}] ❌ Failed!", "err")
                prompt_data['status'] = 'Failed'
                return False
        
        except Exception as e:
            logger.error(f"[Worker-{worker_id}] Error: {e}")
            if self.callback:
                self.callback(f"[Worker-{worker_id}] ❌ {str(e)[:50]}", "err")
            return False
    
    def wait_completion(self):
        """Đợi tất cả workers xong"""
        self.prompt_queue.join()
        for worker in self.workers:
            worker.join()
        self.is_running = False
    
    def stop(self):
        """Stop workers"""
        self.stop_requested = True
        for worker in self.workers:
            worker.join(timeout=5)
        self.is_running = False
    
    def get_stats(self) -> Dict:
        """Lấy stats"""
        with self.stats_lock:
            return self.stats.copy()