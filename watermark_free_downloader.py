#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Watermark-Free Video Downloader - FIXED FOR NEW SECURITY
=================================================================
✅ Bypass SaveSora new security
✅ Real browser cookies
✅ Complete headers
"""

import os
import json
import time
import threading
import random
import urllib.parse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable
from queue import Queue, Empty
from dataclasses import dataclass, field

from curl_cffi import requests

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class DownloadTask:
    """Task download video không watermark"""
    post_url: str
    prompt: str
    mode: str  # "i2v" hoặc "t2v"
    stt: int
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y_%m_%d_%H_%M_%S"))
    status: str = "pending"
    error: Optional[str] = None
    output_path: Optional[str] = None
    progress: int = 0
    
    def get_filename(self) -> str:
        """Generate filename: i2v_001_2025_01_15_14_30_45.mp4"""
        return f"{self.mode}_{self.stt:03d}_{self.timestamp}.mp4"


# ============================================================================
# SAVESORA API CLIENT - FIXED FOR NEW SECURITY
# ============================================================================

class SaveSoraAPIClient:
    """
    SaveSora API Client - Bypass new security
    """
    
    BASE_URL = "https://savesora.com"
    API_DOWNLOAD_NEW = f"{BASE_URL}/api/download-video-new"
    API_PROXY_DOWNLOAD = f"{BASE_URL}/api/proxy-download"
    CHUNK_SIZE = 1048576  # 1MB
    IMPERSONATE = "chrome142"
    
    def __init__(self):
        """Initialize with curl_cffi session"""
        self.session = requests.Session(impersonate=self.IMPERSONATE)
        self._setup_session()
        logger.info("[SaveSora] ✅ Client initialized")
    
    def _setup_session(self):
        """Setup headers and cookies - FIXED"""
        current_time = int(time.time())
        client_id = random.randint(1000000000, 9999999999)
        
        # Real Google Analytics cookies
        self.session.cookies.set('_ga', f'GA1.1.{client_id}.{current_time}', domain='.savesora.com')
        self.session.cookies.set('_ga_B6E6ECFR8T', f'GS1.1.{client_id}.1.1.{current_time}.0.0.0', domain='.savesora.com')
        
        # Base headers - sẽ update theo từng request
        self.session.headers.update({
            'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
            'sec-ch-ua': '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
        })
    
    def submit_video(self, video_url: str, max_retries: int = 3) -> Dict:
        """Submit video URL để lấy encoded URL - FIXED"""
        payload = {"video_url": video_url, "format": "mp4"}
        
        # Headers for POST request
        headers = {
            'accept': '*/*',
            'authorization': 'Bearer null',
            'content-type': 'application/json',
            'origin': self.BASE_URL,
            'referer': f'{self.BASE_URL}/sora-watermark-remover',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"[SaveSora] 📤 Submitting (attempt {attempt}/{max_retries})...")
                
                response = self.session.post(
                    self.API_DOWNLOAD_NEW,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 403:
                    logger.warning("[SaveSora] ⚠️ Cloudflare challenge")
                    if attempt < max_retries:
                        wait = 2 ** attempt
                        logger.info(f"[SaveSora] ⏳ Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                    raise ConnectionError("Cloudflare blocked")
                
                response.raise_for_status()
                data = response.json()
                
                if data.get('code') != 200:
                    raise RuntimeError(f"API Error: {data.get('msg', 'Unknown')}")
                
                result = data.get('data', {})
                encoded_url = result.get('encoded_video_url01')
                
                if not encoded_url:
                    raise RuntimeError("No encoded URL")
                
                logger.info("[SaveSora] ✅ Submit successful")
                return result
            
            except requests.RequestException as e:
                logger.error(f"[SaveSora] Request error: {e}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                else:
                    raise ConnectionError(f"Failed after {max_retries} attempts") from e
    
    def download_video(self,
                      encoded_url: str,
                      output_path: str,
                      progress_callback: Optional[Callable[[int], None]] = None,
                      max_retries: int = 3) -> bool:
        """Download video từ encoded URL - FIXED"""
        url_param = urllib.parse.quote(encoded_url, safe='')
        download_url = f"{self.API_PROXY_DOWNLOAD}?url={url_param}"
        
        # Headers for download - giống curl command
        headers = {
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'referer': f'{self.BASE_URL}/',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'priority': 'u=0, i',
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"[SaveSora] ⬇️ Downloading (attempt {attempt}/{max_retries})...")
                
                response = self.session.get(
                    download_url, 
                    headers=headers,
                    stream=True, 
                    timeout=300
                )
                
                if response.status_code == 403:
                    logger.warning("[SaveSora] ⚠️ Cloudflare blocked")
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    raise ConnectionError("Download blocked")
                
                response.raise_for_status()
                
                # Stream download
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_progress = 0
                
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=self.CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size > 0:
                                progress = int((downloaded / total_size) * 100)
                                if progress != last_progress and progress_callback:
                                    progress_callback(progress)
                                    last_progress = progress
                
                # Verify
                file_size = Path(output_path).stat().st_size
                if file_size < 1024 * 20:
                    raise RuntimeError(f"File too small: {file_size} bytes")
                
                logger.info(f"[SaveSora] ✅ Downloaded: {file_size / 1024 / 1024:.2f}MB")
                return True
            
            except requests.RequestException as e:
                logger.error(f"[SaveSora] Download error: {e}")
                
                if Path(output_path).exists():
                    Path(output_path).unlink()
                
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                else:
                    raise ConnectionError(f"Download failed after {max_retries} attempts") from e


# ============================================================================
# MAIN DOWNLOADER CLASS
# ============================================================================

class WatermarkFreeDownloader:
    """Manager download video không watermark"""
    
    def __init__(self, app_instance, output_folder: str = "./downloads_no_watermark"):
        self.app = app_instance
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        self.download_queue = Queue()
        self.is_running = False
        self.worker_threads = []
        self.num_workers = 2
        
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'pending': 0
        }
        self.stats_lock = threading.Lock()
        
        logger.info("[WFD] Initialized")
    
    def start(self):
        """Start worker threads"""
        if self.is_running:
            return
        
        self.is_running = True
        
        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker, daemon=True, name=f"WFD-Worker-{i+1}")
            t.start()
            self.worker_threads.append(t)
        
        self.log(f"✅ Started with {self.num_workers} workers", "ok")
    
    def stop(self):
        """Stop worker threads"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        for _ in range(self.num_workers):
            self.download_queue.put(None)
        
        for t in self.worker_threads:
            t.join(timeout=5)
        
        self.worker_threads.clear()
        self.log("🛑 Stopped", "warn")
    
    def add_download_task(self, post_url: str, prompt: str, mode: str, stt: int):
        """Add download task"""
        task = DownloadTask(
            post_url=post_url,
            prompt=prompt,
            mode=mode,
            stt=stt
        )
        
        self.download_queue.put(task)
        
        with self.stats_lock:
            self.stats['total'] += 1
            self.stats['pending'] += 1
        
        self.log(f"📥 Queued: {task.get_filename()}", "info")
    
    def _worker(self):
        """Worker thread"""
        api_client = SaveSoraAPIClient()
        
        while self.is_running:
            try:
                task = self.download_queue.get(timeout=1)
                
                if task is None:
                    break
                
                self._process_task(task, api_client)
            
            except Empty:
                continue
            except Exception as e:
                logger.error(f"[WFD] Worker error: {e}", exc_info=True)
    
    def _process_task(self, task: DownloadTask, api_client: SaveSoraAPIClient):
        """Process download task"""
        try:
            with self.stats_lock:
                self.stats['pending'] -= 1
            
            task.status = "processing"
            self.log(f"⚙️ Processing: {task.get_filename()}", "info")
            
            # Submit
            result = api_client.submit_video(task.post_url)
            encoded_url = result.get('encoded_video_url01')
            
            if not encoded_url:
                raise RuntimeError("No encoded URL")
            
            # Download
            output_path = self.output_folder / task.get_filename()
            
            def progress_callback(progress: int):
                task.progress = progress
                if progress % 20 == 0:
                    self.log(f"⬇️ {task.get_filename()}: {progress}%", "info")
            
            api_client.download_video(encoded_url, str(output_path), progress_callback)
            
            task.status = "completed"
            task.output_path = str(output_path)
            task.progress = 100
            
            file_size = output_path.stat().st_size
            
            with self.stats_lock:
                self.stats['completed'] += 1
            
            self.log(f"✅ Downloaded: {task.get_filename()} ({file_size / 1024 / 1024:.1f}MB)", "ok")
            
            if hasattr(self.app, 'add_video_to_merger'):
                try:
                    self.app.add_video_to_merger(str(output_path))
                except Exception as e:
                    logger.error(f"[WFD] Merger error: {e}")
        
        except Exception as e:
            logger.error(f"[WFD] Task failed: {e}", exc_info=True)
            
            task.status = "failed"
            task.error = str(e)
            
            with self.stats_lock:
                self.stats['failed'] += 1
            
            self.log(f"❌ Failed: {task.get_filename()} - {str(e)[:100]}", "err")
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        with self.stats_lock:
            return self.stats.copy()
    
    def log(self, message: str, tag: str = None):
        """Thread-safe logging"""
        try:
            if hasattr(self.app, 'root') and hasattr(self.app, 'log'):
                self.app.root.after(0, lambda: self._safe_log(message, tag))
            elif hasattr(self.app, 'log'):
                self.app.log(f"[WFD] {message}", tag)
            else:
                logger.info(f"[WFD] {message}")
        except Exception as e:
            logger.warning(f"[WFD] Log failed: {e}")
    
    def _safe_log(self, message: str, tag: str = None):
        """Safe log helper"""
        try:
            self.app.log(f"[WFD] {message}", tag)
        except Exception as e:
            logger.warning(f"[WFD] Log error: {e}")


