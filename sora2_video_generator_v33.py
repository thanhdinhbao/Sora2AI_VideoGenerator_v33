"""\nSora 2 AI Video Generator v28 - Full Edition (FIXED POPUPS)\n=============================================\nTrần Nguyên - Zalo: 0789.535.888\n\nVERSION 24 FEATURES:\n-------------------\n✅ Multi-Profile Management (5/10/15/20 profiles based on license)\n✅ Auto-switch profile when quota exhausted (30 videos/day/profile)\n✅ POST or DELETE draft after download\n✅ Profile statistics dashboard\n✅ License-based profile limits\n✅ Portable chrome_profile folder\n✅ Auto-detect existing profiles\n✅ FIXED: All popups with auto-close and timeout\n\nPOPUP FIXES:\n-----------\n✅ Confirmation dialogs: 3s timeout, default YES\n✅ Info dialogs: auto-close 3s\n✅ Warning dialogs: auto-close 5s\n❌ Error dialogs: NO changes (user must read)\n\nCHANGES FROM v22:\n-----------------\n+ ProfileManager integration\n+ Profile Stats UI in Settings tab\n+ Auto-rotation when quota reached\n+ get_license_features() import\n+ chrome_profile path = ./chrome_profile\n+ POST video feature with API client\n+ Draft action radio buttons (Delete/Post)\n\nINTEGRATION:\n-----------\n- sora2_license_system.py (with LICENSE_TIERS)\n- profile_manager.py (multi-profile management)\n- sora_api_client.py (POST video API)\n- text_to_video_tab.py (Text-to-Video tab)\n"""
import os
import json
import time
import threading
import sys
import queue
import logging
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from contextlib import contextmanager
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from tkinter.scrolledtext import ScrolledText
import requests
from curl_cffi import requests as curl_requests
from language_config import lang_manager
from profile_manager import ProfileManager, ProfileInfo, calculate_credits
from profile_token_manager import ProfileTokenManager
from text_to_video_tab import TextToVideoTab
from sora_api_client import SoraAPIClient
from sora_api_client_full import SoraAPIClient as SoraAPIClientFull
from credential_manager import CredentialManager
from api_generation_manager import APIGenerationManager
from unified_token_manager import AutoModeManager
from sora2_character_tab import Sora2CharacterTab
from watermark_free_downloader import WatermarkFreeIntegration, PostURLExtractor
from video_merger import FFmpegValidator
from video_merger import VideoMerger, MergeTask
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, WebDriverException
SELENIUM_AVAILABLE = True
from PIL import Image, ImageTk, ImageDraw
PIL_AVAILABLE = True
from path_helper import get_writable_path, get_chrome_profile_dir, get_profile_usage_path, get_profile_tokens_path, get_downloads_dir, get_config_path

