#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora 2 AI - Protection System
Basic anti-tampering and integrity checks

FEATURES:
- File integrity verification (SHA256)
- License file tampering detection
- Anti-debug checks (optional)
- Runtime protection monitoring
- Security logging

USAGE:
- Integrated into main application
- Automatic checks at startup and runtime
"""

import hashlib
import os
import sys
import time
import platform
from datetime import datetime
from typing import Tuple, Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

EXPECTED_EXE_HASH = ""  # Will be filled after first build
LOG_FILE = "sora_security.log"

# ============================================================================
# FILE INTEGRITY CHECK
# ============================================================================

class IntegrityCheck:
    """File integrity verification"""
    
    @staticmethod
    def get_file_hash(filepath: str) -> Optional[str]:
        """Calculate SHA256 hash of file"""
        try:
            sha256 = hashlib.sha256()
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Hash calculation error: {e}")
            return None
    
    @staticmethod
    def verify_executable(expected_hash: str) -> bool:
        """Verify executable hasn't been modified"""
        if not expected_hash:
            # Hash not set yet - skip check during development
            return True
        
        try:
            exe_path = sys.executable
            actual_hash = IntegrityCheck.get_file_hash(exe_path)
            
            if not actual_hash:
                return False
            
            return actual_hash.lower() == expected_hash.lower()
        except:
            return False
    
    @staticmethod
    def check_license_file_tampering(license_path: str) -> bool:
        """Check if license file was recently modified (potential tampering)"""
        try:
            if not os.path.exists(license_path):
                return False
            
            mtime = os.path.getmtime(license_path)
            file_age_hours = (time.time() - mtime) / 3600
            
            # If file was modified in last 5 minutes, might be tampering
            return file_age_hours < 0.083  # 5 minutes
        except:
            return False

# ============================================================================
# BASIC ANTI-DEBUG DETECTION
# ============================================================================

class AntiDebug:
    """Basic debugging detection - non-aggressive"""
    
    @staticmethod
    def timing_check() -> bool:
        """Simple timing check for debugger presence"""
        try:
            start = time.perf_counter()
            x = 1
            for i in range(10000):
                x += i
            elapsed = time.perf_counter() - start
            
            # If code takes unusually long, might be debugged
            return elapsed > 0.5  # 500ms threshold
        except:
            return False
    
    @staticmethod
    def check_debugger_present() -> bool:
        """Check if debugger is attached (Windows only)"""
        if platform.system() != "Windows":
            return False
        
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            return kernel32.IsDebuggerPresent() != 0
        except:
            return False
    
    @staticmethod
    def check_all() -> bool:
        """Run all anti-debug checks"""
        return (AntiDebug.check_debugger_present() or 
                AntiDebug.timing_check())

# ============================================================================
# PROTECTION SYSTEM
# ============================================================================

