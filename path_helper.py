#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path Helper for PyInstaller Executable
Handles resource paths for both development and frozen (EXE) modes

Author: Trần Nguyên
Version: 1.0
"""

import sys
import os
from pathlib import Path

def get_resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller
    
    Args:
        relative_path: Relative path to resource file
    
    Returns:
        Absolute path to resource
    
    Usage:
        config_path = get_resource_path('sora_browser_config.json')
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Not frozen, use current directory
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def get_writable_path(relative_path):
    """
    Get path for writable files (config, data, profiles)
    These files should be in the same directory as the EXE
    
    Args:
        relative_path: Relative path to writable file/folder
    
    Returns:
        Absolute path to writable location
    
    Usage:
        profile_path = get_writable_path('chrome_profile')
        config_path = get_writable_path('profile_usage.json')
    """
    if getattr(sys, 'frozen', False):
        # Running as EXE - use EXE directory
        base_path = os.path.dirname(sys.executable)
    else:
        # Running as script - use current directory
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def ensure_writable_file(relative_path, default_content='{}'):
    """
    Ensure writable file exists, create with default content if not
    
    Args:
        relative_path: Relative path to file
        default_content: Default content if file doesn't exist
    
    Returns:
        Absolute path to file
    
    Usage:
        config_path = ensure_writable_file('profile_usage.json')
    """
    file_path = get_writable_path(relative_path)
    
    if not os.path.exists(file_path):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(default_content)
        except Exception as e:
            print(f"[PATH] Warning: Cannot create {file_path}: {e}")
    
    return file_path

def ensure_writable_folder(relative_path):
    """
    Ensure writable folder exists, create if not
    
    Args:
        relative_path: Relative path to folder
    
    Returns:
        Absolute path to folder
    
    Usage:
        chrome_profile_dir = ensure_writable_folder('chrome_profile')
    """
    folder_path = get_writable_path(relative_path)
    
    try:
        os.makedirs(folder_path, exist_ok=True)
    except Exception as e:
        print(f"[PATH] Warning: Cannot create folder {folder_path}: {e}")
    
    return folder_path

def is_frozen():
    """
    Check if running as frozen executable
    
    Returns:
        True if running as EXE, False if running as script
    """
    return getattr(sys, 'frozen', False)

def get_exe_dir():
    """
    Get directory containing the executable or script
    
    Returns:
        Absolute path to directory
    """
    if is_frozen():
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(".")

# ============================================================================
# CONVENIENCE FUNCTIONS FOR COMMON PATHS
# ============================================================================

def get_config_path(filename):
    """Get path to config file (writable)"""
    return ensure_writable_file(filename, '{}')

def get_chrome_profile_dir():
    """Get path to chrome_profile directory (writable)"""
    return ensure_writable_folder('chrome_profile')

def get_downloads_dir():
    """Get path to downloads directory (writable)"""
    return ensure_writable_folder('downloads')

def get_profile_usage_path():
    """Get path to profile_usage.json (writable)"""
    return ensure_writable_file('profile_usage.json', '{"profiles": [], "current_profile_index": 0}')

def get_profile_tokens_path():
    """Get path to profile_tokens.json (writable)"""
    return ensure_writable_file('profile_tokens.json', '{"tokens": {}, "count": 0}')

def get_license_path():
    """Get path to license file (writable)"""
    return get_writable_path('sora_license.dat')

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("=== Path Helper Test ===")
    print(f"Is Frozen: {is_frozen()}")
    print(f"EXE Dir: {get_exe_dir()}")
    print()
    print("Writable Paths:")
    print(f"  Chrome Profile: {get_chrome_profile_dir()}")
    print(f"  Downloads: {get_downloads_dir()}")
    print(f"  Profile Usage: {get_profile_usage_path()}")
    print(f"  Profile Tokens: {get_profile_tokens_path()}")
    print(f"  License: {get_license_path()}")