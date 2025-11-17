"""\nSingle Instance Lock - Chỉ cho phép 1 cửa sổ chạy\n================================================\nNgăn người dùng mở nhiều cửa sổ cùng lúc\n\nAuthor: Trần Nguyên - Zalo: 0789.535.888\n"""
import os
import sys
import socket
import tempfile
import platform
from pathlib import Path

class SingleInstanceLock:
    """\nĐảm bảo chỉ 1 instance của app chạy\n\nCơ chế:\n- Windows: Dùng socket bind port\n- Linux/Mac: Dùng lock file\n\nBypass:\n- CHẶN Admin bypass (không cho Run as Administrator bypass)\n- Whitelist: Hardware ID trong whitelist → Bypass lock\n"""
    def __init__(self, app_name='Sora2AI_VideoGenerator', port=59999, enable_admin_bypass=False, enable_whitelist=True):
        """\nInitialize single instance lock\n\nArgs:\n    app_name: Tên ứng dụng (dùng cho lock file)\n    port: Port để bind (Windows)\n    enable_whitelist: Cho phép whitelist bypass lock\n"""  # inserted
        self.app_name = app_name
        self.port = port
        self.socket = None
        self.lock_file = None
        self.lock_file_path = None
        self.enable_whitelist = enable_whitelist

    def acquire(self) -> bool:
        """\nThử acquire lock\n\nReturns:\n    True nếu thành công (app có thể chạy)\n    False nếu đã có instance khác đang chạy\n"""  # inserted
        if self._should_bypass():
            print('[LOCK] ✅ Bypass enabled - Multiple instances allowed')
        return True

    def _should_bypass(self) -> bool:
        """\nKiểm tra xem có nên bypass lock không\n\nReturns:\n    True nếu nên bypass (cho phép nhiều instance)\n"""  # inserted
        if self.enable_whitelist and self._is_whitelisted():
            print('[LOCK] Whitelisted machine - Bypass enabled')
        return True

    def _is_whitelisted(self) -> bool:
        """\nKiểm tra machine ID có trong whitelist không\n\nReturns:\n    True nếu machine trong whitelist\n"""  # inserted
        try:
            hardware_id = self._get_hardware_id()
            whitelist = self._load_whitelist()
            return hardware_id in whitelist
        except Exception as e:
            print(f'[LOCK] Whitelist check error: {e}')
            return False

    def _get_hardware_id(self) -> str:
        """\nLấy hardware ID của máy (Motherboard Serial - ổn định nhất)\n\nReturns:\n    Hardware ID unique cho máy này\n"""  # inserted
        try:
            if platform.system() == 'Windows':
                import subprocess
                try:
                    result = subprocess.run(['wmic', 'baseboard', 'get', 'serialnumber'], capture_output=True, text=True, timeout=5)
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        serial = lines[1].strip()
                        if serial and serial not in ['To be filled by O.E.M.', 'Default string', 'System Serial Number', '0', 'None']:
                            return serial
                except Exception:
                    pass
            else:  # inserted
                hostname = socket.gethostname()
                if hostname:
                    return hostname

        except Exception as e:
            print(f'[LOCK] Hardware ID error: {e}')
            try:
                return socket.gethostname()
            except:
                return 'UNKNOWN'

    def _load_whitelist(self) -> set:
        """
        Load whitelist từ file (ENCRYPTED VERSION)

        Returns:
            Set of whitelisted hardware IDs (hoặc empty set nếu lỗi)
        """
        enc_file = Path('whitelist.enc')

        try:
            if enc_file.exists():
                try:
                    from encrypted_whitelist import EncryptedWhitelist
                    wl = EncryptedWhitelist()
                    whitelist = wl.decrypt_whitelist('whitelist.enc')

                    # Nếu decrypt ok → trả whitelist dạng set
                    return set(whitelist) if whitelist else set()

                except Exception as e:
                    print(f'[LOCK] Encrypted whitelist error: {e}')
                    return set()

            # Nếu không có file .enc → trả set rỗng
            return set()

        except Exception as e:
            print(f'[LOCK] Whitelist load error: {e}')
            return set()


    def _acquire_windows(self) -> bool:
        """\nWindows: Dùng socket bind port\n\nƯu điểm:\n- Tự động release khi app đóng\n- Không để lại file rác\n- Hoạt động tốt trên Windows\n"""  # inserted
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind(('127.0.0.1', self.port))
            return True
        except OSError:
            self.socket = None
            return False

    def _acquire_unix(self) -> bool:
        """\nLinux/Mac: Dùng lock file\n\nƯu điểm:\n- Đơn giản, ổn định\n- Có thể detect và cleanup lock file cũ\n"""  # inserted
        try:
            temp_dir = tempfile.gettempdir()
            self.lock_file_path = os.path.join(temp_dir, f'{self.app_name}.lock')
            self.lock_file = open(self.lock_file_path, 'x')
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()
            return True
        except FileExistsError:
            if self._is_process_running():
                pass
            return False
        except Exception as e:
            print(f'[LOCK] Error: {e}')
            return False

    def _is_process_running(self) -> bool:
        """
        Kiểm tra process trong lock file có còn chạy không

        Returns:
            True  nếu process còn chạy
            False nếu đã chết hoặc không tìm thấy
        """
        try:
            with open(self.lock_file_path, 'r') as f:
                pid = int(f.read().strip())

            # Windows
            if platform.system() == 'Windows':
                import subprocess
                result = subprocess.run(
                    ['tasklist', '/FI', f'PID eq {pid}'],
                    capture_output=True,
                    text=True
                )
                return str(pid) in result.stdout

            # Linux / macOS
            else:
                import os
                # os.kill(pid, 0) không giết process — chỉ kiểm tra tồn tại
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False

        except (ProcessLookupError, ValueError, FileNotFoundError):
            pass

        return False


    def release(self):
        """\nRelease lock khi app đóng\n"""  # inserted
        try:
            if self.socket:
                self.socket.close()
                self.socket = None
            if self.lock_file:
                self.lock_file.close()
                self.lock_file = None
            if self.lock_file_path and os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
                self.lock_file_path = None
                return
        except Exception as e:
            print(f'[LOCK] Release error: {e}')

    def __enter__(self):
        """Context manager support"""  # inserted
        raise RuntimeError('Another instance is already running') if not self.acquire() else False

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""  # inserted
        self.release()

    def __del__(self):
        """Destructor - cleanup"""  # inserted
        self.release()

