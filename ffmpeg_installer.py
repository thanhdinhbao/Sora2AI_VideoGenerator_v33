#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFmpeg Auto-Installer & Manager
Tự động tải và quản lý FFmpeg portable cho Windows
"""

import os
import sys
import zipfile
import shutil
import platform
import logging
from pathlib import Path
from typing import Optional
import urllib.request

logger = logging.getLogger(__name__)


class FFmpegInstaller:
    """
    Tự động tải và cài đặt FFmpeg portable
    Không cần quyền admin, không cần thêm vào PATH
    """
    
    # URL tải FFmpeg cho Windows (portable)
    FFMPEG_WINDOWS_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    def __init__(self, install_dir: str = "./ffmpeg_portable"):
        """
        Args:
            install_dir: Thư mục chứa FFmpeg portable
        """
        self.install_dir = Path(install_dir)
        self.ffmpeg_exe = None
        self.ffprobe_exe = None
        
    def is_installed(self) -> bool:
        """
        Kiểm tra FFmpeg đã được cài đặt và nhận diện chưa
        Returns: True nếu dùng được, False nếu lỗi.
        """
        # Check system FFmpeg
        system_ffmpeg = self._find_system_ffmpeg()
        if system_ffmpeg:
            self.ffmpeg_exe = system_ffmpeg
            self.ffprobe_exe = self._find_system_ffprobe()
            logger.info(f"[FFmpegInstaller] Found system FFmpeg: {self.ffmpeg_exe}")
            return True

        # Check portable FFmpeg
        exe_path = self.install_dir / "ffmpeg.exe"
        ffprobe_path = self.install_dir / "ffprobe.exe"
        if exe_path.exists() and ffprobe_path.exists():
            self.ffmpeg_exe = exe_path
            self.ffprobe_exe = ffprobe_path
            logger.info(f"[FFmpegInstaller] Found portable FFmpeg: {self.ffmpeg_exe}")
            return True

        logger.warning("[FFmpegInstaller] FFmpeg not found!")
        return False

    
    def _find_system_ffmpeg(self):
        # Check system PATH
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            return Path(ffmpeg_bin)
        # Check cùng thư mục main
        here = Path(__file__).parent
        candidate = here / "ffmpeg.exe"
        if candidate.exists():
            return candidate
        # Check thư mục chạy hiện tại
        candidate = Path(os.getcwd()) / "ffmpeg.exe"
        if candidate.exists():
            return candidate
        return None

    
    def _find_system_ffprobe(self) -> Optional[str]:
        """Tìm FFprobe trong system PATH"""
        try:
            if platform.system() == "Windows":
                result = os.popen("where ffprobe").read().strip()
            else:
                result = os.popen("which ffprobe").read().strip()
            
            if result and os.path.exists(result.split('\n')[0]):
                return result.split('\n')[0]
        except:
            pass
        return None
    
    def download_and_install(self, progress_callback=None) -> bool:
        """
        Tải và cài đặt FFmpeg portable (Windows).
        Tự động cleanup thư mục tạm nếu có lỗi.
        Returns: True nếu cài đặt thành công, False nếu thất bại.
        """
        temp_dir = self.install_dir / "ffmpeg_temp"
        zip_path = temp_dir / "ffmpeg.zip"
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"[FFmpegInstaller] Downloading FFmpeg to {zip_path} ...")
            urllib.request.urlretrieve(self.FFMPEG_WINDOWS_URL, str(zip_path))
            logger.info(f"[FFmpegInstaller] Extracting FFmpeg ...")
            with zipfile.ZipFile(str(zip_path), 'r') as zip_ref:
                zip_ref.extractall(str(temp_dir))
            
            # Tìm extracted folder chính xác
            extracted_dirs = [d for d in temp_dir.iterdir() if d.is_dir()]
            if not extracted_dirs:
                raise RuntimeError("No folder extracted from FFmpeg zip!")
            extracted_dir = extracted_dirs[0]

            if self.install_dir.exists():
                shutil.rmtree(self.install_dir)
            shutil.move(str(extracted_dir), str(self.install_dir))

            logger.info(f"[FFmpegInstaller] FFmpeg installed at {self.install_dir}")

            # Xóa thư mục tạm
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as clr:
                logger.warning(f"[FFmpegInstaller] Cleanup temp_dir failed: {clr}")

            # Xác thực cài đặt và version
            if self.is_installed():
                try:
                    version_cmd = [str(self.ffmpeg_exe), "-version"]
                    result = subprocess.run(version_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, text=True)
                    first_line = result.stdout.split('\n')[0]
                    if 'version' in first_line:
                        ver_num = first_line.split('version')[1].strip().split(' ')[0]
                        main_ver = float(ver_num.split('.')[0] + '.' + ver_num.split('.')[1])
                        if main_ver < 4.4:
                            logger.warning(f"[FFmpegInstaller] FFmpeg version too old: {main_ver}")
                    logger.info(f"✓ FFmpeg installed successfully at: {self.install_dir} - version: {ver_num}")
                except Exception as ve:
                    logger.warning("Could not verify FFmpeg version!")
                return True
            else:
                raise RuntimeError("Installation verification failed")
        except Exception as e:
            logger.error(f"Failed to install FFmpeg: {e}", exc_info=True)
            # Cleanup zip, temp nếu có
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as clr:
                logger.warning(f"Cleanup temp_dir failed: {clr}")
            return False

    
    def get_ffmpeg_path(self) -> str:
        """Lấy đường dẫn đến ffmpeg executable"""
        if not self.is_installed():
            raise RuntimeError("FFmpeg not installed. Call download_and_install() first.")
        return self.ffmpeg_exe
    
    def get_ffprobe_path(self) -> str:
        """Lấy đường dẫn đến ffprobe executable"""
        if not self.is_installed():
            raise RuntimeError("FFmpeg not installed. Call download_and_install() first.")
        return self.ffprobe_exe


class FFmpegManager:
    """
    Manager đơn giản để sử dụng FFmpeg
    Tự động kiểm tra và cài đặt nếu chưa có
    """
    
    _instance = None
    _installer = None
    
    @classmethod
    def get_instance(cls):
        """Singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._installer = FFmpegInstaller()
        self._ready = False
    
    def ensure_ffmpeg(self, progress_callback=None) -> bool:
        """
        Đảm bảo FFmpeg sẵn sàng sử dụng
        Tự động tải nếu chưa có
        
        Args:
            progress_callback: Hàm callback cho download progress
        
        Returns:
            True nếu FFmpeg sẵn sàng
        """
        if self._ready:
            return True
        
        # Check đã cài chưa
        if self._installer.is_installed():
            self._ready = True
            logger.info("✓ FFmpeg ready")
            return True
        
        # Chưa có → Tải về
        logger.info("FFmpeg not found. Downloading...")
        success = self._installer.download_and_install(progress_callback)
        
        if success:
            self._ready = True
            logger.info("✓ FFmpeg ready")
            return True
        else:
            logger.error("✗ Failed to setup FFmpeg")
            return False
    
    def get_ffmpeg_command(self) -> str:
        """Lấy command ffmpeg để chạy subprocess"""
        if not self._ready:
            raise RuntimeError("FFmpeg not ready. Call ensure_ffmpeg() first.")
        return self._installer.get_ffmpeg_path()
    
    def get_ffprobe_command(self) -> str:
        """Lấy command ffprobe để chạy subprocess"""
        if not self._ready:
            raise RuntimeError("FFmpeg not ready. Call ensure_ffmpeg() first.")
        return self._installer.get_ffprobe_path()


# ==================== TEST ====================

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("="*60)
    print("FFmpeg Auto-Installer Test")
    print("="*60)
    
    manager = FFmpegManager.get_instance()
    
    def progress(downloaded_mb, total_mb, percent):
        print(f"\rDownloading: {downloaded_mb:.1f}MB / {total_mb:.1f}MB ({percent:.1f}%)", end='', flush=True)
    
    print("\n[1] Checking FFmpeg...")
    if manager.ensure_ffmpeg(progress_callback=progress):
        print("\n✓ FFmpeg is ready!")
        print(f"   FFmpeg: {manager.get_ffmpeg_command()}")
        print(f"   FFprobe: {manager.get_ffprobe_command()}")
        
        # Test run
        print("\n[2] Testing FFmpeg...")
        import subprocess
        result = subprocess.run(
            [manager.get_ffmpeg_command(), '-version'],
            capture_output=True,
            text=True
        )
        print(result.stdout.split('\n')[0])
        print("✓ Test passed!")
    else:
        print("\n✗ Failed to setup FFmpeg")