class AutoCloseMessageBox:
    """\nHelper class for auto-closing messageboxes\n⚠️ DISABLED FOR API MODE - All methods return default values without showing popups\n"""

    @staticmethod
    def _auto_close_window(window, timeout_ms):
        """DISABLED - No-op"""  # inserted
        return

    @staticmethod
    def showinfo(title, message, timeout=3, **kwargs):
        """DISABLED - No popup shown in API mode"""  # inserted
        return

    @staticmethod
    def showwarning(title, message, timeout=5, **kwargs):
        """DISABLED - No popup shown in API mode"""  # inserted
        return

    @staticmethod
    def askyesno(title, message, timeout=3, default_yes=True, **kwargs):
        """DISABLED - Auto-return default value (True/False) without showing popup"""  # inserted
        return default_yes

    @staticmethod
    def askyesnocancel(title, message, timeout=3, default='yes', **kwargs):
        """DISABLED - Auto-return default value without showing popup"""  # inserted
        if default == 'yes':
            pass  # postinserted
        return True
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
try:
    from sora2_license_system import check_activation, show_activation_dialog, get_hardware_id, LICENSE_FILE, get_license_features
    from sora2_protection_system import ProtectionSystem
    from sora2_hash import EXPECTED_EXE_HASH
    protection_system = ProtectionSystem(enable_integrity_check=True, enable_anti_debug=False)
    LICENSE_ENABLED = True
    logger.info('[LICENSE] Security initialized')
    APP_NAME = 'Sora 2 Video Generator v28 - Multi-Profile Zalo: 0789.535.888'
    CONFIG_PATH = Path(get_config_path('sora_browser_config.json'))
    COOKIES_PATH = Path(get_config_path('sora_browser_cookies.json'))
    CHROME_PROFILES_DIR = Path(get_chrome_profile_dir())
    PROFILE_DATA_PATH = Path(get_profile_usage_path())
    SORA_URL = 'https://sora.chatgpt.com'
    DRAFTS_URL = 'https://sora.chatgpt.com/drafts'
    LOGIN_TIMEOUT = 300
    GENERATION_TIMEOUT = 600
    ELEMENT_TIMEOUT = 30
    DOWNLOAD_TIMEOUT = 120
    MAX_RETRIES = 3
    POLL_INTERVAL = 3
    from enum import Enum
    from dataclasses import dataclass

    class VideoStatus(Enum):
        PENDING = 'pending'
        PROCESSING = 'processing'
        COMPLETED = 'completed'
        FAILED = 'failed'

    class Orientation(Enum):
        PORTRAIT = '9:16'
        LANDSCAPE = '16:9'

        @classmethod
        def from_string(cls, value: str) -> 'Orientation':
            value_clean = value.strip().lower()
            return cls.PORTRAIT if value_clean in ['9:16', 'portrait'] else value_clean in ['16:9', 'landscape']

        def get_display_name(self) -> str:
            return 'Portrait' if self == Orientation.PORTRAIT else 'Landscape'

    @dataclass
    class VideoTask:
        prompt: str
        orientation: Orientation
        image_path: Optional[str] = None
        status: VideoStatus = VideoStatus.PENDING
        video_url: Optional[str] = None
        thumbnail_url: Optional[str] = None
        error: Optional[str] = None
        draft_id: Optional[str] = None

    def retry_on_exception(max_retries: int = MAX_RETRIES, delay: float = 1.0):
        """Decorator for retrying functions"""

        def decorator(func):
            def wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            logger.warning(f"Retry {attempt + 1}/{max_retries}: {e}")
                            time.sleep(delay * (attempt + 1))
                # for-else: chỉ chạy nếu không return thành công trong try
                else:
                    raise last_exception

            return wrapper

        return decorator

    def safe_execute_script(driver, script: str, *args):
        """Execute JavaScript with error handling"""  # inserted
        try:
            return driver.execute_script(script, *args)
        except Exception as e:
            logger.error(f'Script execution error: {e}')

    def create_placeholder_thumbnail(output_path: str, orientation: str='landscape'):
        """Create placeholder thumbnail"""  # inserted
        if not PIL_AVAILABLE:
            pass  # postinserted
        return False

    class ThreadSafeQueue:
        """Thread-safe queue"""

        def __init__(self):
            self._queue = queue.Queue()
            self._lock = threading.Lock()

        def put(self, item):
            with self._lock:
                self._queue.put(item)

        def get_nowait(self):
            with self._lock:
                return self._queue.get_nowait()

        def empty(self) -> bool:
            with self._lock:
                return self._queue.empty()

    def resize_reference_image(input_path: str, output_path: str, orientation: str='landscape', max_size: tuple=(80, 90)) -> bool:
        """Resize reference image for table display"""  # inserted
        if not PIL_AVAILABLE:
            pass  # postinserted
        return False

    class BrowserManager:
        """\nBrowser automation for Sora website\nHandles login, video generation, download, and cleanup\n"""
        pass
        pass
        pass
        pass
        def __init__(self, headless: bool=False, driver=None, download_dir: str=None, profile_path: str=None):
            """Initialize browser manager"""  # inserted
            self.headless = headless
            self.driver = driver
            self.download_dir = download_dir or str(Path(__file__).parent / 'downloads')
            self.profile_path = profile_path
            Path(self.download_dir).mkdir(parents=True, exist_ok=True)
            self.wait = None
            self._login_status = False
            if not self.driver:
                self._initialize_browser()
            return None

        def _initialize_browser(self):
            """Initialize Chrome driver"""  # inserted
            raise ImportError('Selenium not installed') if not SELENIUM_AVAILABLE else None
        
        def _kill_chrome_processes(self, user_data_dir: str):
            """Kill Chrome processes using this profile"""
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        if proc.info['name'] and 'chrome' in proc.info['name'].lower():
                            cmdline = ' '.join(proc.info['cmdline'] or [])
                            if user_data_dir in cmdline:
                                logger.info(f"Killing Chrome PID {proc.info['pid']}")
                                proc.kill()
                                time.sleep(0.5)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except ImportError:
                return None


        def trigger_pending_request(self, callback=None) -> bool:
            """Trigger pending request"""  # inserted
            try:
                callback('[TRIGGER] 🚀 Triggering request...', 'info') if callback else None
                self.driver.get('https://sora.chatgpt.com')
                time.sleep(3)
                self.driver.refresh()
                time.sleep(3)
                callback('[TRIGGER] ✅ Triggered', 'ok') if callback else None
                return True
            except Exception as e:
                logger.error(f'Trigger error: {e}')
                return False

        def extract_token_from_pending_request(self, callback=None) -> Optional[str]:
            """Extract token from performance logs"""
            try:
                if callback:
                    callback('[TOKEN] 🔍 Searching logs...', 'info')

                logs = self.driver.get_log('performance')

                for entry in logs:
                    try:
                        log_message = json.loads(entry['message'])
                        message = log_message.get('message', {})
                        method = message.get('method', '')

                        if method == 'Network.requestWillBeSent':
                            params = message.get('params', {})
                            request = params.get('request', {})
                            url = request.get('url', '')
                            headers = request.get('headers', {})

                            if 'pending' in url.lower():
                                auth_header = headers.get('Authorization') or headers.get('authorization')
                                if auth_header:
                                    token = auth_header.replace('Bearer ', '').strip()
                                    if token.startswith('eyJ') and token.count('.') == 2:
                                        if callback:
                                            callback(f'[TOKEN] ✅ Extracted ({len(token)} chars)', 'ok')
                                        return token

                    except Exception:
                        # Skip malformed log entries
                        continue

                # for-else executes ONLY when loop finishes without returning a token
                else:
                    if callback:
                        callback('[TOKEN] ⚠️ Not found', 'warn')

            except Exception as e:
                logger.error(f'Extract error: {e}')


        def close(self):
            """Close browser"""
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info('[BROWSER] Closed')
                    return None
                except Exception:
                    return None
            return None


    class ImagePreviewDialog(tk.Toplevel):
        """Image preview dialog"""

        def __init__(self, parent, image_path):
            super().__init__(parent)
            self.title('Image Preview')
            self.geometry('800x800')
            if not PIL_AVAILABLE:
                ttk.Label(self, text='PIL not installed').pack(pady=20)
                ttk.Button(self, text='Close', command=self.destroy).pack()
            return None

    class VideoPreviewDialog(tk.Toplevel):
        """Video details dialog"""

        def __init__(self, parent, video_data):
            super(video_data, self).__init__(parent)
            self.title('Video Details')
            self.geometry('600x700')
            main_frame = ttk.Frame(self, padding=20)
            main_frame.pack(fill='both', expand=True)
            if PIL_AVAILABLE and video_data.get('thumbnail_path'):
                if os.path.exists(video_data['thumbnail_path']):
                    try:
                        img = Image.open(video_data['thumbnail_path'])
                        img.thumbnail((400, 300))
                        photo = ImageTk.PhotoImage(img)
                        thumb_label = ttk.Label(main_frame, image=photo)
                        thumb_label.image = photo
                        thumb_label.pack(pady=10)
                    except:
                        pass
            info_frame = ttk.LabelFrame(main_frame, text='Video Information', padding=10)
            info_frame.pack(fill='x', pady=10)
            details = [('Prompt', video_data.get('prompt', 'N/A')), ('Orientation', video_data.get('orientation', 'N/A')), ('Status', video_data.get('status', 'N/A')), ('File', os.path.basename(video_data.get('path', 'N/A')))]
            for label, value in details:
                row = ttk.Frame(info_frame)
                row.pack(fill='x', pady=2)
                ttk.Label(row, text=f'{label}:', font=('Segoe UI', 9, 'bold'), width=15).pack(side='left')
                ttk.Label(row, text=value, wraplength=400).pack(side='left', fill='x', expand=True)
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill='x', pady=10)
            if video_data.get('path') and os.path.exists(video_data['path']):
                ttk.Button(btn_frame, text='Open Video', command=lambda: self.open_video(video_data['path'])).pack(side='left', padx=5)
                ttk.Button(btn_frame, text='Open Folder', command=lambda: self.open_folder(video_data['path'])).pack(side='left', padx=5)
            action_row = ttk.Frame(info_frame)
            action_row.pack(fill='x', pady=5)
            if video_data.get('draft_id'):
                self = video_data['draft_id']
                ttk.Button(action_row, text='📤 POST to Public', command=lambda: self.post_video_to_public(draft_id), width=18).pack(side='left', padx=5)
                ttk.Button(action_row, text='🗑️ DELETE Draft', command=lambda: self.delete_draft_api(draft_id), width=18).pack(side='left', padx=5)
            ttk.Button(btn_frame, text='Close', command=self.destroy).pack(side='right', padx=5)

        def open_video(self, path):
            import subprocess
            if sys.platform == 'win32':
                os.startfile(path)
            return None

        def open_folder(self, path):
            import subprocess
            folder = os.path.dirname(path)
            if sys.platform == 'win32':
                os.startfile(folder)
            return None

    class RegenDialog(tk.Toplevel):
        """Regenerate video dialog"""

        def __init__(self, parent, original_data):
            super().__init__(parent)
            self.title('Regenerate Video')
            self.geometry('600x450')
            self.result = None
            main_frame = ttk.Frame(self, padding=10)
            main_frame.pack(fill='both', expand=True)
            ttk.Label(main_frame, text='Prompt:', font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 5))
            self.txt_prompt = tk.Text(main_frame, height=6, wrap=tk.WORD, font=('Segoe UI', 10))
            self.txt_prompt.pack(fill='x', pady=(0, 10))
            self.txt_prompt.insert('1.0', original_data.get('prompt', ''))
            settings_frame = ttk.LabelFrame(main_frame, text='Settings', padding=10)
            settings_frame.pack(fill='x', pady=(0, 10))
            row1 = ttk.Frame(settings_frame)
            row1.pack(fill='x', pady=5)
            ttk.Label(row1, text='Orientation:', width=15).pack(side='left')
            self.cmb_orientation = ttk.Combobox(row1, values=['landscape', 'portrait'], state='readonly')
            self.cmb_orientation.pack(side='left', fill='x', expand=True)
            self.cmb_orientation.set(original_data.get('orientation', 'landscape'))
            row2 = ttk.Frame(settings_frame)
            row2.pack(fill='x', pady=5)
            ttk.Label(row2, text='Duration:', width=15).pack(side='left')
            self.cmb_duration = ttk.Combobox(row2, values=['10s', '15s'], state='readonly')
            self.cmb_duration.pack(side='left', fill='x', expand=True)
            self.cmb_duration.set(original_data.get('duration', '10s'))
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill='x', pady=10)
            ttk.Button(btn_frame, text='Regenerate', style='Accent.TButton', command=self.on_ok).pack(side='left', padx=5)
            ttk.Button(btn_frame, text='Cancel', command=self.destroy).pack(side='left')

        def on_ok(self):
            self.result = {'prompt': self.txt_prompt.get('1.0', 'end').strip(), 'orientation': self.cmb_orientation.get(), 'duration': self.cmb_duration.get()}
            self.destroy()

    class App:
        """Main Application with Multi-Profile Support"""

        def __init__(self, master):
            self.master = master
            self.lang = lang_manager
            self.setup_theme()
            self.master.configure(bg='#E3F2FD')
            self.master.title(APP_NAME)
            self.master.geometry('1600x1000')
            self.master.minsize(1400, 900)
            self.excel_data_i2v = []
            self.json_data_i2v = []
            if LICENSE_ENABLED:
                logger.info('[LICENSE] Running startup checks...')
                if not protection_system.protect_startup():
                    messagebox.showerror('Security Error', 'Security check failed.\nContact: Zalo 0789.535.888')
                    master.destroy()
                return None
            license_features = get_license_features()
            max_profiles = license_features.get('max_profiles', 5)
            logger.info('[LICENSE] Features loaded')
            CHROME_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
            logger.info(f'[PROFILE] Chrome profiles dir: {CHROME_PROFILES_DIR}')
            self.profile_manager = ProfileManager(profiles_base_dir=str(CHROME_PROFILES_DIR), max_profiles=max_profiles, data_file=str(PROFILE_DATA_PATH))
            self.api_client = None
            self.draft_action = tk.StringVar(value='delete')
            token_file = Path(get_profile_tokens_path())
            self.token_manager = ProfileTokenManager(str(token_file))
            logger.info(f"[TOKEN] Initialized with {self.token_manager.get_stats()['total']} tokens")
            self.api_manager = None
            self.current_profile = None
            self.browser = None
            self.concurrent_manager = None
            self.max_concurrent_workers = 2
            self.var_enable_concurrent = tk.BooleanVar(value=True)
            self.credential_manager = CredentialManager(credentials_dir='./credentials')
            from api_generation_manager import APIGenerationManager
            self.api_manager = APIGenerationManager(self.credential_manager)
            logger.info('[INIT] ✅ API Manager initialized')
            self.api_client_full = None
            self.mode_manager = None
            self.use_api_mode = False
            logger.info('[INIT] ✅ API mode support initialized')
            self.is_logged_in = False
            self.uploaded_images = []
            self.prompts = []
            self._gui_queue = queue.Queue()
            self.is_generating = False
            self.stop_generation = False
            self.config = self.load_config()
            self.legacy_token = self.config.get('bearer_token', '')
            logger.info('[TOKEN] Legacy credentials found') if self.legacy_token else None
            self.wf_integration = WatermarkFreeIntegration(self)
            self.video_merger = None
            self.var_enable_merger = tk.BooleanVar(value=False)
            self.var_merge_batch_size = tk.IntVar(value=5)
            self.var_concurrent_mode = tk.BooleanVar(value=False)
            self.wf_integration = WatermarkFreeIntegration(self)
            try:
                default_profile = 'Profile_1'
                if default_profile in self.credential_manager.list_profiles():
                    logger.info(f'[INIT] 🔄 Auto-loading {default_profile}...')
                    if not hasattr(self, 'api_manager') or not self.api_manager:
                        from api_generation_manager import APIGenerationManager
                        self.api_manager = APIGenerationManager(self.credential_manager)
                    success = self.api_manager.set_account(default_profile)
                    if success:
                        logger.info(f'[INIT] ✅ {default_profile} ready for API!')
                    self.build_ui()
                    self.process_gui_queue()
                    self.master.protocol('WM_DELETE_WINDOW', self.on_closing)
                    self.var_download_dir = tk.StringVar(value=self.config.get('download_dir', './downloads'))
                    self.var_headless = tk.BooleanVar(value=self.config.get('headless', False))
                    if LICENSE_ENABLED:
                        self.start_runtime_protection()
                    return None
            except Exception as e:
                logger.error(f'[INIT] Auto-load error: {e}')

        def setup_theme(self):
            """Theme xanh đậm - Tabs + Nội dung xanh xám"""  # inserted
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('TNotebook', background='#1976D2', borderwidth=0, tabmargins=[0, 0, 0, 0])
            style.configure('TNotebook.Tab', background='#1976D2', foreground='#FFD700', padding=[25, 12], font=('Arial', 10, 'bold'), borderwidth=0)
            style.map('TNotebook.Tab', background=[('selected', '#0D47A1'), ('!selected', '#1976D2')], foreground=[('selected', '#FFEB3B'), ('!selected', '#FFD700')], expand=[('selected', [1, 1, 1, 0])])
            style.configure('TFrame', background='#E3F2FD')
            style.configure('TLabel', background='#E3F2FD', foreground='#0D47A1')
            style.configure('TLabelframe', background='#E3F2FD', foreground='#1565C0', borderwidth=1)
            style.configure('TLabelframe.Label', background='#E3F2FD', foreground='#0D47A1', font=('Arial', 10, 'bold'))
            style.configure('TCheckbutton', background='#E3F2FD', foreground='#0D47A1')
            style.configure('TRadiobutton', background='#E3F2FD', foreground='#0D47A1')

        def rebuild_ui(self):
            """Rebuild entire UI after language change - NO RESTART NEEDED"""  # inserted
            try:
                self.log('[UI] 🔄 Rebuilding interface...', 'info')
                for widget in self.master.winfo_children():
                    widget.destroy()
                self._gui_queue = queue.Queue()
                self.build_ui()
                self.process_gui_queue()
                self.log('[UI] ✅ Interface rebuilt successfully!', 'ok')
            except Exception as e:
                logger.error(f'[UI] Rebuild error: {e}', exc_info=True)
                messagebox.showerror('Rebuild Error', f'Failed to rebuild UI:\n\n{str(e)[:200]}\n\nPlease restart the application.')

        def on_language_change(self, event=None):
            """Callback khi đổi ngôn ngữ - REBUILD UI NGAY"""  # inserted
            selected = self.cmb_language.get()
            lang_map = {'English': 'en', 'Tiếng Việt': 'vi'}
            lang_code = lang_map.get(selected)
            if lang_code and lang_code!= lang_manager.current_lang:
                self.save_language_preference(lang_code)
                lang_manager.set_language(lang_code)
                self.rebuild_ui()
                AutoCloseMessageBox.showinfo('Language Changed', f'✅ Language changed to {selected}\n\n✅ Đã đổi ngôn ngữ sang {selected}', timeout=3)
                return None
            return None

        def save_language_preference(self, lang_code: str):
            """Lưu ngôn ngữ vào file config"""
            config_file = get_config_path('language_preference.json')
            try:
                import json
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump({'language': lang_code}, f)
                logger.info(f'[LANG] Saved: {lang_code}')
            except Exception as e:
                logger.error(f'[LANG] Save error: {e}')


        def load_language_preference(self):
            """Load ngôn ngữ từ file config khi khởi động"""  # inserted
            config_file = get_config_path('language_preference.json')
            try:
                import json
                if os.path.exists(config_file):
                    with open(config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        lang_code = config.get('language', 'en')
                        lang_manager.set_language(lang_code)
                        logger.info(f'[LANG] Loaded: {lang_code}')
                        return lang_code
            except Exception as e:
                logger.error(f'[LANG] Load error: {e}')
                return 'en'

        def restart_application(self):
            """Khởi động lại ứng dụng"""  # inserted
            try:
                import sys
                import subprocess
                logger.info('[APP] Restarting...')
                self.master.destroy()
                python = sys.executable
                subprocess.Popen([python] + sys.argv)
                sys.exit(0)
            except Exception as e:
                logger.error(f'[APP] Restart error: {e}')
                self.master.destroy()
                sys.exit(0)

        def show_profile_stats(self):
            """Show profile statistics dialog"""  # inserted
            stats = self.profile_manager.get_profile_stats()
            dialog = tk.Toplevel(self.master)
            dialog.title('Profile Statistics')
            dialog.geometry('600x500')
            dialog.transient(self.master)
            dialog.grab_set()
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)
            ttk.Label(main_frame, text='📊 Profile Statistics', font=('Arial', 14, 'bold')).pack(pady=(0, 20))
            summary_frame = ttk.LabelFrame(main_frame, text='Summary', padding=15)
            summary_frame.pack(fill='x', pady=(0, 15))
            summary_data = [('Total Profiles', stats['total_profiles']), ('Active Profiles', stats['active_profiles']), ('Total Credits Quota', stats['total_credits_quota']), ('Credits Used Today', stats['credits_used_today']), ('Credits Remaining', stats['credits_remaining_today'])]
            for i, (label, value) in enumerate(summary_data):
                row = ttk.Frame(summary_frame)
                row.pack(fill='x', pady=2)
                ttk.Label(row, text=f'{label}:', font=('Arial', 10, 'bold'), width=20).pack(side='left')
                ttk.Label(row, text=str(value), font=('Arial', 10)).pack(side='left')
            details_frame = ttk.LabelFrame(main_frame, text='Profile Details', padding=15)
            details_frame.pack(fill='both', expand=True)
            tree = ttk.Treeview(details_frame, columns=('Status', 'Used', 'Max', 'Remaining'), show='tree headings', height=8)
            tree.heading('#0', text='Profile')
            tree.heading('Status', text='Status')
            tree.heading('Used', text='Used')
            tree.heading('Max', text='Max')
            tree.heading('Remaining', text='Remaining')
            tree.column('#0', width=150)
            tree.column('Status', width=80, anchor='center')
            tree.column('Used', width=80, anchor='center')
            tree.column('Max', width=80, anchor='center')
            tree.column('Remaining', width=100, anchor='center')
            scrollbar = ttk.Scrollbar(details_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            for p in stats['profiles']:
                status_icon = '✓' if p['active'] else '✗'
                status_color = 'green' if p['active'] else 'gray'
                tree.insert('', 'end', text=p['name'], values=(status_icon, p['credits_used'], p['max_credits'], p['remaining']), tags=(status_color,))
            tree.tag_configure('green', foreground='green')
            tree.tag_configure('gray', foreground='gray')
            ttk.Button(main_frame, text='Close', command=dialog.destroy).pack(pady=(15, 0))

        def update_profile_info_label(self):
            """Update profile info label in UI"""  # inserted
            if hasattr(self, 'lbl_profile_info'):
                stats = self.profile_manager.get_profile_stats()
                profile_info = f"Profiles: {stats['active_profiles']}/{stats['total_profiles']} active | Credits today: {stats['credits_used_today']}/{stats['total_credits_quota']} | Remaining: {stats['credits_remaining_today']}"
                self.lbl_profile_info.config(text=profile_info)
            return None

        def init_api_client(self):
            """\nInitialize API client by extracting tokens from browser\n"""  # inserted
            if not self.browser:
                AutoCloseMessageBox.showwarning('Warning', 'Browser not started!\n\nStart browser first.')
            return False

        def build_ui(self):
            """Build main UI with tabs"""  # inserted
            notebook = ttk.Notebook(self.master)
            notebook.configure(style='TNotebook')
            notebook.pack(fill='both', expand=True, padx=10, pady=10)
            tab_settings = ttk.Frame(notebook)
            notebook.add(tab_settings, text=self.lang.get('tab_settings'))
            self.build_settings_tab(tab_settings)
            tab_generation = ttk.Frame(notebook)
            notebook.add(tab_generation, text=self.lang.get('tab_image_to_video'))
            self.build_generation_tab(tab_generation)
            tab_text = ttk.Frame(notebook)
            notebook.add(tab_text, text=self.lang.get('tab_text_to_video'))
            self.text_to_video_tab = TextToVideoTab(tab_text, self, self.lang)
            tab_character = ttk.Frame(notebook)
            notebook.add(tab_character, text=self.lang.get('tab_character'))
            self.character_tab = Sora2CharacterTab(tab_character, self)
            self.video_merger_integration = None
            license_info = f' | License: {self._license_message}' if hasattr(self, '_license_message') else ''
            self.status_bar = ttk.Label(self.master, text=f'Ready - Sora 2 v24 Multi-Profile{license_info}', relief='sunken', anchor='w')
            self.status_bar.pack(fill='x', side='bottom')

        def build_settings_tab(self, parent: ttk.Frame):
            """\nBuild Settings tab - 2 COLUMN LAYOUT VERSION\n\n✅ CỘT TRÁI: Language + Profile + Download Directory\n✅ CỘT PHẢI: Browser + API Account\n"""  # inserted
            main_container = ttk.Frame(parent)
            main_container.pack(fill='both', expand=True, padx=10, pady=10)
            main_container.columnconfigure(0, weight=1)
            main_container.columnconfigure(1, weight=1)
            main_container.rowconfigure(0, weight=1)
            hw_id = tk.Canvas(main_container, borderwidth=0, bg='#E3F2FD')
            left_scrollbar = ttk.Scrollbar(main_container, orient='vertical', command=hw_id.yview)
            left_frame = ttk.Frame(hw_id)
            left_frame.bind('<Configure>', lambda e: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
            hw_id.create_window((0, 0), window=left_frame, anchor='nw')
            hw_id.configure(yscrollcommand=left_scrollbar.set)
            hw_id.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
            left_scrollbar.grid(row=0, column=0, sticky='nse')

            def _on_left_mousewheel(event):
                left_canvas.yview_scroll(int((-1) * (event.delta / 120)), 'units')
            hw_id.bind('<Enter>', lambda e: left_canvas.bind_all('<MouseWheel>', _on_left_mousewheel))
            hw_id.bind('<Leave>', lambda e: left_canvas.unbind_all('<MouseWheel>'))
            left_canvas = tk.Canvas(main_container, borderwidth=0, bg='#E3F2FD')
            right_scrollbar = ttk.Scrollbar(main_container, orient='vertical', command=left_canvas.yview)
            right_frame = ttk.Frame(left_canvas)
            right_frame.bind('<Configure>', lambda e: right_canvas.configure(scrollregion=right_canvas.bbox('all')))
            left_canvas.create_window((0, 0), window=right_frame, anchor='nw')
            left_canvas.configure(yscrollcommand=right_scrollbar.set)
            left_canvas.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
            right_scrollbar.grid(row=0, column=1, sticky='nse')

            def _on_right_mousewheel(event):
                right_canvas.yview_scroll(int((-1) * (event.delta / 120)), 'units')
            left_canvas.bind('<Enter>', lambda e: right_canvas.bind_all('<MouseWheel>', _on_right_mousewheel))
            left_canvas.bind('<Leave>', lambda e: right_canvas.unbind_all('<MouseWheel>'))
            lang_frame = ttk.LabelFrame(left_frame, text='🌐 ' + self.lang.get('language'), padding=20)
            lang_frame.pack(fill='x', pady=(0, 15))
            lang_row = ttk.Frame(lang_frame)
            lang_row.pack(fill='x', pady=10)
            ttk.Label(lang_row, text=self.lang.get('select_language') + ':', font=('Arial', 10)).pack(side='left', padx=(0, 10))
            self.cmb_language = ttk.Combobox(lang_row, values=list(self.lang.get_available_languages().values()), state='readonly')
            self.cmb_language.pack(side='left', fill='x', expand=True, padx=5)
            self.cmb_language.set('English')
            self.cmb_language.bind('<<ComboboxSelected>>', self.on_language_change)
            profile_frame = ttk.LabelFrame(left_frame, text='👤 ' + self.lang.get('profile_management_title'), padding=20)
            profile_frame.pack(fill='x', pady=(0, 15))
            create_row = ttk.Frame(profile_frame)
            create_row.pack(fill='x', pady=(0, 10))
            ttk.Label(create_row, text=self.lang.get('create_profiles_button') + ':', font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
            self.var_num_profiles = tk.IntVar(value=5)
            ttk.Spinbox(create_row, from_=1, to=100, textvariable=self.var_num_profiles, width=10).pack(side='left', padx=5)
            ttk.Label(create_row, text=f"({self.lang.get('max')}: {self.profile_manager.max_profiles})").pack(side='left', padx=5)
            ttk.Button(create_row, text=self.lang.get('create_profiles_button'), command=self.create_profiles_action).pack(side='left', fill='x', expand=True, padx=10)
            stats = self.profile_manager.get_profile_stats()
            profile_info = f"{self.lang.get('profiles')}: {stats['active_profiles']}/{stats['total_profiles']} {self.lang.get('active')} | {self.lang.get('quota')} {self.lang.get('today')}: {stats['credits_used_today']}/{stats['total_credits_quota']} | {self.lang.get('remaining')}: {stats['credits_remaining_today']}"
            self.lbl_profile_info = ttk.Label(profile_frame, text=profile_info, foreground='blue', font=('Arial', 9))
            self.lbl_profile_info.pack(anchor='w', pady=(10, 0))
            ttk.Button(profile_frame, text=self.lang.get('view_profile_stats'), command=self.show_profile_stats).pack(fill='x', pady=(5, 0))
            download_frame = ttk.LabelFrame(left_frame, text=self.lang.get('download_dir'), padding=20)
            download_frame.pack(fill='both', expand=True, pady=(0, 15))
            system_frame = ttk.LabelFrame(left_frame, text='🔐 System Information', padding=20)
            system_frame.pack(fill='x', pady=(0, 15))
            try:
                from single_instance_lock import SingleInstanceLock
                lock_temp = SingleInstanceLock()
                _on_right_mousewheel = lock_temp._get_hardware_id()
                info_row = ttk.Frame(system_frame)
                info_row.pack(fill='x', pady=5)
                ttk.Label(info_row, text='Hardware ID:', font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
                hw_id_entry = ttk.Entry(info_row, width=30, font=('Courier', 10))
                hw_id_entry.pack(side='left', fill='x', expand=True, padx=5)
                hw_id_entry.insert(0, _on_right_mousewheel)
                hw_id_entry.config(state='readonly')

                def copy_hw_id():
                    self.master.clipboard_clear()
                    self.master.clipboard_append(hw_id)
                    self.log(f'📋 Hardware ID copied: {hw_id}', 'ok')
                    messagebox.showinfo('Copied', f'✅ Hardware ID copied to clipboard!\n\n{hw_id}')
                ttk.Button(info_row, text='📋 Copy', command=copy_hw_id, width=8).pack(side='left', padx=5)
                ttk.Label(system_frame, text='ℹ️ Use this ID for license activation\nContact: Zalo 0789.535.888', font=('Arial', 8), foreground='blue', justify='left').pack(anchor='w', pady=(10, 0))
                dir_row = ttk.Frame(download_frame)
                dir_row.pack(fill='x', pady=5)
                self.var_download_dir = tk.StringVar(value=self.config.get('download_dir', './downloads'))
                ttk.Label(dir_row, text=self.lang.get('save_to')).pack(side='left', padx=(0, 10))
                ttk.Entry(dir_row, textvariable=self.var_download_dir).pack(side='left', fill='x', expand=True, padx=5)
                ttk.Button(dir_row, text=self.lang.get('browse_btn'), command=self.browse_download_dir, width=12).pack(side='left')
                browser_frame = ttk.LabelFrame(right_frame, text='🌐 Browser (One-Time Login Only)', padding=20)
                browser_frame.pack(fill='x', pady=(0, 15))
                ttk.Label(browser_frame, text='ℹ️ Use browser ONLY for first-time login\n✅ Login once → Save credentials → Close browser\n✅ After that, use 100% API mode!', font=('Arial', 9), foreground='blue', justify='left').pack(anchor='w', pady=(0, 10))
                status_row = ttk.Frame(browser_frame)
                status_row.pack(fill='x', pady=(0, 10))
                self.lbl_browser_status = ttk.Label(status_row, text='⚪ Browser: Not running', font=('Arial', 10, 'bold'), foreground='gray')
                self.lbl_browser_status.pack(side='left')
                self.lbl_login_status = ttk.Label(status_row, text='', font=('Arial', 9), foreground='gray')
                self.lbl_login_status.pack(side='left', padx=(20, 0))
                ttk.Separator(browser_frame, orient='horizontal').pack(fill='x', pady=10)
                profile_select_frame = ttk.Frame(browser_frame)
                profile_select_frame.pack(fill='x', pady=(0, 10))
                ttk.Label(profile_select_frame, text='Select Profile:', font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
                self.var_selected_profile = tk.StringVar()
                self.combo_profile = ttk.Combobox(profile_select_frame, textvariable=self.var_selected_profile, state='readonly')
                self.combo_profile.pack(side='left', fill='x', expand=True, padx=5)
                ttk.Button(profile_select_frame, text='🔄', command=self.update_profile_combo, width=3).pack(side='left')
                self.update_profile_combo()
                headless_row = ttk.Frame(browser_frame)
                headless_row.pack(fill='x', pady=(0, 10))
                self.var_headless = tk.BooleanVar(value=False)
                ttk.Checkbutton(headless_row, text='Run in Headless Mode', variable=self.var_headless).pack(side='left')
                ttk.Label(headless_row, text='⚠️ Uncheck for first login', font=('Arial', 8), foreground='orange').pack(side='left', padx=(10, 0))
                btn_frame = ttk.Frame(browser_frame)
                btn_frame.pack(fill='x', pady=(10, 0))
                self.btn_start_browser = ttk.Button(btn_frame, text='🚀 Start Browser', command=self.start_browser_for_profile_login, style='Accent.TButton')
                self.btn_start_browser.pack(side='left', fill='x', expand=True, padx=5)
                self.btn_extract_creds = ttk.Button(btn_frame, text='✅ Extract & Save', command=self.extract_profile_credentials, state='disabled')
                self.btn_extract_creds.pack(side='left', fill='x', expand=True, padx=5)
                self.btn_stop_browser = ttk.Button(btn_frame, text='⏹️ Stop', command=self.stop_browser, state='disabled')
                self.btn_stop_browser.pack(side='left', fill='x', expand=True, padx=5)
                account_frame = ttk.LabelFrame(right_frame, text='🚀 API Account (Select to Generate)', padding=20)
                account_frame.pack(fill='x', pady=(0, 15))
                ttk.Label(account_frame, text='ℹ️ Select account with saved credentials to generate via API\n✅ No browser needed during generation\n✅ Fully automated and faster', font=('Arial', 9), foreground='blue', justify='left').pack(anchor='w', pady=(0, 10))
                select_row = ttk.Frame(account_frame)
                select_row.pack(fill='x', pady=(10, 5))
                ttk.Label(select_row, text='API Account:', font=('Arial', 10, 'bold')).pack(side='left', padx=(0, 10))
                self.account_var = tk.StringVar()
                self.account_dropdown = ttk.Combobox(select_row, textvariable=self.account_var, state='readonly')
                self.account_dropdown.pack(side='left', fill='x', expand=True, padx=5)
                self.account_dropdown.bind('<<ComboboxSelected>>', self._on_account_selected)
                ttk.Button(select_row, text='🔄', command=self._refresh_accounts_list, width=3).pack(side='left', padx=2)
                self.account_status_label = ttk.Label(account_frame, text='Status: No account selected', font=('Arial', 9), foreground='gray')
                self.account_status_label.pack(anchor='w', pady=5)
                btn_row = ttk.Frame(account_frame)
                btn_row.pack(fill='x', pady=(10, 0))
                ttk.Button(btn_row, text='✅ Check Status', command=self._check_account_status).pack(side='left', fill='x', expand=True, padx=5)
                ttk.Button(btn_row, text='🗑️ Remove', command=self._remove_account).pack(side='left', fill='x', expand=True, padx=5)
                self._refresh_accounts_list()
            except Exception as e:
                _on_right_mousewheel = 'Unknown'
                print(f'[ERROR] Cannot get hardware ID: {e}')

        def _refresh_accounts_list(self):
            """Refresh account dropdown - FIXED VERSION"""  # inserted
            try:
                accounts = self.credential_manager.list_profiles()
                if accounts:
                    self.account_dropdown['values'] = accounts
                    if not self.account_var.get() or self.account_var.get() not in accounts:
                        self.account_var.set(accounts[0])
                        self._load_account(accounts[0])
                    return None
                return None
            except Exception as e:
                logger.error(f'Refresh accounts error: {e}')

        def _on_account_selected(self, event=None):
            """Handle account selection - FIXED"""  # inserted
            try:
                account = self.account_var.get()
                if account:
                    if account!= 'No accounts - Extract first':
                        self._load_account(account)
                    return
            except Exception as e:
                logger.error(f'Account selected error: {e}')

        def _load_account(self, account_name: str):
            """Load account for API - CRITICAL FIX"""  # inserted
            try:
                self.log(f'[ACCOUNT] 📂 Loading: {account_name}', 'info')
                if not hasattr(self, 'api_manager') or not self.api_manager:
                    from api_generation_manager import APIGenerationManager
                    self.api_manager = APIGenerationManager(self.credential_manager)
                success = self.api_manager.set_account(account_name)
                if success:
                    self.account_status_label.config(text=f'Status: ✅ {account_name} ready for API', foreground='green')
                    self.log(f'[ACCOUNT] ✅ {account_name} loaded', 'ok')
                return None
            except Exception as e:
                logger.error(f'Load account error: {e}', exc_info=True)
                self.account_status_label.config(text='Status: ❌ Error', foreground='red')

        def _check_account_status(self):
            """Check if account/token is valid - FIXED"""  # inserted
            try:
                account = self.account_var.get()
                if not account or account == 'No accounts - Extract first':
                    messagebox.showinfo('No Selection', 'Select account first!')
                return None
            except Exception as e:
                logger.error(f'Check account error: {e}')
                messagebox.showerror('Error', str(e)[:200])

        def _remove_account(self):
            """Remove account credentials - FIXED"""  # inserted
            try:
                account = self.account_var.get()
                if not account or account == 'No accounts - Extract first':
                    messagebox.showinfo('No Selection', 'Select account first!')
                return None
            except Exception as e:
                logger.error(f'Remove account error: {e}')

        def extract_profile_credentials(self):
            """Extract credentials - SAVE TO CREDENTIALMANAGER"""  # inserted
            if not self.browser or not self.current_profile:
                messagebox.showwarning('No Browser', 'Browser not running!')
            return None

        def force_extract_token_now(self):
            """\nForce extract token from browser NOW\n\nSimplified version - no options, just extract and save\n"""  # inserted
            try:
                if not self.browser or not self.browser.driver:
                    AutoCloseMessageBox.showwarning('No Browser', '❌ Browser not running!\n\nSteps:\n1. Start Browser & Open Sora\n2. Login to Sora\n3. Click this button again')
                return None
            except Exception as e:
                logger.error(f'Force extract error: {e}', exc_info=True)
                messagebox.showerror('Error', f'Extraction failed:\n\n{str(e)[:200]}')

        def on_profile_mode_change(self):
            """Handle profile mode change"""  # inserted
            if self.var_profile_mode.get() == 'manual':
                self.combo_profile.config(state='readonly')
            return None

        def update_profile_combo(self):
            """Update profile dropdown"""  # inserted
            profiles = self.profile_manager.profiles
            if profiles:
                profile_names = [p.profile_name for p in profiles]
                self.combo_profile['values'] = profile_names
                if profile_names and (not self.var_selected_profile.get()):
                    self.var_selected_profile.set(profile_names[0])
            self.on_profile_mode_change()

        def update_login_status(self, status, color='gray'):
            """Update login status label"""  # inserted
            self.lbl_login_status.config(text=status, foreground=color)

        def _check_login_after_navigate(self):
            """Check login after navigate - WITH AUTO TOKEN EXTRACTION"""  # inserted
            try:
                if not self.browser:
                    pass  # postinserted
                return None
            except Exception as e:
                logger.error(f'Check login error: {e}', exc_info=True)

        def _inject_token_monitor(self):
            """\nInject JavaScript to monitor and capture Authorization header\n"""  # inserted
            try:
                script = '\n            // Create global storage for captured token\n            window.__SORA_CAPTURED_TOKEN__ = null;\n            \n            // Intercept fetch\n            const originalFetch = window.fetch;\n            window.fetch = function(...args) {\n                // Capture headers before request\n                const url = args[0];\n                const options = args[1] || {};\n                \n                if (options.headers) {\n                    const headers = options.headers;\n                    const authHeader = headers[\'Authorization\'] || headers[\'authorization\'];\n                    \n                    if (authHeader && !window.__SORA_CAPTURED_TOKEN__) {\n                        window.__SORA_CAPTURED_TOKEN__ = authHeader.replace(\'Bearer \', \'\');\n                        console.log(\'[SORA] Token captured from fetch:\', window.__SORA_CAPTURED_TOKEN__.substring(0, 20) + \'...\');\n                    }\n                }\n                \n                return originalFetch.apply(this, args);\n            };\n            \n            // Intercept XHR\n            const originalOpen = XMLHttpRequest.prototype.open;\n            const originalSetRequestHeader = XMLHttpRequest.prototype.setRequestHeader;\n            \n            XMLHttpRequest.prototype.setRequestHeader = function(header, value) {\n                if ((header === \'Authorization\' || header === \'authorization\') && !window.__SORA_CAPTURED_TOKEN__) {\n                    window.__SORA_CAPTURED_TOKEN__ = value.replace(\'Bearer \', \'\');\n                    console.log(\'[SORA] Token captured from XHR:\', window.__SORA_CAPTURED_TOKEN__.substring(0, 20) + \'...\');\n                }\n                return originalSetRequestHeader.apply(this, arguments);\n            };\n            \n            console.log(\'[SORA] Token monitor injected successfully\');\n            '
                self.browser.driver.execute_script(script)
                self.log('[TOKEN] 🎯 Injected network monitor', 'info')
            except Exception as e:
                logger.error(f'Inject token monitor error: {e}')

        def _extract_token_from_monitor(self) -> Optional[str]:
            """\nExtract captured token from injected monitor\n\nReturns:\n    Bearer token or None\n"""  # inserted
            try:
                token = self.browser.driver.execute_script('return window.__SORA_CAPTURED_TOKEN__;')
                if token:
                    if token.startswith('eyJ') and token.count('.') == 2:
                        self.log(f'[TOKEN] ✅ Captured token ({len(token)} chars)', 'ok')
                        self.log(f'          Preview: {token[:20]}...{token[(-15):]}', 'info')
                        return token
                return None
            except Exception as e:
                logger.error(f'Extract from monitor error: {e}')

        def _auto_save_extracted_token(self, token: str):
            """\nAuto-save extracted token to current profile\n\nArgs:\n    token: Bearer token string\n"""  # inserted
            try:
                if not self.current_profile:
                    self.log('[TOKEN] ⚠️ No current profile to save to', 'warn')
                return None
            except Exception as e:
                logger.error(f'Auto-save token error: {e}')

        def _show_auto_close_notification(self, title: str, message: str, duration: int = 5000):
            """
            Show auto-closing notification dialog

            Args:
                title: Dialog title
                message: Message text
                duration: Auto-close after milliseconds (default 5s)
            """
            try:
                dialog = tk.Toplevel(self.master)
                dialog.title(title)
                dialog.geometry('500x300')
                dialog.transient(self.master)
                dialog.attributes('-topmost', True)

                dialog.update_idletasks()
                x = dialog.winfo_screenwidth() // 2 - dialog.winfo_width() // 2
                y = dialog.winfo_screenheight() // 2 - dialog.winfo_height() // 2
                dialog.geometry(f'+{x}+{y}')

                # UI
                main_frame = ttk.Frame(dialog, padding=20)
                main_frame.pack(fill='both', expand=True)

                ttk.Label(main_frame, text='✅', font=('Arial', 48)).pack(pady=(10, 15))
                ttk.Label(main_frame, text=message, font=('Arial', 10), justify='left').pack(pady=10, padx=10)

                remaining = duration // 1000
                countdown_label = ttk.Label(
                    main_frame,
                    text=f'Auto-closing in {remaining}s...',
                    font=('Arial', 8),
                    foreground='gray'
                )
                countdown_label.pack(pady=(15, 5))

                ttk.Button(main_frame, text='Close Now', command=dialog.destroy).pack(pady=5)

                # Countdown function
                def update_countdown(remaining_time):
                    if remaining_time <= 0:
                        try:
                            dialog.destroy()
                        except Exception:
                            pass
                        return

                    countdown_label.config(text=f'Auto-closing in {remaining_time}s...')
                    dialog.after(1000, lambda: update_countdown(remaining_time - 1))

                dialog.after(1000, lambda: update_countdown(remaining - 1))

            except Exception as e:
                logger.error(f'Notification dialog error: {e}')


        def check_login_status(self):
            """Check current login status - WITH AUTO TOKEN EXTRACTION"""  # inserted
            if not self.browser:
                AutoCloseMessageBox.showwarning('No Browser', 'Start browser first.')
            return None

        def _auto_extract_and_save_token(self):
            """\nAuto-extract token from browser and save to current profile\n\nThis method:\n1. Triggers \'pending\' request\n2. Extracts token from performance logs\n3. Validates token format\n4. Saves to ProfileTokenManager\n5. Shows success notification\n\nCalled after manual login is detected.\n"""  # inserted
            try:
                if not self.browser or not self.browser.driver:
                    self.log('[TOKEN] ❌ Browser not available', 'err')
                return None
                download_frame = ttk.LabelFrame(main_frame, text=self.lang.get('download_dir'), padding=20)
                download_frame.pack(fill='x', pady=(0, 15))
                dir_row = ttk.Frame(download_frame)
                dir_row.pack(fill='x', pady=5)
                self.var_download_dir = tk.StringVar(value=self.config.get('download_dir', './downloads'))
                ttk.Label(dir_row, text=self.lang.get('save_to')).pack(side='left', padx=(0, 10))
                ttk.Entry(dir_row, textvariable=self.var_download_dir, width=50).pack(side='left', fill='x', expand=True, padx=5)
                ttk.Button(dir_row, text=self.lang.get('browse_btn'), command=self.browse_download_dir, width=12).pack(side='left')
            except Exception as e:
                logger.error(f'Auto-extract token error: {e}', exc_info=True)
                self.log(f'[TOKEN] ❌ ERROR: {str(e)[:200]}', 'err')

        def on_profile_mode_change(self):
            """Handle profile mode change (auto vs manual)"""  # inserted
            if self.var_profile_mode.get() == 'manual':
                self.combo_profile.config(state='readonly')
            return None

        def update_profile_combo(self):
            """Update profile dropdown with available profiles"""  # inserted
            profiles = self.profile_manager.profiles
            if profiles:
                profile_names = [p.profile_name for p in profiles]
                self.combo_profile['values'] = profile_names
                if profile_names and (not self.var_selected_profile.get()):
                    self.var_selected_profile.set(profile_names[0])
            self.on_profile_mode_change()

        def create_profiles_action(self):
            """Create multiple Chrome profiles"""  # inserted
            num_profiles = self.var_num_profiles.get()
            if num_profiles > self.profile_manager.max_profiles:
                AutoCloseMessageBox.showwarning('Limit Exceeded', f'Your license allows maximum {self.profile_manager.max_profiles} profiles.\n\nRequested: {num_profiles}\nMaximum: {self.profile_manager.max_profiles}\n\nContact: Zalo 0789.535.888 for upgrade')
            return None

        def extract_token_from_browser(self):
            """Extract bearer token from current browser session"""  # inserted
            if not self.browser or not self.browser.driver:
                AutoCloseMessageBox.showwarning('No Browser', 'Browser not started!\n\nStart browser and login first.')
            return None

        def refresh_token_table(self):
            """Refresh token status table - SIMPLIFIED"""  # inserted
            if not hasattr(self, 'token_tree'):
                pass  # postinserted
            return None

        def get_token_for_profile(self, profile_name: str) -> Optional[str]:
            """\nGet token with proper profile isolation - FIXED VERSION\n\nArgs:\n    profile_name: Profile identifier (e.g., \"Profile_1\", \"Default\")\n\nReturns:\n    Bearer token string or None\n"""  # inserted
            if not profile_name:
                logger.error('[TOKEN] ❌ No profile name provided!')
                self.log('[TOKEN] ❌ No profile name provided!', 'err')
            return None

        def init_api_client_for_profile(self, profile_name: str):
            """Initialize Full API client for profile with upload support"""  # inserted
            try:
                self.log(f'[API] Initializing client for {profile_name}...', 'info')
                bearer_token = self.token_manager.get_token(profile_name)
                if not bearer_token:
                    self.log(f'[API] ❌ No token for {profile_name}', 'err')
                return False
            except Exception as e:
                logger.error(f'Init API client error: {e}', exc_info=True)
                self.log(f'[API] ❌ Init error: {str(e)[:100]}', 'err')
                return False

        def build_generation_tab(self, parent: ttk.Frame):
            """Build Image-to-Video generation tab - FIXED VERSION"""  # inserted
            main_frame = ttk.Frame(parent)
            main_frame.pack(fill='both', expand=True, padx=8, pady=8)
            left_container = ttk.Frame(main_frame, width=400)
            left_container.pack(side='left', fill='y', padx=(0, 8))
            left_container.pack_propagate(False)
            canvas_window = tk.Canvas(left_container, bg='#E3F2FD', highlightthickness=0)
            left_scrollbar = ttk.Scrollbar(left_container, orient='vertical', command=canvas_window.yview)
            left_panel = ttk.Frame(canvas_window)
            left_panel.bind('<Configure>', lambda e: left_canvas.configure(scrollregion=left_canvas.bbox('all')))
            _on_mousewheel = canvas_window.create_window((0, 0), window=left_panel, anchor='nw')
            canvas_window.configure(yscrollcommand=left_scrollbar.set)
            left_scrollbar.pack(side='right', fill='y')
            canvas_window.pack(side='left', fill='both', expand=True)

            def _on_mousewheel(event):
                left_canvas.yview_scroll(int((-1) * (event.delta / 120)), 'units')
            canvas_window.bind('<Enter>', lambda e: left_canvas.bind_all('<MouseWheel>', _on_mousewheel))
            canvas_window.bind('<Leave>', lambda e: left_canvas.unbind_all('<MouseWheel>'))

            def _on_canvas_configure(event):
                left_canvas.itemconfig(canvas_window, width=event.width)
            canvas_window.bind('<Configure>', _on_canvas_configure)
            image_frame = ttk.LabelFrame(left_panel, text=self.lang.get('ref_images'), padding=10)
            image_frame.pack(fill='x', pady=(0, 8))
            img_btn_row1 = ttk.Frame(image_frame)
            img_btn_row1.pack(fill='x', pady=(0, 5))
            ttk.Button(img_btn_row1, text=self.lang.get('add_images'), command=self.add_images, width=15).pack(side='left', padx=2)
            ttk.Button(img_btn_row1, text=self.lang.get('get_paths'), command=self.get_image_paths, width=15).pack(side='left', padx=2)
            img_btn_row2 = ttk.Frame(image_frame)
            img_btn_row2.pack(fill='x')
            ttk.Button(img_btn_row2, text=self.lang.get('clear_images'), command=self.clear_images, width=15).pack(side='left', padx=2)
            self.lbl_image_count = ttk.Label(image_frame, text=f"📊 {self.lang.get('images')}: 0", foreground='blue', font=('Segoe UI', 9))
            self.lbl_image_count.pack(anchor='w', pady=(8, 0))
            settings_frame = ttk.LabelFrame(left_panel, text=self.lang.get('gen_settings'), padding=10)
            settings_frame.pack(fill='x', pady=(0, 8))
            ttk.Label(settings_frame, text=self.lang.get('orientation') + ':').grid(row=0, column=0, sticky='w', pady=5)
            self.cmb_orientation = ttk.Combobox(settings_frame, values=['landscape', 'portrait'], state='readonly', width=30)
            self.cmb_orientation.grid(row=1, column=0, sticky='ew', pady=5)
            self.cmb_orientation.set('landscape')
            ttk.Label(settings_frame, text=self.lang.get('duration') + ':').grid(row=2, column=0, sticky='w', pady=5)
            self.cmb_duration = ttk.Combobox(settings_frame, values=['10s', '15s'], state='readonly', width=30)
            self.cmb_duration.grid(row=3, column=0, sticky='ew', pady=5)
            self.cmb_duration.set('10s')
            ttk.Label(settings_frame, text=self.lang.get('draft_action_title')).grid(row=4, column=0, sticky='w', pady=(10, 5))
            ttk.Separator(settings_frame, orient='horizontal').grid(row=8, column=0, sticky='ew', pady=10)
            self.var_enable_wf_download = tk.BooleanVar(value=False)
            ttk.Checkbutton(settings_frame, text=self.lang.get('download_no_watermark'), variable=self.var_enable_wf_download, command=self.toggle_wf_download).grid(row=9, column=0, sticky='w', pady=5)
            wf_info = f"{self.lang.get('only_works_post_mode')}\n{self.lang.get('videos_saved_to')}"
            ttk.Label(settings_frame, text=wf_info, font=('Arial', 8), foreground='gray', wraplength=280, justify='left').grid(row=10, column=0, sticky='w', pady=(5, 0))
            self.lbl_wf_stats_i2v = ttk.Label(settings_frame, text=f"{self.lang.get('stats')}: 0 {self.lang.get('total')} | 0 {self.lang.get('completed')} | 0 {self.lang.get('failed')}", font=('Arial', 8), foreground='blue')
            self.lbl_wf_stats_i2v.grid(row=11, column=0, sticky='w', pady=(5, 0))

            def update_wf_stats_i2v():
                if hasattr(self, 'wf_integration'):
                    stats = self.wf_integration.get_stats()
                    self.lbl_wf_stats_i2v.config(text=f"Stats: {stats['total']} total | {stats['completed']} completed | {stats['failed']} failed")
                self.master.after(2000, update_wf_stats_i2v)
            update_merger_stats_i2v()
            ttk.Separator(settings_frame, orient='horizontal').grid(row=12, column=0, sticky='ew', pady=10)
            self.var_enable_merger = tk.BooleanVar(value=False)
            ttk.Checkbutton(settings_frame, text=self.lang.get('enable_merger'), variable=self.var_enable_merger, command=self.toggle_video_merger).grid(row=13, column=0, sticky='w', pady=5)
            merger_batch_row = ttk.Frame(settings_frame)
            merger_batch_row.grid(row=14, column=0, sticky='w', pady=5, padx=(20, 0))
            ttk.Label(merger_batch_row, text=self.lang.get('batch_size')).pack(side='left', padx=(0, 5))
            ttk.Spinbox(merger_batch_row, from_=2, to=20, textvariable=self.var_merge_batch_size, command=self.update_merger_batch_size, width=10).pack(side='left')
            ttk.Label(merger_batch_row, text=self.lang.get('videos_batch')).pack(side='left', padx=(5, 0))
            merger_info_i2v = f"{self.lang.get('auto_merge')}\n{self.lang.get('output_folder')}"
            ttk.Label(settings_frame, text=merger_info_i2v, font=('Arial', 8), foreground='gray', wraplength=280, justify='left').grid(row=15, column=0, sticky='w', pady=(5, 0))
            self.lbl_merger_stats_i2v = ttk.Label(settings_frame, text=self.lang.get('merger_disabled'), font=('Arial', 9, 'bold'), foreground='purple')
            self.lbl_merger_stats_i2v.grid(row=16, column=0, sticky='w', pady=(5, 0))

            def update_merger_stats_i2v():
                if hasattr(self, 'video_merger') and self.video_merger:
                    stats = self.video_merger.get_stats()
                    buffer_size = len(self.video_merger.video_buffer)
                    batch_size = self.var_merge_batch_size.get()
                    self.lbl_merger_stats_i2v.config(text=f"Merger: {stats['total']} batches | {stats['completed']} merged | {stats['pending']} pending | Buffer: {buffer_size}/{batch_size}")
                self.master.after(2000, update_merger_stats_i2v)
            left_canvas()
            ttk.Separator(settings_frame, orient='horizontal').grid(row=17, column=0, sticky='ew', pady=10)
            ttk.Checkbutton(settings_frame, text='⚡ Enable Concurrent Mode (2 workers parallel)', variable=self.var_enable_concurrent, command=self._on_concurrent_toggle).grid(row=18, column=0, sticky='w', pady=5)
            self.lbl_concurrent_info = ttk.Label(settings_frame, text='✅ Faster but needs more CPU/RAM', foreground='green', font=('Arial', 8))
            self.lbl_concurrent_info.grid(row=19, column=0, sticky='w', pady=(0, 5))
            if not hasattr(self, 'draft_action'):
                self.draft_action = tk.StringVar(value='delete')
            ttk.Radiobutton(settings_frame, text=self.lang.get('delete_draft_default'), variable=self.draft_action, value='delete').grid(row=5, column=0, sticky='w', pady=2)
            ttk.Radiobutton(settings_frame, text=self.lang.get('post_public'), variable=self.draft_action, value='post').grid(row=6, column=0, sticky='w', pady=2)
            ttk.Label(settings_frame, text=f"{self.lang.get('both_remove_draft')}\n{self.lang.get('post_requires_token')}", font=('Arial', 8), foreground='gray', wraplength=280, justify='left').grid(row=7, column=0, sticky='w', pady=(5, 0))
            settings_frame.columnconfigure(0, weight=1)
            settings_frame.columnconfigure(0, weight=1)
            prompt_frame = ttk.LabelFrame(left_panel, text=self.lang.get('prompts_title'), padding=10)
            prompt_frame.pack(fill='both', expand=True, pady=(0, 8))
            import_row = ttk.Frame(prompt_frame)
            import_row.pack(fill='x', pady=(0, 5))
            ttk.Button(import_row, text=self.lang.get('import_txt'), command=self.import_to_queue).pack(side='left', padx=2)
            ttk.Button(import_row, text=self.lang.get('import_excel'), command=self.import_to_queue).pack(side='left', padx=2)
            ttk.Label(prompt_frame, text=self.lang.get('enter_prompt'), font=('Segoe UI', 9)).pack(anchor='w', pady=(0, 3))
            self.txt_prompt = ScrolledText(prompt_frame, height=8, wrap=tk.WORD, font=('Segoe UI', 10))
            self.txt_prompt.pack(fill='both', expand=True, pady=(0, 10))
            ctrl_frame = ttk.Frame(prompt_frame)
            ctrl_frame.pack(fill='x')
            ttk.Button(ctrl_frame, text=self.lang.get('add_to_queue'), command=self.add_prompt_to_queue, width=18).pack(side='left', padx=2)
            self.btn_start_gen = ttk.Button(ctrl_frame, text=self.lang.get('start_gen'), command=self.start_generation, width=18, style='Accent.TButton')
            self.btn_start_gen.pack(side='left', padx=2)
            self.btn_stop_gen = ttk.Button(ctrl_frame, text=self.lang.get('stop'), command=self.stop_generation_process, width=10, state='disabled')
            self.btn_stop_gen.pack(side='left', padx=2)
            right_panel = ttk.Frame(main_frame)
            right_panel.pack(side='right', fill='both', expand=True)
            table_controls = ttk.Frame(right_panel)
            table_controls.pack(fill='x', pady=(0, 5))
            ttk.Button(table_controls, text=self.lang.get('select_all'), command=self.select_all_prompts, width=12).pack(side='left', padx=2)
            ttk.Button(table_controls, text=self.lang.get('deselect_all'), command=self.deselect_all_prompts, width=12).pack(side='left', padx=2)
            ttk.Button(table_controls, text=self.lang.get('delete_selected'), command=self.table_delete_selected, width=15).pack(side='left', padx=2)
            ttk.Button(table_controls, text=self.lang.get('clear_all'), command=self.clear_queue, width=12).pack(side='left', padx=2)
            table_container = ttk.Frame(right_panel)
            table_container.pack(fill='both', expand=True, pady=(0, 8))
            self.table_canvas = tk.Canvas(table_container, bg='#E3F2FD', highlightthickness=1)
            scrollbar_y = ttk.Scrollbar(table_container, orient='vertical', command=self.table_canvas.yview)
            scrollbar_x = ttk.Scrollbar(table_container, orient='horizontal', command=self.table_canvas.xview)
            self.table_canvas.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            scrollbar_y.pack(side='right', fill='y')
            scrollbar_x.pack(side='bottom', fill='x')
            self.table_canvas.pack(side='left', fill='both', expand=True)
            self.table_inner_frame = ttk.Frame(self.table_canvas)
            self.table_canvas_window = self.table_canvas.create_window((0, 0), window=self.table_inner_frame, anchor='nw')

            def configure_canvas(event):
                self.table_canvas.configure(scrollregion=self.table_canvas.bbox('all'))
                self.table_canvas.itemconfig(self.table_canvas_window, width=event.width)
            self.table_canvas.bind('<Configure>', configure_canvas)
            self.table_inner_frame.bind('<Configure>', lambda e: self.table_canvas.configure(scrollregion=self.table_canvas.bbox('all')))
            self.table_canvas.bind('<MouseWheel>', lambda e: self.table_canvas.yview_scroll(int((-1) * (e.delta / 120)), 'units'))
            header = ttk.Frame(self.table_inner_frame, relief='raised', borderwidth=1)
            header.pack(fill='x', pady=(0, 2))
            header.columnconfigure(3, weight=1)
            ttk.Label(header, text='[ ]', width=3, anchor='center', font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, padx=5, pady=8, sticky='w')
            ttk.Label(header, text=self.lang.get('no_dot'), width=5, anchor='center', font=('Segoe UI', 9, 'bold')).grid(row=0, column=1, padx=5, pady=8, sticky='w')
            ttk.Label(header, text=self.lang.get('ref_image'), width=12, anchor='center', font=('Segoe UI', 9, 'bold')).grid(row=0, column=2, padx=5, pady=8, sticky='w')
            ttk.Label(header, text=self.lang.get('prompt'), anchor='w', font=('Segoe UI', 9, 'bold')).grid(row=0, column=3, padx=10, pady=8, sticky='ew')
            ttk.Label(header, text=self.lang.get('status'), anchor='center', font=('Segoe UI', 9, 'bold')).grid(row=0, column=4, padx=5, pady=8, sticky='e')
            ttk.Label(header, text=self.lang.get('video_preview'), anchor='center', font=('Segoe UI', 9, 'bold')).grid(row=0, column=5, padx=5, pady=8, sticky='e')
            ttk.Label(header, text=self.lang.get('actions'), width=10, anchor='center', font=('Segoe UI', 9, 'bold')).grid(row=0, column=6, padx=5, pady=8, sticky='e')
            log_frame = ttk.LabelFrame(right_panel, text=self.lang.get('gen_log'), padding=10)
            log_frame.pack(fill='x')
            self.log_text = ScrolledText(log_frame, height=6, font=('Consolas', 9))
            self.log_text.pack(fill='both', expand=True)
            self.log_text.tag_config('ok', foreground='green')
            self.log_text.tag_config('err', foreground='red')
            self.log_text.tag_config('info', foreground='blue')
            self.log_text.tag_config('warn', foreground='orange')

        def add_images(self):
            """Add images for generation"""  # inserted
            filepaths = filedialog.askopenfilenames(title='Select Reference Images', filetypes=[('Images', '*.jpg;*.jpeg;*.png;*.webp'), ('All Files', '*.*')])
            if not filepaths:
                pass  # postinserted
            return None

        def get_image_paths(self):
            """Get image paths and copy to clipboard for Excel - FIXED"""  # inserted
            try:
                paths = filedialog.askopenfilenames(title='Select Images for Excel', filetypes=[('Images', '*.jpg;*.jpeg;*.png;*.webp'), ('All Files', '*.*')])
                if not paths:
                    pass  # postinserted
                return None
            except Exception as e:
                logger.error(f'Get image paths error: {e}', exc_info=True)
                messagebox.showerror('Error', f'Failed to get image paths:\n\n{str(e)[:200]}')

        def clear_images(self):
            """Clear all uploaded images"""  # inserted
            if not self.uploaded_images:
                AutoCloseMessageBox.showinfo('Info', 'No images to clear.')
            return None

        def add_image_to_list(self, image_path: str):
            """Add image from Character Manager to I2V"""  # inserted
            try:
                if not os.path.exists(image_path):
                    pass  # postinserted
                return False
            except Exception as e:
                logger.error(f'Add image failed: {e}')
                return False

        def table_refresh_stt(self):
            """Refresh row numbers (STT) after deletion"""  # inserted
            for i, prompt_data in enumerate(self.prompts, 1):
                prompt_data['stt'] = i
                row_frame = prompt_data.get('row_frame')
                if row_frame and row_frame.winfo_exists():
                    pass  # postinserted
                else:  # inserted
                    for widget in row_frame.winfo_children():
                        if isinstance(widget, ttk.Label):
                            pass  # postinserted
                        else:  # inserted
                            grid_info = widget.grid_info()
                            if grid_info and grid_info.get('column') == 1:
                                pass  # postinserted
                            else:  # inserted
                                widget.config(text=str(i))
                                break

        def update_image_count(self):
            """Update image count label"""  # inserted
            if hasattr(self, 'lbl_image_count') and self.lbl_image_count.winfo_exists():
                count = len(self.uploaded_images)
                self.lbl_image_count.config(text=f'📊 Images: {count}')
                return None

        def add_prompt_to_queue(self):
            """Add prompt(s) to generation queue - FIXED TO USE EXCEL/JSON DATA"""  # inserted
            text = self.txt_prompt.get('1.0', 'end').strip()
            prompts_in_text = [p.strip() for p in text.split('\n') if p.strip()]
            if not prompts_in_text:
                AutoCloseMessageBox.showwarning(self.lang.get('warning'), f"{self.lang.get('no_prompts')}\n\n{self.lang.get('please_add')}\n{self.lang.get('type_manually')}\n{self.lang.get('import_from')}")
            return None

        def select_all_prompts(self):
            """Select all prompts in queue"""  # inserted
            for prompt_data in self.prompts:
                if 'checkbox_var' in prompt_data:
                    pass  # postinserted
                else:  # inserted
                    prompt_data['checkbox_var'].set(True)
                    prompt_data['selected'] = True
            self.log('Selected all prompts', 'info')

        def deselect_all_prompts(self):
            """Deselect all prompts in queue"""  # inserted
            for prompt_data in self.prompts:
                if 'checkbox_var' in prompt_data:
                    pass  # postinserted
                else:  # inserted
                    prompt_data['checkbox_var'].set(False)
                    prompt_data['selected'] = False
            self.log('Deselected all prompts', 'info')

        def clear_queue(self):
            """Clear generation queue"""  # inserted
            if not self.prompts:
                AutoCloseMessageBox.showinfo('Info', 'Queue is empty.')
            return None

        def table_add_row(self, prompt_data):
            """Add row to generation table"""  # inserted
            stt = len(self.prompts) + 1
            row_id = f'row_{stt}_{int(time.time() * 1000)}'
            prompt_data['row_id'] = row_id
            prompt_data['index'] = len(self.prompts)
            row_frame = ttk.Frame(self.table_inner_frame, relief='solid', borderwidth=1)
            row_frame.columnconfigure(3, weight=1)
            row_frame.pack(fill='x', padx=2, pady=2)
            prompt_data['checkbox_var'] = tk.BooleanVar(value=True)
            prompt_data['selected'] = True
            chk = ttk.Checkbutton(row_frame, variable=prompt_data['checkbox_var'], command=lambda pd=prompt_data: self.on_checkbox_changed(pd))
            chk.grid(row=0, column=0, padx=5, pady=8)
            ttk.Label(row_frame, text=str(stt), anchor='center').grid(row=0, column=1, padx=5, pady=8)
            ref_img_frame = ttk.Frame(row_frame, width=80, height=90, relief='sunken', borderwidth=1)
            ref_img_frame.grid(row=0, column=2, padx=5, pady=5)
            ref_img_frame.grid_propagate(False)
            image_path = prompt_data.get('image_path') or ''
            image_path = str(image_path).strip() if image_path else image_path
            has_valid_image = bool(image_path) and os.path.exists(image_path)
            if has_valid_image:
                self.log(f'  [ROW {stt}] Loading image: {image_path}', 'info')
                self.log(f'  [ROW {stt}] Checking PIL...', 'info')
                pass
                try:
                    from PIL import Image, ImageTk
                    self.log(f'  [ROW {stt}] PIL OK', 'ok')
                    image_path = prompt_data['image_path']
                    temp_ref_path = image_path + '_ref_thumb.jpg'
                    if not os.path.exists(temp_ref_path):
                        self.log(f'  [ROW {stt}] Creating thumbnail...', 'info')
                        if not resize_reference_image(image_path, temp_ref_path, prompt_data.get('orientation', 'landscape')):
                            raise Exception('Failed to create thumbnail')
                    self.log(f'  [ROW {stt}] Opening: {temp_ref_path}', 'info')
                    img = Image.open(temp_ref_path)
                    self.log(f'  [ROW {stt}] Creating PhotoImage...', 'info')
                    photo = ImageTk.PhotoImage(img)
                    self.log(f'  [ROW {stt}] Saving reference...', 'info')
                    prompt_data['ref_image_photo'] = photo
                    self.log(f'  [ROW {stt}] Displaying...', 'info')
                    thumb_label = ttk.Label(ref_img_frame, image=photo, cursor='hand2')
                    thumb_label.place(relx=0.5, rely=0.5, anchor='center')
                    thumb_label.bind('<Button-1>', lambda e, p=image_path: ImagePreviewDialog(self.master, p))
                    self.log(f'  [ROW {stt}] ✅ Image displayed successfully', 'ok')
                    prompt_data['ref_img_frame'] = ref_img_frame
                    prompt_short = prompt_data['prompt'][:60] + '...' if len(prompt_data['prompt']) > 60 else prompt_data['prompt']
                    ttk.Label(row_frame, text=prompt_short, anchor='w').grid(row=0, column=3, padx=10, pady=8, sticky='ew')
                    status_color = {'Success': 'green', 'Failed': 'red', 'Pending': 'orange', 'Processing': 'blue'}.get(prompt_data['status'], 'gray')
                    status_label = ttk.Label(row_frame, text=prompt_data['status'], anchor='center', foreground=status_color)
                    status_label.grid(row=0, column=4, padx=5, pady=8, sticky='e')
                    prompt_data['status_label'] = status_label
                    preview_frame = ttk.Frame(row_frame, width=165, height=95, relief='sunken', borderwidth=1)
                    preview_frame.grid(row=0, column=5, padx=5, pady=5, sticky='e')
                    preview_frame.grid_propagate(False)
                    ttk.Label(preview_frame, text='Pending', foreground='gray', font=('Segoe UI', 8)).place(relx=0.5, rely=0.5, anchor='center')
                    prompt_data['preview_frame'] = preview_frame
                    action_frame = ttk.Frame(row_frame)
                    action_frame.grid(row=0, column=6, padx=5, pady=5, sticky='e')
                    prompt_data['action_frame'] = action_frame
                    prompt_data['row_frame'] = row_frame
                    prompt_data['stt'] = stt
                    self.prompts.append(prompt_data)
                except Exception as e:
                    logger.error(f'Reference image load error: {e}')
                    ttk.Label(ref_img_frame, text='Error', foreground='red', font=('Segoe UI', 8)).place(relx=0.5, rely=0.5, anchor='center')

        def change_reference_image(self, prompt_data, ref_img_frame):
            """Change reference image - FIXED VERSION"""  # inserted
            new_image_path = filedialog.askopenfilename(title='Select New Reference Image', filetypes=[('Images', '*.jpg;*.jpeg;*.png;*.webp'), ('All', '*.*')])
            if not new_image_path:
                pass  # postinserted
            return None

        def add_reference_image(self, prompt_data, ref_img_frame):
            """Add reference image to prompt that has none - FIXED VERSION"""  # inserted
            new_image_path = filedialog.askopenfilename(title='Select Reference Image', filetypes=[('Images', '*.jpg;*.jpeg;*.png;*.webp'), ('All', '*.*')])
            if not new_image_path:
                pass  # postinserted
            return None

        def table_update_video_preview(self, prompt_data, video_data):
            """Update video preview slot"""  # inserted
            preview_frame = prompt_data.get('preview_frame')
            if preview_frame and (not preview_frame.winfo_exists()):
                pass  # postinserted
            return None

        def add_regen_button(self, prompt_data):
            """Add regenerate button"""  # inserted
            action_frame = prompt_data.get('action_frame')
            if action_frame and (not action_frame.winfo_exists()):
                pass  # postinserted
            return None

        def regenerate_video(self, prompt_data):
            """Regenerate video"""  # inserted
            dialog = RegenDialog(self.master, prompt_data)
            dialog.wait_window()
            if dialog.result:
                prompt_data['prompt'] = dialog.result['prompt']
                prompt_data['orientation'] = dialog.result['orientation']
                prompt_data['duration'] = dialog.result.get('duration', '10s')
                prompt_data['status'] = 'Pending'
            prompt_data['status_label'].config(text='Pending', foreground='orange') if 'status_label' in prompt_data and prompt_data['status_label'].winfo_exists() else prompt_data['status_label']
            preview_frame = prompt_data.get('preview_frame')
            if preview_frame and preview_frame.winfo_exists():
                for w in preview_frame.winfo_children():
                    w.destroy()
                ttk.Label(preview_frame, text='Pending', foreground='gray', font=('Segoe UI', 8)).place(relx=0.5, rely=0.5, anchor='center')
            self.log(f"Video marked for regeneration: {prompt_data['prompt'][:50]}...", 'info')
            AutoCloseMessageBox.showinfo('Queued', 'Video marked for regeneration.\n\nStart generation to process.')

        def on_checkbox_changed(self, prompt_data):
            """Handle checkbox change"""  # inserted
            prompt_data['selected'] = prompt_data['checkbox_var'].get()

        def open_video_file(self, path):
            """Open video file"""  # inserted
            if not os.path.exists(path):
                messagebox.showerror('Error', f'File not found:\n{path}')
            return None

        def stop_generation_process(self):
            """Stop generation process"""  # inserted
            if AutoCloseMessageBox.askyesno('Confirm', 'Stop generation process?\n\nCurrent video will complete.'):
                self.stop_generation = True
                self.log('[GENERATION] ⚠️ Stop requested', 'warn')
            return None

        def start_generation(self):
            """\nStart generation - With Concurrent Toggle\n"""  # inserted
            if self.is_generating:
                messagebox.showwarning('In Progress', 'Already running!')
            return None

        def _generation_thread_api(self, selected_prompts):
            """\nBackground thread for API-based generation\n\n✅ 100% API - No browser needed\n✅ Auto-upload images with curl_cffi\n✅ Auto-switch profiles when quota exhausted\n"""  # inserted
            try:
                self.log('============================================================', 'info')
                self.log(f'[API] Starting batch: {len(selected_prompts)} videos', 'info')
                self.log('============================================================', 'info')
                selected_prompts = 0
                self = 0
                for i, prompt_data in enumerate(selected_prompts, 1):
                    if self.stop_generation:
                        self.log('[API] ⚠️ Stopped by user', 'warn')
                        break
                self.log('\n============================================================', 'info')
                self.log('[API] 🎉 Batch Complete!', 'ok')
                self.log(f'  ✅ Success: {selected_prompts}', 'ok')
                self.log(f'  ❌ Failed: {self}', 'err')
                self.log(f'  Total processed: {selected_prompts + self}/{len(selected_prompts)}', 'info')
                self.log('============================================================', 'info')
                self.schedule_gui_update(lambda: AutoCloseMessageBox.showinfo('Generation Complete', f'🎉 Batch finished!\n\n✅ Success: {success_count}/{len(selected_prompts)}\n❌ Failed: {fail_count}/{len(selected_prompts)}\n\nTotal videos processed: {success_count + fail_count}'))
                self.is_generating = False
                self.schedule_gui_update(lambda: self.btn_start_gen.config(state='normal'))
                self.schedule_gui_update(lambda: self.btn_stop_gen.config(state='disabled'))
            except Exception as e:
                logger.error(f'API generation thread error: {e}', exc_info=True)
                self.log(f'[API] ❌ FATAL: {str(e)[:200]}', 'err')

        def start_runtime_protection(self):
            """\nEnhanced Runtime Protection v2.0\n\n🛡️ SECURITY FEATURES:\n- Random check intervals (3-7 min)\n- File integrity monitoring\n- Anti-debug detection\n- Exception recovery\n- Memory obfuscation\n"""  # inserted
            import random
            import hashlib as detect_debugger
            from pathlib import Path
            hashlib = Path('sora_license.dat')
            self._license_hash = detect_debugger.sha256(hashlib.read_bytes()).hexdigest() if hashlib.exists() else None

            def detect_debugger():
                """Anti-debug check"""  # inserted
                import sys
                if sys.gettrace() is not None:
                    pass  # postinserted
                return True

            def check_file_integrity():
                """Check license file not tampered"""  # inserted
                if not license_path.exists():
                    pass  # postinserted
                return False

            def check_protection():
                try:
                    if LICENSE_ENABLED:
                        import random
                        if detect_debugger():
                            logger.critical('[PROTECTION] Security violation')
                            error_code = random.randint(4096, 65535)
                            messagebox.showerror('Error', f'Security check failed.\n\nError: 0x{error_code:04X}\n\nContact: Zalo 0789.535.888')
                            self.master.destroy()
                        return None
                except Exception as e:
                    logger.critical('[PROTECTION] Fatal security error')
                    messagebox.showerror('Security Error', 'Critical security error.\n\nApplication will close.')
                    self.master.destroy()
            first_check = random.randint(120000, 300000)
            logger.info('[PROTECTION] 🛡️ Runtime monitor started')
            self.master.after(first_check, check_file_integrity)

        def generate_single_video_api(self, prompt_data) -> bool:
            """\nGenerate video 100% via API - NO BROWSER!\n\n✅ Uses SoraAPIClient from sora_api_client_full.py\n✅ Auto-uploads images with curl_cffi bypass\n✅ Handles watermark-free download if enabled\n\nArgs:\n    prompt_data: Prompt data dict\n    \nReturns:\n    bool: True if success\n"""  # inserted
            try:
                if not self.api_manager or not self.api_manager.is_ready():
                    self.log('❌ API Manager not ready', 'err')
                return False
            except Exception as e:
                logger.error(f'API generate error: {e}', exc_info=True)
                self.log(f'[API] ❌ Error: {str(e)[:100]}', 'err')
                return False

        def get_latest_post_id(self, bearer_token):
            """
            Call API để lấy post_id của post mới nhất

            Returns:
                post_id (str) hoặc None
            """
            try:

                url = 'https://sora.chatgpt.com/backend/project_y/posts/search'
                headers = {
                    'accept': '*/*',
                    'authorization': f'Bearer {bearer_token}',
                    'content-type': 'application/json',
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                payload = {'limit': 1, 'sort': 'recent'}

                self.log('[API] 🌐 Calling posts API...', 'info')

                response = curl_requests.post(
                    url, json=payload, headers=headers, timeout=10, impersonate='chrome136'
                )

                if response.status_code == 200:
                    data = response.json()
                    posts = data.get('posts', [])

                    if posts:
                        latest_post = posts[0]
                        post_id = latest_post.get('id')

                        if post_id:
                            self.log(f'[API] ✅ Got latest post ID: {post_id}', 'ok')

                            match post_id:
                                case _:
                                    pass  # postinserted

                            return post_id

                    return None

                return None

            except Exception as e:
                self.log(f'[API] ❌ Exception: {str(e)[:100]}', 'err')
                return None


        def generate_single_video_draft_handling(self, prompt_data, video_path, draft_id, generation_id):
            """\nHandle draft action after video download - FIXED INTERCEPTOR TIMING\n\n✅ FIX CRITICAL: Inject interceptor TRƯỚC KHI navigate to draft page\n\nArgs:\n    prompt_data: Prompt data dict\n    video_path: Downloaded video file path\n    draft_id: Draft ID (for DELETE)\n    generation_id: Generation ID (for POST)\n\nReturns:\n    bool: True if action successful\n"""  # inserted
            try:
                draft_action = self.draft_action.get()
                self.log('============================================================', 'info')
                self.log(f'[DRAFT] Action: {draft_action.upper()}', 'info')
                self.log('============================================================', 'info')
                if draft_action == 'post':
                    self.log('[DRAFT] 📤 Posting video to public...', 'info')
                    if not generation_id:
                        self.log('[DRAFT] ⚠️ No generation_id, cannot POST', 'warn')
                        self.log('[DRAFT] 💡 Falling back to DELETE', 'info')
                        if draft_id and self.current_profile:
                            profile_name = self.current_profile.profile_name
                            bearer_token = self.get_token_for_profile(profile_name)
                            return self.browser.delete_draft_by_id(draft_id, bearer_token, callback=self.log) if bearer_token else self.log('[DELETE] ❌ No token available', 'err')
                        return False
                    return False
                return False
            except Exception as e:
                logger.error(f'[DRAFT] ❌ Exception: {e}', exc_info=True)
                self.log(f'[DRAFT] ❌ Error: {str(e)[:200]}', 'err')
                return False

        def log(self, message: str, tag=None):
            """Thread-safe logging"""  # inserted

            def _log():
                try:
                    if not hasattr(self, 'log_text') or self.log_text is None:
                        print(f"[{time.strftime('%H:%M:%S')}] {message}")
                    return None
                except Exception as e:
                    logger.error(f'Log error: {e}')
            if threading.current_thread() == threading.main_thread():
                _log()
            return None

        def schedule_gui_update(self, callback):
            """Schedule GUI update from background thread"""  # inserted
            self._gui_queue.put(callback)

        def load_config(self) -> dict:
            """Load configuration"""
            if CONFIG_PATH.exists():
                try:
                    with open(CONFIG_PATH, 'r') as f:
                        return json.load(f)
                except Exception:
                    pass

            return {'headless': False, 'download_dir': './downloads'}


        def save_config(self):
            """Save configuration"""  # inserted
            config = {'headless': self.var_headless.get(), 'download_dir': self.var_download_dir.get()}
            try:
                with open(CONFIG_PATH, 'w') as f:
                    json.dump(config, f, indent=2)
            except Exception as e:
                logger.error(f'Save config error: {e}')

        def browse_download_dir(self):
            """Browse and select download directory"""  # inserted
            directory = filedialog.askdirectory(title='Select Download Directory', initialdir=self.var_download_dir.get())
            if directory:
                self.var_download_dir.set(directory)
                self.log(f'Download directory changed to: {directory}', 'info')
                self.save_config()
            return None

        def toggle_wf_download(self):
            """Toggle watermark-free download feature"""  # inserted
            if self.var_enable_wf_download.get():
                if self.draft_action.get() == 'delete':
                    AutoCloseMessageBox.showwarning('POST Mode Required', '⚠️ Watermark-free download requires POST mode!\n\nPlease select \'POST to Public\' in Draft Action.')
                    self.var_enable_wf_download.set(False)
                return None
            return None

        def validate_all_profile_tokens(self) -> dict:
            """Validate tokens cho tất cả profiles"""  # inserted
            results = {}
            stats = self.profile_manager.get_profile_stats()
            all_profiles = ['Default'] + [p['name'] for p in stats['profiles']]
            for profile_name in all_profiles:
                token = self.token_manager.get_token(profile_name)
                results[profile_name] = bool(token and len(token) > 50)
            return results

        def show_token_validation_report(self):
            """Show validation report dialog"""  # inserted
            from tkinter import messagebox
            validation = self.validate_all_profile_tokens()
            valid_count = sum((1 for v in validation.values() if v))
            invalid_count = len(validation) - valid_count
            report = 'TOKEN VALIDATION REPORT\n'
            report += '============================================================\n\n'
            report += f'Total profiles: {len(validation)}\n'
            report += f'✅ Valid tokens: {valid_count}\n'
            report += f'❌ Missing/Invalid: {invalid_count}\n\n'
            if invalid_count > 0:
                report += 'Profiles WITHOUT valid tokens:\n'
                for profile_name, is_valid in validation.items():
                    if not is_valid:
                        pass  # postinserted
                    else:  # inserted
                        report += f'  ❌ {profile_name}\n'
                report += '\n⚠️ These profiles CANNOT generate videos!'
            AutoCloseMessageBox.showinfo('Token Validation', report)

        def update_browser_status(self, status, color='gray'):
            """Update browser status label"""  # inserted
            if hasattr(self, 'lbl_browser_status') and self.lbl_browser_status.winfo_exists():
                self.lbl_browser_status.config(text=f'Browser: {status}', foreground=color)
                return None
            return None

        def update_login_status(self, status, color='gray'):
            """Update login status label"""  # inserted
            if hasattr(self, 'lbl_login_status') and self.lbl_login_status.winfo_exists():
                self.lbl_login_status.config(text=status, foreground=color)
                return None

        def on_closing(self):
            """Handle window closing"""  # inserted
            if self.is_generating and (not AutoCloseMessageBox.askyesno('Exit', '⚠️ Generation in progress!\n\nExit anyway?')):
                pass  # postinserted
            return None

        def _get_available_profile_for_generation(self, duration: int=10):
            """\nLấy profile khả dụng cho generation - TỰ ĐỘNG SWITCH khi hết quota\n\nArgs:\n    duration: Video duration để tính credits cần (10 hoặc 15)\n    \nReturns:\n    ProfileInfo nếu có, None nếu hết\n"""  # inserted
            from profile_manager import calculate_credits
            credits_needed = calculate_credits(duration)
            if self.current_profile and self.current_profile.can_generate(credits_needed):
                logger.info(f'[PROFILE] Using current: {self.current_profile.profile_name} ({self.current_profile.remaining_credits()} credits left)')

        def _after_video_generated_success(self, duration: int=10):
            """\nGọi SAU KHI generate video thành công\nCập nhật usage counter cho profile\n\nArgs:\n    duration: Video duration để tính credits (10 hoặc 15)\n"""  # inserted
            from profile_manager import calculate_credits
            if not self.current_profile:
                logger.warning('[PROFILE] No current profile to update')
            return None

        def _get_time_until_reset(self):
            """Helper: Thời gian đến khi reset quota (00:00 hôm sau)"""  # inserted
            from datetime import datetime, timedelta
            now = datetime.now()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            delta = tomorrow - now
            hours = delta.seconds // 3600
            minutes = delta.seconds % 3600 // 60
            return f'{hours}h {minutes}m'

        def process_gui_queue(self):
            """Process GUI update queue"""  # inserted
            try:
                    pass
                    callback = self._gui_queue.get_nowait()
                    callback()
            except queue.Empty:
                pass
            self.master.after(100, self.process_gui_queue)

        def table_select_all(self):
            """Select all prompts"""  # inserted
            for prompt_data in self.prompts:
                if 'checkbox_var' in prompt_data:
                    pass  # postinserted
                else:  # inserted
                    prompt_data['checkbox_var'].set(True)
                    prompt_data['selected'] = True
            self.log('Selected all prompts', 'info')

        def table_deselect_all(self):
            """Deselect all prompts"""  # inserted
            for prompt_data in self.prompts:
                if 'checkbox_var' in prompt_data:
                    pass  # postinserted
                else:  # inserted
                    prompt_data['checkbox_var'].set(False)
                    prompt_data['selected'] = False
            self.log('Deselected all prompts', 'info')

        def table_delete_selected(self):
            """Delete selected prompts"""  # inserted
            selected = [p for p in self.prompts if p.get('selected', False)]
            if not selected:
                AutoCloseMessageBox.showinfo('Info', 'ℹ️ No prompts selected')
            return None

        def table_delete_prompt_row(self, prompt_data, confirm=True):
            """Delete a single prompt row"""  # inserted
            if confirm and (not AutoCloseMessageBox.askyesno('Confirm', 'Delete this prompt?')):
                pass  # postinserted
            return None

        def table_clear_all(self):
            """Clear all prompts"""  # inserted
            if not self.prompts:
                AutoCloseMessageBox.showinfo('Info', 'Queue is empty.')
            return None

        def import_prompts_txt(self):
            """Import prompts from TXT file - CHỈ HIỂN THỊ TRONG TEXT AREA"""  # inserted
            filepath = filedialog.askopenfilename(title='Select TXT File', filetypes=[('Text Files', '*.txt'), ('All Files', '*.*')])
            if not filepath:
                pass  # postinserted
            return None

        def import_prompts_excel(self):
            """Import prompts from Excel file - CHỈ HIỂN THỊ TRONG TEXT AREA"""  # inserted
            filepath = filedialog.askopenfilename(title='Select Excel File', filetypes=[('Excel Files', '*.xlsx;*.xls'), ('All Files', '*.*')])
            if not filepath:
                pass  # postinserted
            return None

        def convert_video_script_to_prompt(self, script_data: dict) -> str:
            """\nConvert complex video script JSON to single Sora prompt\n\nArgs:\n    script_data: Dict from JSON with video script structure\n\nReturns:\n    Combined prompt string for Sora\n"""  # inserted
            try:
                prompt_parts = []
                if 'brand' in script_data:
                    prompt_parts.append(f"Brand: {script_data['brand']}")
                prompt_parts.append(f"Title: {script_data['ad_title']}") if 'ad_title' in script_data else prompt_parts.append(f"<mask_5>{script_data['ad_title']}")
                if '1_Style_Mood_Theme' in script_data:
                    smt = script_data['1_Style_Mood_Theme']
                    prompt_parts.append(f"Style: {smt['style']}") if 'style' in smt else prompt_parts.append(f"<mask_5>{smt['style']}")
                    prompt_parts.append(f"Mood: {smt['mood']}") if 'mood' in smt else prompt_parts.append(f"<mask_5>{smt['mood']}")
                    if 'theme' in smt:
                        prompt_parts.append(f"Theme: {smt['theme']}")
                if '2_Camera_Lighting_ColorTone' in script_data:
                    clc = script_data['2_Camera_Lighting_ColorTone']
                    if 'camera' in clc:
                        prompt_parts.append(f"Camera: {clc['camera']}")
                    if 'lighting' in clc:
                        prompt_parts.append(f"Lighting: {clc['lighting']}")
                    if 'color_tone' in clc:
                        prompt_parts.append(f"Color: {clc['color_tone']}")
                if '3_Character_Details' in script_data:
                    chars = script_data['3_Character_Details']
                    if 'primary_character' in chars:
                        pc = chars['primary_character']
                        char_desc = f"Primary character: {pc.get('gender', 'Person')}, {pc.get('age', 'adult')}"
                        if 'attire' in pc:
                            char_desc += f", wearing {pc['attire']}"
                        if 'expression' in pc:
                            char_desc += f", {pc['expression']}"
                        prompt_parts.append(char_desc)
                    if 'secondary_character' in chars:
                        sc = chars['secondary_character']
                        char_desc = f"Secondary character: {sc.get('gender', 'Person')}, {sc.get('age', 'adult')}"
                        if 'attire' in sc:
                            char_desc += f", wearing {sc['attire']}"
                        if 'expression' in sc:
                            char_desc += f", {sc['expression']}"
                        prompt_parts.append(char_desc)
                if '4_Setting_Environment_TimeOfDay' in script_data:
                    env = script_data['4_Setting_Environment_TimeOfDay']
                    if 'location' in env:
                        prompt_parts.append(f"Location: {env['location']}")
                    if 'environment_details' in env:
                        prompt_parts.append(f"Environment: {env['environment_details']}")
                    if 'time_of_day' in env:
                        prompt_parts.append(f"Time: {env['time_of_day']}")
                if '5_Action_Scene_Breakdown' in script_data:
                    scenes = script_data['5_Action_Scene_Breakdown']
                    if isinstance(scenes, list) and scenes:
                        scene_descriptions = []
                        for scene in scenes:
                            if 'scene' in scene:
                                pass  # postinserted
                            else:  # inserted
                                time_marker = scene.get('time', '')
                                scene_desc = f"[{time_marker}] {scene['scene']}" if time_marker else scene['scene']
                                scene_descriptions.append(scene_desc)
                        else:  # inserted
                            prompt_parts.append('Action sequence: ' + ' → '.join(scene_descriptions)) if scene_descriptions else prompt_parts.append('Action sequence: ' + ' → '.join(scene_descriptions))
                if '6_Dialogues' in script_data:
                    dialogues = script_data['6_Dialogues']
                    vo_parts = []
                    for key, value in dialogues.items():
                        if 'voiceover' in key.lower():
                            pass  # postinserted
                        else:  # inserted
                            vo_parts.append(value)
                    else:  # inserted
                        if vo_parts:
                            prompt_parts.append('Voiceover: ' + ' | '.join(vo_parts))
                if '7_Audio_Music_Tone' in script_data:
                    audio = script_data['7_Audio_Music_Tone']
                    if 'music' in audio:
                        prompt_parts.append(f"Music: {audio['music']}")
                    if 'sound_design' in audio:
                        prompt_parts.append(f"Sound: {audio['sound_design']}")
                if '8_Ending_Shot_LogoReveal' in script_data:
                    ending = script_data['8_Ending_Shot_LogoReveal']
                    if 'visual' in ending:
                        prompt_parts.append(f"Ending: {ending['visual']}")
                    prompt_parts.append(f"Tagline: {ending['tagline']}") if 'tagline' in ending else prompt_parts.append(f"<mask_5>{ending['tagline']}")
                final_prompt = '. '.join(prompt_parts)
                return final_prompt
            except Exception as e:
                logger.error(f'Convert script error: {e}', exc_info=True)
                return ''

        def import_prompts_json_advanced(self):
            """\nImport prompts from JSON file - FIXED VERSION\n✅ Fixes:\n- Correct field mapping (orientation vs image_path)\n- Auto-load thumbnail preview\n- Add change image button\n"""  # inserted
            filepath = filedialog.askopenfilename(title='Select JSON File', filetypes=[('JSON Files', '*.json'), ('All Files', '*.*')])
            if not filepath:
                pass  # postinserted
            return None

        def import_to_queue(self):
            """Show import options dialog"""  # inserted
            self = tk.Toplevel(self.master)
            self.title('Import Prompts')
            self.geometry('450x300')
            self.transient(self.master)
            self.grab_set()
            self.update_idletasks()
            x = self.winfo_screenwidth() // 2 - self.winfo_width() // 2
            y = self.winfo_screenheight() // 2 - self.winfo_height() // 2
            self.geometry(f'+{x}+{y}')
            main_frame = ttk.Frame(self, padding=20)
            main_frame.pack(fill='both', expand=True)
            ttk.Label(main_frame, text='Import prompts from file:', font=('Arial', 12, 'bold')).pack(pady=(0, 20))
            ttk.Button(main_frame, text='📄 Import from TXT', command=lambda: [self.import_prompts_txt(), dialog.destroy()], width=30).pack(pady=5)
            ttk.Button(main_frame, text='📊 Import from Excel', command=lambda: [self.import_prompts_excel(), dialog.destroy()], width=30).pack(pady=5)
            ttk.Button(main_frame, text='📋 Import from JSON (Advanced)', command=lambda: [self.import_prompts_json_advanced(), dialog.destroy()], width=30).pack(pady=5)
            info_text = 'ℹ️ Supported formats:\n• TXT: One prompt per line\n• Excel: Columns: Prompt | Orientation | Image\n• JSON: Simple prompts or Video Scripts'
            ttk.Label(main_frame, text=info_text, font=('Arial', 8), foreground='gray', justify='left').pack(pady=(15, 10))
            ttk.Button(main_frame, text='Cancel', command=self.destroy, width=30).pack(pady=(5, 0))

        def toggle_bearer_token(self):
            """Toggle bearer token visibility"""  # inserted
            if hasattr(self, 'txt_bearer'):
                current = self.txt_bearer.cget('show')
                self.txt_bearer.config(show='' if current == '*' else '*')
            return None

        def paste_bearer_token(self):
            """Paste bearer token from clipboard"""  # inserted
            try:
                token = self.master.clipboard_get()
                if hasattr(self, 'txt_bearer'):
                    self.txt_bearer.delete(0, 'end')
                    self.txt_bearer.insert(0, token)
                    self.log('Bearer token pasted', 'info')
                return None
            except Exception as e:
                messagebox.showerror('Error', f'Paste failed:\n{str(e)}')

        def save_bearer_token(self):
            """Save bearer token to config"""  # inserted
            if hasattr(self, 'txt_bearer'):
                token = self.txt_bearer.get().strip()
                if token:
                    self.config['bearer_token'] = token
                    self.save_config()
                    self.log('Bearer token saved', 'ok')
                    AutoCloseMessageBox.showinfo('Saved', 'Bearer token saved to config.')
                return None
            return None

        def clear_bearer_token(self):
            """Clear bearer token"""  # inserted
            if AutoCloseMessageBox.askyesno('Confirm', 'Clear bearer token?'):
                self.txt_bearer.delete(0, 'end') if hasattr(self, 'txt_bearer') else self.txt_bearer
                if 'bearer_token' in self.config:
                    del self.config['bearer_token']
                    self.save_config()
                self.log('Bearer token cleared', 'info')
            return None

        def toggle_video_merger(self):
            """Toggle video merger on/off - WITH LOGGING"""  # inserted
            if self.var_enable_merger.get():
                try:
                    batch_size = self.var_merge_batch_size.get()
                    self.log('============================================================', 'info')
                    self.log('[MERGER] 🎬 Initializing Video Merger...', 'info')
                    self.log(f'[MERGER]    Batch size: {batch_size} videos', 'info')
                    self.log('[MERGER]    Output: ./merged_videos', 'info')
                    self.log('============================================================', 'info')
                    if not hasattr(self, 'video_merger') or not self.video_merger:
                        from video_merger import VideoMerger
                        self.video_merger = VideoMerger(app_instance=self, output_folder='./merged_videos', batch_size=batch_size)
                        self.video_merger.start()
                        self.log('[MERGER] ✅ Video Merger started', 'ok')
                    if hasattr(self, 'lbl_merger_stats_i2v'):
                        self.lbl_merger_stats_i2v.config(text=f'Merger: ENABLED (batch={batch_size}) | Buffer: 0/{batch_size}', foreground='green')
                    return
                except Exception as e:
                    logger.error(f'Enable merger error: {e}', exc_info=True)
                    self.var_enable_merger.set(False)
                    self.log(f'[MERGER] ❌ Failed to enable: {str(e)[:200]}', 'err')
                    messagebox.showerror('Error', f'Failed to enable merger:\n\n{str(e)[:200]}')

        def enable_video_merger(self):
            """Enable video merger with current batch size"""  # inserted
            try:
                batch_size = self.var_merge_batch_size.get()
                if batch_size < 2:
                    messagebox.showwarning('Warning', 'Batch size must be at least 2')
                    self.var_enable_merger.set(False)
                return None
            except RuntimeError as e:
                logger.error(f'FFmpeg error: {e}', exc_info=True)
                messagebox.showerror('FFmpeg Error', str(e))
                self.var_enable_merger.set(False)
                self.video_merger = None
            except Exception as e:
                logger.error(f'Enable merger error: {e}', exc_info=True)
                messagebox.showerror('Error', f'Failed to enable merger: {str(e)[:200]}')
                self.var_enable_merger.set(False)
                self.video_merger = None

        def disable_video_merger(self):
            """Disable and stop video merger"""  # inserted
            if self.video_merger:
                self.video_merger.stop()
                self.video_merger = None
                self.log('Video Merger: DISABLED', 'warn')
            return None

        def update_merger_batch_size(self):
            """Update batch size if merger is running - WITH LOGGING"""  # inserted
            if self.video_merger and self.video_merger.is_running:
                new_size = self.var_merge_batch_size.get()
                old_size = self.video_merger.batch_size
                self.video_merger.set_batch_size(new_size)
                self.log(f'[MERGER] 🔧 Batch size updated: {old_size} → {new_size}', 'info')
                return None
            return None

        def add_video_to_merger(self, video_path: str):
            """Add a video to merger queue after watermark-free download"""  # inserted
            if self.video_merger and (not self.video_merger.is_running):
                pass  # postinserted
            return None

        def update_profile_combo(self):
            """Update profile dropdown"""  # inserted
            profiles = self.profile_manager.profiles
            if profiles:
                profile_names = [p.profile_name for p in profiles]
                self.combo_profile['values'] = profile_names
                if profile_names and (not self.var_selected_profile.get()):
                    self.var_selected_profile.set(profile_names[0])

        def start_browser_for_profile_login(self):
            """Start browser for ONE-TIME login to extract credentials - FIXED LOGIN CHECK"""  # inserted
            profile = self.var_selected_profile.get()
            if not profile or profile == 'Create profiles first':
                AutoCloseMessageBox.showwarning('No Profile', 'Please create and select a profile first!')
            return None

        def extract_and_save_credentials(self):
            """\n✅ FINAL VERSION: Extract token and save\n\n- Works for both AUTO and MANUAL extraction\n- Fast: Only reads recent 500 logs\n- Simple: No unnecessary checks\n- Clean: Proper error handling\n"""  # inserted
            try:
                if not self.browser or not self.current_profile:
                    self.log('[EXTRACT] ❌ No browser/profile', 'err')
                    messagebox.showerror('Error', 'Browser not running or no profile selected!')
                return False
            except Exception as e:
                logger.error(f'Extract error: {e}', exc_info=True)
                self.log(f'[EXTRACT] ❌ ERROR: {str(e)[:200]}', 'err')
                messagebox.showerror('Error', f'Extraction failed:\n\n{str(e)[:200]}\n\nCheck logs for details.')
                return False

        def _auto_extract_now(self):
            """\nAUTO EXTRACT - Simplified version\nCalled when login detected\n"""  # inserted
            try:
                if not self.browser or not self.current_profile:
                    self.log('[EXTRACT] ❌ No browser/profile', 'err')
                return None
            except Exception as e:
                logger.error(f'Auto extract error: {e}', exc_info=True)
                self.log(f'[EXTRACT] ❌ ERROR: {str(e)[:200]}', 'err')

        def stop_browser(self):
            """Stop browser"""  # inserted
            if not self.browser:
                pass  # postinserted
            return None

        def update_browser_status(self, status, color='gray'):
            """Update browser status label"""  # inserted
            if hasattr(self, 'lbl_browser_status'):
                self.lbl_browser_status.config(text=f'Browser: {status}', foreground=color)
            return None

        def update_login_status(self, status, color='gray'):
            """Update login status label"""  # inserted
            if hasattr(self, 'lbl_login_status'):
                self.lbl_login_status.config(text=status, foreground=color)
            return None

        def _refresh_accounts_list(self):
            """Refresh API account dropdown"""  # inserted
            try:
                accounts = self.credential_manager.list_profiles()
                if accounts:
                    self.account_dropdown['values'] = accounts
                    if not self.account_var.get() or self.account_var.get() not in accounts:
                        self.account_var.set(accounts[0])
                        self._load_account(accounts[0])
                    return None
                return None
            except Exception as e:
                logger.error(f'Refresh accounts error: {e}')

        def _on_account_selected(self, event=None):
            """Handle account selection"""  # inserted
            try:
                account = self.account_var.get()
                if account and account!= 'No accounts - Extract credentials first':
                    self._load_account(account)
                    return
            except Exception as e:
                logger.error(f'Account selected error: {e}')

        def _load_account(self, account_name: str):
            """Load account for API usage"""  # inserted
            try:
                self.log(f'[ACCOUNT] 📂 Loading: {account_name}', 'info')
                if not hasattr(self, 'api_manager') or not self.api_manager:
                    self.api_manager = APIGenerationManager(self.credential_manager)
                success = self.api_manager.set_account(account_name)
                if success:
                    self.account_status_label.config(text=f'Status: ✅ {account_name} ready for API', foreground='green')
                    self.log('[ACCOUNT] ✅ Ready', 'ok')
                return None
            except Exception as e:
                logger.error(f'Load account error: {e}')
                self.account_status_label.config(text='Status: ❌ Error', foreground='red')

        def _check_account_status(self):
            """Check if account is valid"""  # inserted
            try:
                account = self.account_var.get()
                if not account or account == 'No accounts - Extract credentials first':
                    AutoCloseMessageBox.showinfo('No Selection', 'Select account first!')
                return None
            except Exception as e:
                logger.error(f'Check account error: {e}')
                messagebox.showerror('Error', str(e)[:200])

        def _remove_account(self):
            """Remove account credentials"""  # inserted
            try:
                account = self.account_var.get()
                if not account or account == 'No accounts - Extract credentials first':
                    AutoCloseMessageBox.showinfo('No Selection', 'Select account first!')
                return None
            except Exception as e:
                logger.error(f'Remove account error: {e}')

        def _on_concurrent_toggle(self):
            """\nCallback khi toggle concurrent mode\n"""  # inserted
            enabled = self.var_enable_concurrent.get()
            if enabled:
                self.lbl_concurrent_info.config(text='✅ Faster but needs more CPU/RAM', foreground='green')
                self.log('[MODE] ⚡ Concurrent mode ENABLED (2 workers)', 'ok')
            return None

        def _concurrent_generation_thread(self, prompt_list):
            """\nBackground thread cho concurrent generation\n\nArgs:\n    prompt_list: List of prompts to generate\n"""  # inserted
            try:
                self.concurrent_manager.start(prompt_list)
                self.concurrent_manager.wait_completion()
                self = self.concurrent_manager.get_stats()
                self.log('======================================================================', 'info')
                self.log('🎉 ALL WORKERS COMPLETE!', 'ok')
                self.log(f"   ✅ Success: {self['completed']}", 'ok')
                self.log(f"   ❌ Failed: {self['failed']}", 'err')
                self.log(f"   📊 Total: {self['total']}", 'info')
                self.log('======================================================================', 'info')
                self.schedule_gui_update(lambda: messagebox.showinfo('Complete', f"🎉 Generation finished!\n\n✅ Success: {stats['completed']}\n❌ Failed: {stats['failed']}\n📊 Total: {stats['total']}"))
                self.is_generating = False
                self.schedule_gui_update(lambda: self.btn_start_gen.config(state='normal'))
                self.schedule_gui_update(lambda: self.btn_stop_gen.config(state='disabled'))
            except Exception as e:
                logger.error(f'[CONCURRENT] Thread error: {e}', exc_info=True)
                self.log(f'[ERROR] {str(e)[:100]}', 'err')

    def main():
        lock = SingleInstanceLock(app_name='Sora2AI_VideoGenerator_v33', port=59999, enable_admin_bypass=False, enable_whitelist=True)
        if not lock.acquire():
            show_already_running_dialog()
            sys.exit(0)
        hw_id = lock._get_hardware_id()
        print('=' * 60)
        print(f'🔑 Hardware ID của máy này: {hw_id}')
        print('=' * 60)
        try:
            root = tk.Tk()
            try:
                root.iconbitmap('icon.ico')
                app = App(root)

                def on_closing():
                    lock.release()
                    root.destroy()
                root.protocol('WM_DELETE_WINDOW', on_closing)
                root.mainloop()
                lock.release()
            except:
                pass
        except KeyboardInterrupt:
            logger.info('Interrupted by user')
            lock.release()
            sys.exit(0)
    if __name__ == '__main__':
        main()

        def _setup_account_management_ui(self, parent_frame):
            """Setup Account Management UI - thay cho browser controls"""  # inserted
            account_frame = ttk.LabelFrame(parent_frame, text='👥 Account Management (100% API Mode)', padding=15)
            account_frame.pack(fill=tk.X, padx=10, pady=10)
            ttk.Label(account_frame, text='💡 Add account once → Generate forever (No browser needed!)', font=('Arial', 10), foreground='blue').pack(pady=5)
            select_frame = ttk.Frame(account_frame)
            select_frame.pack(fill=tk.X, pady=5)
            ttk.Label(select_frame, text='Account:', font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=5)
            self.account_var = tk.StringVar()
            self.account_dropdown = ttk.Combobox(select_frame, textvariable=self.account_var, state='readonly', width=30)
            self.account_dropdown.pack(side=tk.LEFT, padx=5)
            self.account_dropdown.bind('<<ComboboxSelected>>', self._on_account_selected)
            self.account_status_label = ttk.Label(account_frame, text='Status: No account selected', font=('Arial', 9), foreground='gray')
            self.account_status_label.pack(pady=5)
            btn_frame = ttk.Frame(account_frame)
            btn_frame.pack(fill=tk.X, pady=5)
            ttk.Button(btn_frame, text='➕ Add Account', command=self._add_account_dialog, width=15).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text='🗑️ Remove', command=self._remove_account, width=12).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_frame, text='✅ Check Status', command=self._check_account_status, width=15).pack(side=tk.LEFT, padx=5)
            self._refresh_accounts_list()

        def _refresh_accounts_list(self):
            """Refresh account dropdown"""  # inserted
            try:
                accounts = self.credential_manager.list_profiles()
                self.account_dropdown['values'] = accounts
                if accounts:
                    self.account_dropdown.current(0)
                    self.account_var.set(accounts[0])
                    self._load_account(accounts[0])
                return None
            except Exception as e:
                logger.error(f'Refresh accounts error: {e}')

        def _on_account_selected(self, event=None):
            """Handle account selection"""  # inserted
            try:
                account = self.account_var.get()
                if account:
                    self._load_account(account)
                return None
            except Exception as e:
                logger.error(f'Account selected error: {e}')

        def _load_account(self, account_name: str):
            """Load account and initialize API manager"""  # inserted
            try:
                self.log(f'[ACCOUNT] Loading: {account_name}', 'info')
                if not self.api_manager:
                    self.api_manager = APIGenerationManager(self.credential_manager)
                success = self.api_manager.set_account(account_name)
                if success:
                    self.account_status_label.config(text=f'Status: ✅ {account_name} ready', foreground='green')
                    self.log(f'[ACCOUNT] ✅ {account_name} loaded', 'ok')
                return None
            except Exception as e:
                logger.error(f'Load account error: {e}')
                self.log(f'[ACCOUNT] ❌ Error: {str(e)[:100]}', 'err')

        def add_account():
            account_name = name_var.get().strip()
            if not account_name:
                messagebox.showerror('Invalid', 'Account name cannot be empty')
            return None

        def _on_account_added(self, account_name: str, success: bool):
            """Callback after account added"""  # inserted
            try:
                if success:
                    self.log(f'[ACCOUNT] ✅ {account_name} added successfully!', 'ok')
                    self._refresh_accounts_list()
                    self.account_var.set(account_name)
                    self._load_account(account_name)
                    messagebox.showinfo('Success!', f'✅ Account \'{account_name}\' added!\n\nYou can now generate videos with 100% API mode.')
                return None
            except Exception as e:
                logger.error(f'On account added error: {e}')

        def _remove_account(self):
            """Remove selected account"""  # inserted
            try:
                account = self.account_var.get()
                if not account:
                    messagebox.showinfo('No Selection', 'Please select an account first')
                return None
            except Exception as e:
                logger.error(f'Remove account error: {e}')

        def _check_account_status(self):
            """Check if account/token is valid"""  # inserted
            try:
                account = self.account_var.get()
                if not account:
                    messagebox.showinfo('No Selection', 'Please select an account first')
                return None
            except Exception as e:
                logger.error(f'Check account error: {e}')
except ImportError:
    SELENIUM_AVAILABLE = False
except ImportError:
    PIL_AVAILABLE = False
except ImportError as e:
    import sys
    import random
    error_code = random.randint(4096, 65535)
    logger.critical(f'[SECURITY] Critical modules missing: {e}')
    logger.critical('[SECURITY] Application cannot start without security modules')
    try:
        import tkinter.messagebox as messagebox
        messagebox.showerror('Security Error', f'Critical security components not found.\n\nApplication cannot start.\n\nError Code: 0x{error_code:04X}\n\nContact: Zalo 0789.535.888')
    except:
        print(f'[FATAL] Security modules missing. Error: 0x{error_code:04X}')
    sys.exit(1)
    protection_system = ProtectionSystem()
    EXPECTED_EXE_HASH = ''