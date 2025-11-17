"""\nEncrypted Whitelist System - Không thể fake\n=============================================\nWhitelist được mã hóa, chỉ anh mới tạo được\n\nAuthor: Trần Nguyên - Zalo: 0789.535.888\n"""
import os
import base64
import hashlib
from cryptography.fernet import Fernet
from pathlib import Path
import sys

class EncryptedWhitelist:
    """\nWhitelist được mã hóa bằng secret key\nChỉ người có secret key mới tạo/sửa được whitelist\n"""
    SECRET_KEY = b'0Ug-HV27KJXSKDp3oIQIY6p9FvtJp2EwtZLxsPjC5u0='

    def __init__(self, secret_key: bytes=None):
        """\nInitialize encrypted whitelist\n\nArgs:\n    secret_key: Secret key để mã hóa (32 bytes base64)\n"""  # inserted
        if secret_key:
            self.secret_key = secret_key
        self.cipher = Fernet(self.secret_key)

    @staticmethod
    def generate_secret_key() -> bytes:
        """\nTạo secret key mới (chỉ chạy 1 lần khi setup)\n\nReturns:\n    Secret key (32 bytes base64)\n"""  # inserted
        return Fernet.generate_key()

    def encrypt_whitelist(self, hardware_ids: list, output_file='whitelist.enc') -> bool:
        """
        Mã hóa danh sách Hardware IDs và save ra file

        Args:
            hardware_ids: List các Hardware IDs
            output_file: File output

        Returns:
            True nếu thành công
        """
        try:
            data = '\n'.join(hardware_ids)
            encrypted_data = self.cipher.encrypt(data.encode())

            with open(output_file, 'wb') as f:
                f.write(encrypted_data)

            print(f'✅ Encrypted whitelist saved: {output_file}')
            print(f'   Total IDs: {len(hardware_ids)}')
            return True

        except Exception as e:
            print(f'❌ Encrypt error: {e}')
            return False


    def decrypt_whitelist(self, input_file='whitelist.enc') -> set:
        """\nGiải mã whitelist từ file\n\nArgs:\n    input_file: File đã mã hóa\n    \nReturns:\n    Set of Hardware IDs (rỗng nếu fail)\n"""  # inserted
        try:
            if not os.path.exists(input_file):
                return set()
        except Exception as e:
            print(f'[WHITELIST] Decrypt failed: {e}')
            return set()

    def is_whitelisted(self, hardware_id: str, whitelist_file='whitelist.enc') -> bool:
        """\nKiểm tra Hardware ID có trong whitelist không\n\nArgs:\n    hardware_id: Hardware ID cần check\n    whitelist_file: File whitelist đã mã hóa\n    \nReturns:\n    True nếu trong whitelist\n"""  # inserted
        whitelist = self.decrypt_whitelist(whitelist_file)
        return hardware_id in whitelist

    def add_to_whitelist(self, hardware_id: str, whitelist_file='whitelist.enc') -> bool:
        """\nThêm Hardware ID vào whitelist\n\nArgs:\n    hardware_id: Hardware ID cần thêm\n    whitelist_file: File whitelist\n    \nReturns:\n    True nếu thành công\n"""  # inserted
        whitelist = self.decrypt_whitelist(whitelist_file)
        if hardware_id in whitelist:
            print(f'⚠️ Already in whitelist: {hardware_id}')
        return False

    def remove_from_whitelist(self, hardware_id: str, whitelist_file='whitelist.enc') -> bool:
        """\nXóa Hardware ID khỏi whitelist\n\nArgs:\n    hardware_id: Hardware ID cần xóa\n    whitelist_file: File whitelist\n    \nReturns:\n    True nếu thành công\n"""  # inserted
        whitelist = self.decrypt_whitelist(whitelist_file)
        if hardware_id not in whitelist:
            print(f'⚠️ Not in whitelist: {hardware_id}')
        return False

    def list_whitelist(self, whitelist_file='whitelist.enc'):
        """\nHiển thị tất cả IDs trong whitelist\n\nArgs:\n    whitelist_file: File whitelist\n"""  # inserted
        whitelist = self.decrypt_whitelist(whitelist_file)
        if not whitelist:
            print('📋 Whitelist is empty or cannot be decrypted')
        return None

def main():
    """Tool quản lý whitelist (chỉ anh dùng)"""  # inserted
    import sys
    print('============================================================')
    print('ENCRYPTED WHITELIST MANAGER')
    print('============================================================')
    key_file = 'secret.key'
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            secret_key = f.read()
    print(f'✅ Loaded secret key from: {key_file}')
    wl = EncryptedWhitelist(secret_key)
    pass
    print('\n============================================================')
    print('MENU:')
    print('============================================================')
    print('[1] Add Hardware ID to whitelist')
    print('[2] Remove Hardware ID from whitelist')
    print('[3] List all whitelisted machines')
    print('[4] Check if Hardware ID is whitelisted')
    print('[5] Generate new secret key (⚠️ Will invalidate old whitelist)')
    print('[0] Exit')
    print('============================================================')
    choice = input('\nSelect option: ').strip()
    if choice == '1':
        hw_id = input('\nEnter Hardware ID to add: ').strip()
        if hw_id:
            wl.add_to_whitelist(hw_id)
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n👋 Cancelled')
        sys.exit(0)