# ============================================================================
# POST URL EXTRACTOR
# ============================================================================

class PostURLExtractor:
    """Extract post URL from browser"""
    
    @staticmethod
    def inject_post_interceptor(driver):
        """Inject JavaScript interceptor"""
        script = """
        window.__SORA_POST_DATA__ = null;
        
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            return originalFetch.apply(this, args).then(response => {
                const clonedResponse = response.clone();
                
                clonedResponse.json().then(data => {
                    if (data && data.post && data.post.id) {
                        window.__SORA_POST_DATA__ = {
                            post_id: data.post.id,
                            post_url: 'https://sora.chatgpt.com/p/' + data.post.id
                        };
                        console.log('[SORA] ✅ Captured post:', data.post.id);
                    }
                }).catch(() => {});
                
                return response;
            });
        };
        
        console.log('[SORA] ✅ Interceptor ready');
        """
        
        try:
            driver.execute_script(script)
            logger.info("[Extractor] ✅ Interceptor injected")
            return True
        except Exception as e:
            logger.error(f"[Extractor] Inject error: {e}")
            return False
    
    @staticmethod
    def extract_post_url(driver, timeout: int = 15) -> Optional[str]:
        """Extract post URL from interceptor"""
        try:
            logger.info(f"[Extractor] 🔍 Extracting post URL (timeout: {timeout}s)...")
            
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                post_data = driver.execute_script("return window.__SORA_POST_DATA__;")
                
                if post_data and isinstance(post_data, dict):
                    post_url = post_data.get('post_url')
                    if post_url:
                        logger.info(f"[Extractor] ✅ Extracted: {post_url}")
                        return post_url
                
                time.sleep(0.5)
            
            logger.warning("[Extractor] ⚠️ Timeout")
            return None
        
        except Exception as e:
            logger.error(f"[Extractor] Error: {e}")
            return None


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

