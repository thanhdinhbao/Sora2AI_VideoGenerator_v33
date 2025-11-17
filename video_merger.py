#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video Merger Module - FFmpeg-based Video Concatenation
Tự động nối video khi đủ batch size, bỏ qua video lỗi
Threading-based, không block generation/download processes
Auto-download FFmpeg nếu chưa có
"""

import os
import json
import time
import threading
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Callable
from queue import Queue, Empty
from dataclasses import dataclass, field

# ✅ NEW: Import FFmpeg Manager
from ffmpeg_installer import FFmpegManager

logger = logging.getLogger(__name__)

# ✅ NEW: Initialize FFmpeg Manager (singleton)
FFMPEG_MANAGER = FFmpegManager.get_instance()


@dataclass
class MergeTask:
    """Đại diện cho một task merge video"""
    video_paths: List[str]  # Danh sách đường dẫn video cần merge
    batch_id: int  # ID của batch
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    status: str = "pending"  # pending, validating, merging, completed, failed
    valid_videos: List[str] = field(default_factory=list)  # Các video hợp lệ sau validate
    output_path: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0  # 0-100%

    def get_filename(self) -> str:
        """Generate filename: merged_batch001_20250131_120000.mp4"""
        return f"merged_batch{self.batch_id:03d}_{self.timestamp}.mp4"


class FFmpegValidator:
    """Validator để kiểm tra video có hợp lệ không"""
    @staticmethod
    def validate_video(video_path: str, timeout: int = 10) -> bool:
        """
        Kiểm tra video có hợp lệ không bằng ffprobe
        Returns: True nếu video hợp lệ, False nếu lỗi
        """
        if not os.path.exists(video_path):
            logger.warning(f"VM: Video không tồn tại: {video_path}")
            return False
        try:
            cmd = [
                FFMPEG_MANAGER.get_ffprobe_command(),
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_name,width,height,duration',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                encoding='utf-8'
            )
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                streams = data.get('streams', [])
                if streams:
                    stream = streams[0]
                    # Check width, height, codec, duration khác None và duration > 0
                    if all([
                        stream.get("width"),
                        stream.get("height"),
                        stream.get("codec_name"),
                        stream.get("duration"),
                        float(stream.get("duration")) > 0
                    ]):
                        logger.info(f"VM: ✓ Video hợp lệ: {Path(video_path).name} "
                                    f"({stream.get('width')}x{stream.get('height')}, "
                                    f"{stream.get('codec_name')}, duration={stream.get('duration')})")
                        return True
                logger.warning(f"VM: ✗ Video không hợp lệ: {Path(video_path).name}")
                return False
            else:
                logger.warning(f"VM: ffprobe error: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            logger.error(f"VM: Timeout khi validate: {video_path}")
            return False
        except Exception as e:
            logger.error(f"VM: Lỗi validate {video_path}: {e}")
            return False



class FFmpegMerger:
    """Merger thực hiện việc nối video bằng ffmpeg"""
    
    @staticmethod
    def merge_videos(
        video_paths: List[str],
        output_path: str,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> bool:
        """
        Nối danh sách video thành 1 video
        
        Args:
            video_paths: Danh sách đường dẫn video (đã validate)
            output_path: Đường dẫn output
            progress_callback: Callback nhận progress (0-100)
            
        Returns:
            True nếu thành công, False nếu thất bại
        """
        if not video_paths:
            logger.error("VM: Không có video để merge")
            return False
        
        if len(video_paths) == 1:
            logger.info(f"VM: Chỉ có 1 video, copy thay vì merge")
            try:
                import shutil
                shutil.copy2(video_paths[0], output_path)
                return True
            except Exception as e:
                logger.error(f"VM: Lỗi copy file: {e}")
                return False
        
        # Tạo file concat list
        concat_file = Path(output_path).parent / f"concat_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        try:
            # Ghi danh sách video
            with open(concat_file, 'w', encoding='utf-8') as f:
                for video in video_paths:
                    # Sử dụng absolute path và escape cho Windows
                    abs_path = os.path.abspath(video).replace('\\', '/')
                    f.write(f"file '{abs_path}'\n")
            
            logger.info(f"VM: Bắt đầu merge {len(video_paths)} video...")
            
            # Command ffmpeg
            cmd = [
                FFMPEG_MANAGER.get_ffmpeg_command(),  # ✅ Dùng portable ffmpeg
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c', 'copy',  # Copy codec, không re-encode (nhanh nhất)
                '-y',  # Overwrite
                str(output_path)
            ]
            
            # Chạy ffmpeg
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8'
            )
            
            # Đọc stderr để track progress (ffmpeg ghi log vào stderr)
            stderr_lines = []
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                stderr_lines.append(line)
                
                # Parse progress từ ffmpeg output (optional)
                if progress_callback and "time=" in line:
                    # Simple progress tracking (có thể cải thiện)
                    progress_callback(50)  # Placeholder
            
            # Đợi hoàn thành
            process.wait()
            
            if process.returncode == 0 and os.path.exists(output_path):
                filesize = os.path.getsize(output_path) / (1024 * 1024)
                logger.info(f"VM: ✓ Merge thành công: {Path(output_path).name} ({filesize:.2f}MB)")
                
                # Xóa concat file
                if concat_file.exists():
                    concat_file.unlink()
                
                if progress_callback:
                    progress_callback(100)
                
                return True
            else:
                error_msg = '\n'.join(stderr_lines[-10:]) # Last 10 lines
                logger.error(f"VM: ✗ Merge thất bại:\n{error_msg}")
                # Cleanup output nếu lỗi
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except Exception as e:
                        logger.warning(f"VM: Cleanup merged file failed: {e}")
                return False

                
        except Exception as e:
            logger.error(f"VM: Exception khi merge: {e}", exc_info=True)
            return False
        finally:
            # Cleanup concat file
            if concat_file.exists():
                try:
                    concat_file.unlink()
                except Exception as e:
                    logger.warning(f"VM: Cleanup concat file failed: {e}")



class VideoMerger:
    """
    Manager chính xử lý merge video
    
    WORKFLOW:
    1. Nhận video paths từ watermark-free downloader
    2. Buffer đến khi đủ batch_size
    3. Tạo MergeTask và đưa vào queue
    4. Worker thread validate và merge
    5. Callback kết quả về UI
    """
    
    def __init__(
        self,
        app_instance,
        output_folder: str = "./downloads_merged",
        batch_size: int = 3
    ):
        """
        Args:
            app_instance: Reference đến main App
            output_folder: Thư mục lưu video đã merge
            batch_size: Số video merge trong 1 batch (default: 3)
        """
        self.app = app_instance
        
        # ✅ NEW: Ensure FFmpeg is ready (auto-download nếu chưa có)
        logger.info("VM: Checking FFmpeg installation...")
        self.log("Checking FFmpeg...", "info")
        
        try:
            if not FFMPEG_MANAGER.ensure_ffmpeg(progress_callback=self._ffmpeg_download_progress):
                error_msg = "❌ FFmpeg installation failed! Video merger cannot work."
                logger.error(error_msg)
                self.log(error_msg, "err")
                raise RuntimeError(error_msg)
            
            self.log("✓ FFmpeg ready", "ok")
        except Exception as e:
            error_msg = f"❌ FFmpeg setup error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.log(error_msg, "err")
            raise
        
        # Continue with normal init
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        
        # Queue và buffer
        self.merge_queue: Queue = Queue()
        self.video_buffer: List[str] = []  # Buffer chứa video paths chờ đủ batch
        
        # Tasks tracking
        self.tasks: Dict[int, MergeTask] = {}  # batch_id -> MergeTask
        self.batch_counter: int = 0
        
        # Worker thread
        self.is_running: bool = False
        self.worker_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'pending': 0,
            'videos_merged': 0
        }
        
        # Validator và Merger
        self.validator = FFmpegValidator()
        self.merger = FFmpegMerger()
        
        logger.info(f"VM: VideoMerger initialized (batch_size={batch_size})")
        logger.info(f"VM: Output folder: {self.output_folder}")
    
    def _ffmpeg_download_progress(self, downloaded_mb, total_mb, percent):
        """Callback cho FFmpeg download progress"""
        if int(percent) % 10 == 0:  # Log mỗi 10%
            self.log(f"📥 Downloading FFmpeg: {percent:.0f}% ({downloaded_mb:.1f}MB/{total_mb:.1f}MB)", "info")
    
    def start(self):
        """Start worker thread"""
        if self.is_running:
            logger.warning("VM: Already running")
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("VM: Worker thread started")
        self.log("🎬 Video Merger started", "ok")
        return True
    def stop(self):
        """Stop worker thread"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        logger.info("VM: Worker thread stopped")
        self.log("⏹️ Video Merger stopped", "info")
    
    def set_batch_size(self, size: int):
        """Thiết lập batch size (số video merge 1 lần)"""
        self.batch_size = size
        logger.info(f"VM: Batch size set to {size}")
        self.log(f"🔧 Batch size: {size} videos", "info")
    
    def add_video(self, video_path: str):
        """
        Thêm video vào buffer
        Tự động tạo merge task khi đủ batch_size
        
        Args:
            video_path: Đường dẫn video đã download (no watermark)
        """
        if not os.path.exists(video_path):
            logger.warning(f"VM: Video không tồn tại: {video_path}")
            return
        
        self.video_buffer.append(video_path)
        logger.info(f"VM: Added video to buffer: {Path(video_path).name} "
                   f"({len(self.video_buffer)}/{self.batch_size})")
        
        # Auto-start worker nếu chưa chạy
        if not self.is_running:
            self.start()
        
        # Khi đủ batch_size, tạo task
        if len(self.video_buffer) >= self.batch_size:
            self._create_merge_task()
    
    def _create_merge_task(self):
        """Tạo MergeTask từ buffer và đưa vào queue"""
        if len(self.video_buffer) < self.batch_size:
            return
        
        # Lấy batch videos
        batch = self.video_buffer[:self.batch_size]
        self.video_buffer = self.video_buffer[self.batch_size:]
        
        # Tạo task
        self.batch_counter += 1
        task = MergeTask(
            video_paths=batch,
            batch_id=self.batch_counter
        )
        
        self.tasks[task.batch_id] = task
        self.merge_queue.put(task)
        self.stats['total'] += 1
        self.stats['pending'] += 1
        
        logger.info(f"VM: Created merge task batch#{task.batch_id} with {len(batch)} videos")
        self.log(f"📦 Merge task created: batch#{task.batch_id}", "info")
    
    def flush_buffer(self):
        """
        Force merge các video còn lại trong buffer
        Dùng khi muốn merge ngay cả khi chưa đủ batch_size
        """
        lock = threading.Lock()
        with lock:
            if not self.video_buffer:
                logger.info("VM: Buffer empty, nothing to flush")
                self.log("ℹ️ Buffer empty", "info")
                return
            logger.info(f"VM: Flushing buffer with {len(self.video_buffer)} videos")
            # Tạo task với số video hiện có
            self.batch_counter += 1
            task = MergeTask(
                video_paths=self.video_buffer.copy(),
                batch_id=self.batch_counter
            )
            self.tasks[task.batch_id] = task
            self.merge_queue.put(task)
            self.stats['total'] += 1
            self.stats['pending'] += 1
            self.video_buffer.clear()
            self.log(f"🔄 Flushed buffer: batch#{task.batch_id}", "info")

    
    def _worker_loop(self):
        lock = threading.Lock()
        """Worker thread chính - xử lý merge queue"""
        logger.info("VM: Worker loop started")
        
        while self.is_running:
            try:
                # Get task from queue (timeout 1s)
                try:
                    task = self.merge_queue.get(timeout=1)
                except Empty:
                    continue
                
                # Process task
                self._process_task(task)
                self.merge_queue.task_done()
                
            except Exception as e:
                logger.error(f"VM: Worker loop error: {e}", exc_info=True)
                time.sleep(1)
        
        logger.info("VM: Worker loop ended")
    
    def _process_task(self, task: MergeTask):
        """Xử lý một merge task"""
        try:
            logger.info(f"VM: Processing task batch#{task.batch_id}")
            
            # STEP 1: Validate videos
            task.status = "validating"
            self.log(f"🔍 Validating batch#{task.batch_id}...", "info")
            
            valid_videos = []
            invalid_count = 0
            for video_path in task.video_paths:
                if self.validator.validate_video(video_path):
                    valid_videos.append(video_path)
                else:
                    logger.warning(f"VM: Bỏ qua video lỗi: {Path(video_path).name}")
                    invalid_count += 1

            task.valid_videos = valid_videos

            # ✅ CHỈ MERGE KHI TẤT CẢ VIDEO TRONG BATCH ĐỀU HỢP LỆ
            if invalid_count > 0:
                raise RuntimeError(f"Batch có {invalid_count} video lỗi - bỏ qua merge để tránh nhảy cóc. "
                                  f"Valid: {len(valid_videos)}/{len(task.video_paths)}")

            if not valid_videos:
                raise RuntimeError("Không có video hợp lệ nào để merge")
            
            # STEP 2: Merge videos
            task.status = "merging"
            self.log(f"🎬 Merging {len(valid_videos)} videos...", "info")
            
            output_path = self.output_folder / task.get_filename()
            
            def progress_cb(progress: int):
                task.progress = progress
                if progress % 10 == 0:  # Log mỗi 10%
                    logger.debug(f"VM: Progress: {progress}%")
            
            success = self.merger.merge_videos(
                video_paths=valid_videos,
                output_path=str(output_path),
                progress_callback=progress_cb
            )
            
            if not success:
                raise RuntimeError("FFmpeg merge failed")
            
            # STEP 3: Success
            task.status = "completed"
            task.output_path = str(output_path)
            task.progress = 100
            
            filesize = os.path.getsize(output_path) / (1024 * 1024)
            
            self.stats['completed'] += 1
            self.stats['pending'] -= 1
            self.stats['videos_merged'] += len(valid_videos)
            
            logger.info(f"VM: ✓ Task completed: {output_path.name} ({filesize:.2f}MB)")
            self.log(f"✅ Merged batch#{task.batch_id}: {output_path.name} ({filesize:.1f}MB)", "ok")
            
        except Exception as e:
            logger.error(f"VM: Task failed: {e}", exc_info=True)
            
            task.status = "failed"
            task.error = str(e)
            
            self.stats['failed'] += 1
            self.stats['pending'] -= 1
            
            self.log(f"❌ Merge failed batch#{task.batch_id}: {str(e)[:100]}", "err")
    
    def get_stats(self) -> Dict:
        """Lấy thống kê"""
        return self.stats.copy()
    
    def get_tasks(self) -> List[MergeTask]:
        """Lấy danh sách tasks"""
        return list(self.tasks.values())
    
    def log(self, message: str, tag: str = None):
        """Log message to app's log widget (thread-safe)"""
        if hasattr(self.app, 'log'):
            try:
                self.app.log(f"[VM] {message}", tag)
            except Exception as e:
                logger.warning(f"Cannot log to app: {e}")