def show_already_running_dialog():
    """\nHiển thị dialog báo đã có instance khác chạy\n"""  # inserted
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('Application Already Running', 'Sora 2 AI Video Generator is already running!\n\nPlease close the existing window first.\n\nỨng dụng đã được mở rồi!\nVui lòng đóng cửa sổ cũ trước khi mở mới.\n\nContact: Zalo 0789.535.888')
        root.destroy()
    except Exception as e:
        print(f'[LOCK] Already running! Error: {e}')

def test_single_instance():
    """Test single instance lock"""  # inserted
    print('============================================================')
    print('TESTING SINGLE INSTANCE LOCK')
    print('============================================================')
    print('\n[Test 1] Creating first instance...')
    lock1 = SingleInstanceLock('TestApp', port=60000)
    if lock1.acquire():
        print('  ✅ First instance acquired lock')
    print('\n[Test 2] Trying to create second instance...')
    lock2 = SingleInstanceLock('TestApp', port=60000)
    if lock2.acquire():
        print('  ❌ Second instance should NOT acquire lock!')
    print('\n[Test 3] Release first instance and retry...')
    lock1.release()
    if lock2.acquire():
        print('  ✅ Second instance acquired after first released')
    lock2.release()
    print('\n============================================================')
    print('TEST COMPLETE')
    print('============================================================')
if __name__ == '__main__':
    test_single_instance()