class WatermarkFreeIntegration:
    """Integration helper for main app"""
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.downloader: Optional[WatermarkFreeDownloader] = None
        self.is_enabled = False
    
    def enable(self, output_folder: str = "./downloads_no_watermark"):
        """Enable watermark-free download"""
        if self.is_enabled:
            return
        
        self.downloader = WatermarkFreeDownloader(self.app, output_folder)
        self.downloader.start()
        self.is_enabled = True
        
        logger.info("[WFI] Enabled")
    
    def disable(self):
        """Disable watermark-free download"""
        if not self.is_enabled:
            return
        
        if self.downloader:
            self.downloader.stop()
        
        self.is_enabled = False
        logger.info("[WFI] Disabled")
    
    def handle_post_success(self, browser, prompt: str, mode: str, stt: int):
        """Call after POST success"""
        if not self.is_enabled or not self.downloader:
            return
        
        try:
            post_url = PostURLExtractor.extract_post_url(browser.driver, timeout=10)
            
            if not post_url:
                logger.warning("[WFI] ⚠️ Cannot extract post URL")
                return
            
            logger.info(f"[WFI] ✅ Detected: {post_url}")
            
            self.downloader.add_download_task(
                post_url=post_url,
                prompt=prompt,
                mode=mode,
                stt=stt
            )
        
        except Exception as e:
            logger.error(f"[WFI] Handle post error: {e}")
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        if self.downloader:
            return self.downloader.get_stats()
        return {'total': 0, 'completed': 0, 'failed': 0, 'pending': 0}


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
    
    class MockApp:
        def log(self, msg, tag=None):
            print(f"[LOG] {msg}")
    
    app = MockApp()
    downloader = WatermarkFreeDownloader(app, "./test_downloads")
    downloader.start()
    
    # Test với post URL thực
    downloader.add_download_task(
        post_url="https://sora.chatgpt.com/p/s_test123",
        prompt="Test video",
        mode="i2v",
        stt=1
    )
    
    try:
        while True:
            stats = downloader.get_stats()
            print(f"\r[STATS] Total:{stats['total']} | Done:{stats['completed']} | "
                  f"Failed:{stats['failed']} | Pending:{stats['pending']}", end='')
            
            if stats['pending'] == 0 and stats['total'] > 0:
                break
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        pass
    
    finally:
        downloader.stop()