# ==================== INTEGRATION HELPER ====================

class VideoMergerIntegration:
    """
    Helper class tích hợp vào main app
    
    USAGE IN MAIN APP:
    ------------------
    # 1. Initialize
    self.videomerger = VideoMergerIntegration(self)
    
    # 2. Enable/Disable
    self.var_enable_merge = tk.BooleanVar(value=False)
    
    # 3. Khi watermark-free download thành công
    if self.var_enable_merge.get():
        self.videomerger.handle_download_success(video_path)
    """
    
    def __init__(self, app_instance):
        self.app = app_instance
        self.merger: Optional[VideoMerger] = None
        self.is_enabled: bool = False
    
    def enable(self, output_folder: str = "./downloads_merged", batch_size: int = 3):
        """Enable video merger"""
        if self.is_enabled:
            return
        
        try:
            self.merger = VideoMerger(
                app_instance=self.app,
                output_folder=output_folder,
                batch_size=batch_size
            )
            self.merger.start()
            self.is_enabled = True
            logger.info("VMI: Video merger enabled")
        except Exception as e:
            logger.error(f"VMI: Failed to enable video merger: {e}", exc_info=True)
            raise
    
    def disable(self):
        """Disable video merger"""
        if not self.is_enabled:
            return
        
        if self.merger:
            self.merger.stop()
        self.is_enabled = False
        logger.info("VMI: Video merger disabled")
    
    def handle_download_success(self, video_path: str):
        """
        Gọi hàm này SAU KHI watermark-free download thành công
        
        Args:
            video_path: Đường dẫn video đã download (no watermark)
        """
        if not self.is_enabled or not self.merger:
            return
        
        try:
            self.merger.add_video(video_path)
        except Exception as e:
            logger.error(f"VMI: Handle download error: {e}", exc_info=True)
    
    def flush_buffer(self):
        """Force merge các video còn lại trong buffer"""
        if self.merger:
            self.merger.flush_buffer()
    
    def set_batch_size(self, size: int):
        """Thiết lập batch size"""
        if self.merger:
            self.merger.set_batch_size(size)
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        if self.merger:
            return self.merger.get_stats()
        return {'total': 0, 'completed': 0, 'failed': 0, 'pending': 0, 'videos_merged': 0}