class ProtectionSystem:
    """Main protection system coordinator"""
    
    def __init__(self, enable_integrity_check: bool = True, 
                 enable_anti_debug: bool = False):
        """
        Initialize protection system
        
        Args:
            enable_integrity_check: Enable file integrity verification
            enable_anti_debug: Enable anti-debugging (can cause false positives)
        """
        self.enable_integrity_check = enable_integrity_check
        self.enable_anti_debug = enable_anti_debug
        self.protection_triggered = False
        self.last_check = time.time()
    
    def protect_startup(self) -> bool:
        """
        Run protection checks at application startup
        
        Returns:
            True if all checks passed, False if threat detected
        """
        is_safe, threat = self._run_startup_checks()
        
        if not is_safe:
            self._handle_threat(threat)
            return False
        
        return True
    
    def protect_runtime(self, license_validate_func) -> bool:
        """
        Run periodic protection checks during runtime
        
        Args:
            license_validate_func: Function to validate license status
            
        Returns:
            True if all checks passed, False if threat detected
        """
        # Only check every 5 minutes to avoid performance impact
        elapsed = time.time() - self.last_check
        if elapsed < 300:
            return True
        
        self.last_check = time.time()
        
        # Run protection checks
        is_safe, threat = self._run_runtime_checks()
        if not is_safe:
            self._handle_threat(threat)
            return False
        
        # Validate license
        is_valid, message = license_validate_func()
        if not is_valid:
            self._handle_threat("LICENSE_INVALID")
            return False
        
        return True
    
    def _run_startup_checks(self) -> Tuple[bool, str]:
        """Run checks at startup"""
        # Check 1: Anti-debug (if enabled)
        if self.enable_anti_debug and AntiDebug.check_all():
            return False, "DEBUGGER_DETECTED"
        
        # Check 2: File integrity (if enabled and hash is set)
        if self.enable_integrity_check and EXPECTED_EXE_HASH:
            if not IntegrityCheck.verify_executable(EXPECTED_EXE_HASH):
                return False, "FILE_MODIFIED"
        
        return True, "OK"
    
    def _run_runtime_checks(self) -> Tuple[bool, str]:
        """Run checks during runtime"""
        # Check 1: License file tampering
        license_file = "sora_license.dat"
        if IntegrityCheck.check_license_file_tampering(license_file):
            return False, "LICENSE_TAMPERED"
        
        # Check 2: Anti-debug (if enabled)
        if self.enable_anti_debug and AntiDebug.check_all():
            return False, "DEBUGGER_DETECTED"
        
        return True, "OK"
    
    def _handle_threat(self, threat_type: str):
        """Handle detected security threat"""
        if self.protection_triggered:
            return
        
        self.protection_triggered = True
        
        # Log the threat
        self._log_threat(threat_type)
        
        # Show error message
        try:
            import tkinter as tk
            from tkinter import messagebox
            
            root = tk.Tk()
            root.withdraw()
            
            messages = {
                "DEBUGGER_DETECTED": 
                    "Security Alert: Debugging detected.\n\n"
                    "Application will exit for security reasons.",
                "FILE_MODIFIED": 
                    "Security Alert: File integrity check failed.\n\n"
                    "The application file may have been modified.\n"
                    "Please reinstall from official source.\n\n"
                    "Contact: Zalo 0789.535.888",
                "LICENSE_TAMPERED": 
                    "Security Alert: License file tampering detected.\n\n"
                    "Please contact: Zalo 0789.535.888",
                "LICENSE_INVALID": 
                    "License validation failed.\n\n"
                    "Your license may have expired or is invalid.\n\n"
                    "Contact: Zalo 0789.535.888"
            }
            
            msg = messages.get(threat_type, "Security violation detected.")
            messagebox.showerror("Security Alert", msg)
            
            root.destroy()
        except:
            pass
        
        # Exit application
        sys.exit(1)
    
    def _log_threat(self, threat_type: str):
        """Log security threat to file"""
        try:
            with open(LOG_FILE, 'a') as f:
                timestamp = datetime.now().isoformat()
                f.write(f"{timestamp} - THREAT: {threat_type}\n")
        except:
            pass

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_exe_hash() -> Optional[str]:
    """Calculate hash of current executable (for setup)"""
    try:
        exe_path = sys.executable
        return IntegrityCheck.get_file_hash(exe_path)
    except:
        return None

def test_protection():
    """Test protection system"""
    print("="*60)
    print("SORA 2 AI PROTECTION SYSTEM - TEST")
    print("="*60)
    
    # Test 1: Calculate EXE hash
    print("\n[Test 1] Calculate executable hash...")
    exe_hash = calculate_exe_hash()
    if exe_hash:
        print(f"  ✓ Hash: {exe_hash}")
        print(f"  → Add this to sora_protection_system.py:")
        print(f'     EXPECTED_EXE_HASH = "{exe_hash}"')
    else:
        print("  ✗ Failed to calculate hash")
    
    # Test 2: Anti-debug check
    print("\n[Test 2] Anti-debug detection...")
    if AntiDebug.check_all():
        print("  ⚠ Debugger detected!")
    else:
        print("  ✓ No debugger detected")
    
    # Test 3: License file check
    print("\n[Test 3] License file integrity...")
    if os.path.exists("sora_license.dat"):
        is_tampered = IntegrityCheck.check_license_file_tampering("sora_license.dat")
        if is_tampered:
            print("  ⚠ License file recently modified")
        else:
            print("  ✓ License file OK")
    else:
        print("  ℹ No license file found")
    
    # Test 4: Protection system
    print("\n[Test 4] Protection system...")
    protection = ProtectionSystem(
        enable_integrity_check=False,  # Disable for testing
        enable_anti_debug=False
    )
    
    if protection.protect_startup():
        print("  ✓ Startup checks passed")
    else:
        print("  ✗ Startup checks failed")
    
    print("\n" + "="*60)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    test_protection()