# ==================== STANDALONE TEST ====================

if __name__ == '__main__':
    # Test standalone
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    class MockApp:
        def log(self, message, tag=None):
            print(f"[LOG] {message}")
    
    app = MockApp()
    
    # Create merger
    print("\n=== TEST: VideoMerger Initialization ===")
    try:
        merger = VideoMerger(
            app_instance=app,
            output_folder="./test_merged",
            batch_size=2  # Test với 2 video
        )
        
        merger.start()
        
        print("\n✓ VideoMerger initialized successfully")
        print(f"✓ FFmpeg ready at: {FFMPEG_MANAGER.get_ffmpeg_command()}")
        
    except Exception as e:
        print(f"\n✗ Initialization failed: {e}")
        sys.exit(1)
    
    # Simulate adding videos
    test_videos = [
        "./downloads_nowatermark/video1.mp4",
        "./downloads_nowatermark/video2.mp4",
        "./downloads_nowatermark/video3.mp4",
        "./downloads_nowatermark/video4.mp4",
    ]
    
    print("\n=== TEST: Adding videos ===")
    for video in test_videos:
        print(f"Adding: {video}")
        merger.add_video(video)
        time.sleep(1)
    
    print("\n=== TEST: Waiting for completion ===")
    try:
        while True:
            stats = merger.get_stats()
            print(f"Stats: Total={stats['total']}, Completed={stats['completed']}, "
                  f"Failed={stats['failed']}, Pending={stats['pending']}", 
                  end='\r', flush=True)
            
            if stats['pending'] == 0 and stats['total'] > 0:
                print("\n✓ All tasks completed!")
                break
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n✗ Interrupted")
    finally:
        merger.stop()
        print("✓ Merger stopped")
