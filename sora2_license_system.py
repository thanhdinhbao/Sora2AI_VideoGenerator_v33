#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora 2 AI - License & Protection System (ENHANCED VERSION)
Hardware-based licensing with multiple time periods + CUSTOM DAYS + REMAINING DAYS EXTENSION

NEW FEATURES (v2):
✅ Custom Days License - Nhập số ngày bất kỳ (14, 23, 45, 100,...)
✅ Remaining Days Extension - Giữ số ngày còn lại khi đổi HWID

ORIGINAL FEATURES:
- Hardware ID binding (HDD serial, MAC address, CPU ID)
- Time-based licenses (1 day → Lifetime)
- Secure key generation with SHA256
- Activation dialog for end users
- Key generator tool for distributors
- Bearer token cookie protection

USAGE:
1. End User: Run app → Activation dialog → Enter license key
2. Distributor: python sora2_license_system.py keygen
3. Test: python sora2_license_system.py test
"""

import hashlib
import uuid
import platform
import subprocess
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ============================================================================
# CONFIGURATION - SECRET KEY (CRITICAL: Change this to your own!)
# ============================================================================

LICENSE_FILE = "sora_license.dat"

# ⚠️ IMPORTANT: Change this secret key to your own unique string
# This key is used to generate and validate license keys
SECRET_KEY = "Sora2AI_2025_Zalo_0789535888_TranNguyen_SHA256_HMAC_AES256_Protected"

# License duration options (in days)
LICENSE_PERIODS = {
    "1_DAY": 1,          # For testing
    "1_WEEK": 7,         # Trial period
    "1_MONTH": 30,       # Monthly subscription
    "2_MONTHS": 60,      # Bi-monthly
    "3_MONTHS": 90,      # Quarterly
    "6_MONTHS": 180,     # Semi-annual
    "1_YEAR": 365,       # Annual subscription
    "2_YEARS": 730,      # Biennial
    "LIFETIME": -1,      # Perpetual license
    "CUSTOM": 0          # ✅ NEW: Custom days (user input)
}

LICENSE_TIERS = {
    "FREE": {
        "max_profiles": 1,
        "max_characters": 5,  # 1 profile = 5 characters
        "max_videos_per_day": 30,
        "features": ["basic_generation"],
        "price": "Free",
        "description": "Trial tier - 1 profile only"
    },
    "BASIC": {
        "max_profiles": 5,
        "max_characters": 50,  # 5 profiles = 25 characters (5 per profile)
        "max_videos_per_day": 150,
        "features": ["basic_generation", "image_to_video", "text_to_video"],
        "price": "$49/month",
        "description": "Starter tier - 5 profiles"
    },
    "PROFESSIONAL": {
        "max_profiles": 10,
        "max_characters": 100,  # 10 profiles = 50 characters (5 per profile)
        "max_videos_per_day": 300,
        "features": ["basic_generation", "image_to_video", "text_to_video", "api_access", "batch_generation"],
        "price": "$99/month",
        "description": "Professional tier - 10 profiles"
    },
    "ENTERPRISE": {
        "max_profiles": 15,
        "max_characters": 150,  # 15 profiles = 75 characters (5 per profile)
        "max_videos_per_day": 450,
        "features": ["basic_generation", "image_to_video", "text_to_video", "api_access", "batch_generation", "priority_support"],
        "price": "$199/month",
        "description": "Enterprise tier - 15 profiles"
    },
    "ULTIMATE": {
        "max_profiles": 20,
        "max_characters": 200,  # 20 profiles = 100 characters (5 per profile)
        "max_videos_per_day": 600,
        "features": ["basic_generation", "image_to_video", "text_to_video", "api_access", "batch_generation", "priority_support", "white_label"],
        "price": "$399/month",
        "description": "Ultimate tier - 20 profiles"
    },
    "UNLIMITED": {
        "max_profiles": 999,  # Không giới hạn
        "max_characters": 999999,  # Không giới hạn characters
        "max_videos_per_day": 999999,
        "features": ["basic_generation", "image_to_video", "text_to_video", "api_access", "batch_generation", "priority_support", "white_label", "unlimited"],
        "price": "$999/month",
        "description": "Unlimited tier - No limits"
    }
}

# ============================================================================
# HARDWARE ID FUNCTIONS - Multi-component detection
# ============================================================================

def get_hardware_id() -> str:
    """
    Get unique hardware ID from computer
    
    Uses multiple components for reliability:
    1. HDD/SSD Serial Number (primary)
    2. MAC Address (fallback)
    3. CPU ID (additional)
    
    Returns:
        str: Formatted hardware ID (e.g., "A1B2-C3D4-E5F6-G7H8")
    """
    components = []
    
    # Component 1: HDD Serial Number (Most stable)
    try:
        if platform.system() == "Windows":
            # Try physical disk serial
            output = subprocess.check_output(
                "wmic diskdrive get serialnumber", 
                shell=True, 
                stderr=subprocess.DEVNULL
            ).decode()
            serial = output.split('\n')[1].strip()
            if serial and serial.lower() != "serialnumber":
                components.append(serial)
    except:
        pass
    
    # Fallback: Volume serial number
    if not components:
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output(
                    "vol c:", 
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode()
                for line in output.split('\n'):
                    if 'Serial Number' in line or 'Mã số sê-ri' in line:
                        serial = line.split()[-1].strip()
                        components.append(serial)
                        break
        except:
            pass
    
    # Component 2: MAC Address (Network card)
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                       for elements in range(0, 2*6, 2)][::-1])
        components.append(mac)
    except:
        pass
    
    # Component 3: CPU ID (Processor serial)
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(
                "wmic cpu get processorid", 
                shell=True,
                stderr=subprocess.DEVNULL
            ).decode()
            cpu_id = output.split('\n')[1].strip()
            if cpu_id and cpu_id.lower() != "processorid":
                components.append(cpu_id)
    except:
        pass
    
    # Validation: Must have at least one component
    if not components:
        raise Exception(
            "Cannot retrieve hardware information.\n\n"
            "This may happen if:\n"
            "- Running in virtual machine\n"
            "- Insufficient permissions\n"
            "- Hardware access blocked\n\n"
            "Please run as administrator or contact support."
        )
    
    # Generate unique hash from all components
    combined = "-".join(components)
    hwid = hashlib.sha256(combined.encode()).hexdigest()[:32].upper()
    
    # Format as XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
    formatted = "-".join([hwid[i:i+4] for i in range(0, 32, 4)])
    
    return formatted

# ============================================================================
# ✅ NEW: REMAINING DAYS CALCULATION
# ============================================================================

def get_remaining_days_from_license(license_key: str) -> Optional[int]:
    """
    Calculate remaining days from an existing license key
    
    Args:
        license_key: Existing license key (format: TIER-HWID-EXPIRY-SIGNATURE)
    
    Returns:
        int: Remaining days (or None if LIFETIME/invalid)
    
    Example:
        >>> remaining = get_remaining_days_from_license("PRO-A1B2C3D4-20250615-1234567890ABCDEF")
        >>> print(f"Còn lại: {remaining} ngày")
    """
    try:
        parts = license_key.strip().split("-")
        if len(parts) != 4:
            return None
        
        expiry = parts[2].upper()
        
        if expiry == "LIFETIME":
            return -1  # LIFETIME = -1
        
        # Parse expiry date
        expiry_date = datetime.strptime(expiry, "%Y%m%d")
        remaining = (expiry_date - datetime.now()).days
        
        # Nếu đã hết hạn, trả về 0
        if remaining < 0:
            return 0
        
        return remaining
    
    except Exception as e:
        print(f"[DEBUG] get_remaining_days_from_license error: {e}")
        return None

# ============================================================================
# LICENSE KEY GENERATION - Secure algorithm with SHA256 (ENHANCED)
# ============================================================================

def generate_license_key(
    hardware_id: str, 
    period_key: str = "1_YEAR", 
    tier: str = "BASIC",
    custom_days: Optional[int] = None,  # ✅ NEW: Custom days parameter
    remaining_days: Optional[int] = None  # ✅ NEW: Remaining days for HWID change
) -> str:
    """
    Generate license key for specific hardware WITH tier support (ENHANCED)
    
    Args:
        hardware_id: Hardware ID from get_hardware_id()
        period_key: License period (1_YEAR, LIFETIME, CUSTOM, etc.)
        tier: License tier (FREE, BASIC, PROFESSIONAL, ENTERPRISE, ULTIMATE, UNLIMITED)
        custom_days: ✅ NEW - Custom number of days (only used when period_key="CUSTOM")
        remaining_days: ✅ NEW - Remaining days from old license (for HWID transfer)
    
    Format: TIER(3)-HWID(8)-EXPIRY(8)-SIGNATURE(16)
    Example: PRO-A1B2C3D4-20251224-1234567890ABCDEF
    
    Returns:
        str: Formatted license key
    """
    # Validate tier
    if tier not in LICENSE_TIERS:
        tier = "BASIC"  # Default to BASIC
    
    # Get tier code (first 3 letters)
    tier_codes = {
        "FREE": "FRE",
        "BASIC": "BAS",
        "PROFESSIONAL": "PRO",
        "ENTERPRISE": "ENT",
        "ULTIMATE": "ULT",
        "UNLIMITED": "UNL"
    }
    tier_code = tier_codes.get(tier, "BAS")
    
    # Validate period
    if period_key not in LICENSE_PERIODS:
        raise ValueError(f"Invalid period: {period_key}. Use: {list(LICENSE_PERIODS.keys())}")
    
    # Format hardware ID (remove dashes, take first 8 chars, uppercase)
    hwid_clean = hardware_id.replace("-", "").upper()[:8]
    
    # ============================================================================
    # ✅ NEW: ENHANCED EXPIRY CALCULATION
    # ============================================================================
    
    # Priority 1: REMAINING DAYS (for HWID transfer)
    if remaining_days is not None:
        if remaining_days == -1:  # LIFETIME
            expiry_str = "LIFETIME"
        elif remaining_days <= 0:
            raise ValueError("❌ Remaining days must be > 0 (or -1 for LIFETIME)")
        else:
            expiry_date = datetime.now() + timedelta(days=remaining_days)
            expiry_str = expiry_date.strftime("%Y%m%d")
    
    # Priority 2: CUSTOM DAYS
    elif period_key == "CUSTOM":
        if custom_days is None or custom_days <= 0:
            raise ValueError("❌ Custom days must be specified and > 0 for CUSTOM period")
        
        expiry_date = datetime.now() + timedelta(days=custom_days)
        expiry_str = expiry_date.strftime("%Y%m%d")
    
    # Priority 3: STANDARD PERIODS
    else:
        days = LICENSE_PERIODS[period_key]
        
        if days == -1:  # LIFETIME
            expiry_str = "LIFETIME"
        else:
            expiry_date = datetime.now() + timedelta(days=days)
            expiry_str = expiry_date.strftime("%Y%m%d")
    
    # Generate signature (HWID + Expiry + Tier + SECRET_KEY)
    signature_input = f"{hwid_clean}{expiry_str}{tier}{SECRET_KEY}"
    signature = hashlib.sha256(signature_input.encode()).hexdigest()[:16].upper()
    
    # Format: TIER-HWID-EXPIRY-SIGNATURE
    license_key = f"{tier_code}-{hwid_clean}-{expiry_str}-{signature}"
    
    return license_key

# ============================================================================
# LICENSE VALIDATION - Verify key against hardware
# ============================================================================

def validate_license_key(hardware_id: str, license_key: str) -> Tuple[bool, str]:
    """Validate license key against current hardware"""
    try:
        # Remove formatting
        hwid_clean = hardware_id.replace("-", "").upper()  # ✅ UPPERCASE
        license_clean = license_key.strip()
        
        # Step 1: Check format
        if "-" not in license_clean or len(license_clean.split("-")) != 4:
            return False, "Invalid license key format"
        
        # Step 2: Parse components
        parts = license_clean.split("-")
        tier_code = parts[0].upper()
        hwid_from_key = parts[1].upper()
        expiry = parts[2].upper()
        signature = parts[3].upper()
        
        # Map tier code
        tier_code_map = {
            "FRE": "FREE",
            "BAS": "BASIC",
            "PRO": "PROFESSIONAL",
            "ENT": "ENTERPRISE",
            "ULT": "ULTIMATE",
            "UNL": "UNLIMITED"
        }
        
        tier = tier_code_map.get(tier_code, None)
        if tier is None:
            return False, f"Invalid tier code: {tier_code}"
        
        # Step 3: Hardware match
        if hwid_clean[:8] != hwid_from_key[:8]:
            return False, (
                "License key does not match this computer.\n\n"
                "This license is bound to different hardware.\n"
                "Contact Zalo: 0789.535.888 for license transfer."
            )
        
        # Step 4: Expiry check
        if expiry != "LIFETIME":
            try:
                expiry_date = datetime.strptime(expiry, "%Y%m%d")
                if datetime.now() > expiry_date:
                    return False, f"License expired on {expiry_date.strftime('%Y-%m-%d')}"
            except ValueError:
                return False, "Invalid expiry date format"
        
        # Step 5: Signature verification - CRITICAL
        # ✅ MUST MATCH generate_license_key() exactly
        signature_input = f"{hwid_from_key}{expiry}{tier}{SECRET_KEY}"
        expected_signature = hashlib.sha256(signature_input.encode()).hexdigest()[:16].upper()
        
        if signature != expected_signature:
            # ✅ DEBUG: Print để kiểm tra
            print(f"[DEBUG] Signature mismatch:")
            print(f"  HWID: {hwid_from_key}")
            print(f"  Expiry: {expiry}")
            print(f"  Tier: {tier}")
            print(f"  Expected: {expected_signature}")
            print(f"  Got: {signature}")
            
            return False, (
                "Invalid license key (signature mismatch).\n\n"
                "The key may be:\n"
                "- Corrupted during copy/paste\n"
                "- Generated with wrong secret key\n"
                "- Modified/tampered\n\n"
                "Contact: Zalo 0789.535.888"
            )
        
        # Step 6: Get tier info
        tier_info = LICENSE_TIERS.get(tier, {})
        max_profiles = tier_info.get('max_profiles', 1)
        max_videos = tier_info.get('max_videos_per_day', 30)
        
        # Success
        if expiry == "LIFETIME":
            return True, (f"License valid (Lifetime)\n"
                         f"Tier: {tier}\n"
                         f"Max Profiles: {max_profiles}\n"
                         f"Max Videos/Day: {max_videos}")
        else:
            expiry_date = datetime.strptime(expiry, "%Y%m%d")
            days_left = (expiry_date - datetime.now()).days
            
            return True, (f"License valid ({days_left} days remaining)\n"
                         f"Tier: {tier}\n"
                         f"Max Profiles: {max_profiles}\n"
                         f"Max Videos/Day: {max_videos}")
    
    except Exception as e:
        return False, f"Validation error: {str(e)}"

# ============================================================================
# LICENSE FILE MANAGEMENT
# ============================================================================

def save_license(license_key: str, license_file: str = LICENSE_FILE) -> bool:
    """Save activated license to file"""
    try:
        hwid = get_hardware_id()
        
        data = {
            "license_key": license_key,
            "activated_at": datetime.now().isoformat(),
            "hwid_hash": hashlib.sha256(hwid.encode()).hexdigest()[:16]
        }
        
        with open(license_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Save license error: {e}")
        return False

def load_license(license_file: str = LICENSE_FILE) -> Optional[str]:
    """Load license key from file"""
    try:
        if os.path.exists(license_file):
            with open(license_file, 'r') as f:
                data = json.load(f)
                return data.get("license_key")
    except Exception as e:
        print(f"Load license error: {e}")
    
    return None

def check_activation() -> Tuple[bool, str]:
    """Check if application is activated"""
    try:
        hwid = get_hardware_id()
    except Exception as e:
        return False, f"Hardware detection error: {str(e)}"
    
    license_key = load_license()
    
    if not license_key:
        return False, "No license found - Activation required"
    
    is_valid, message = validate_license_key(hwid, license_key)
    
    return is_valid, message

def get_license_features() -> dict:
    """
    Get license features including max_profiles and max_characters
    
    Returns license tier information based on current activation.
    If no license or invalid, returns FREE tier (1 profile, 10 characters).
    
    Returns:
        dict: License features with keys:
            - tier: str (FREE, BASIC, PROFESSIONAL, etc.)
            - max_profiles: int (1, 5, 10, 15, 20, or 999)
            - max_characters: int (10, 50, 100, 150, 200, or 999999)
            - max_videos_per_day: int
            - features: list[str]
            - expiry_date: str
            - days_remaining: int
            - description: str
    
    Example:
        >>> features = get_license_features()
        >>> print(f"Max profiles: {features['max_profiles']}")
        Max profiles: 10
        >>> print(f"Max characters: {features['max_characters']}")
        Max characters: 100
    """
    # Check current activation
    is_activated, message = check_activation()
    
    if not is_activated:
        # Return FREE tier as default
        return {
            'tier': 'FREE',
            'max_profiles': 1,
            'max_characters': 5,  # NEW: Character limit (5 chars per profile)
            'max_videos_per_day': 30,
            'features': ['basic_generation'],
            'expiry_date': 'N/A',
            'days_remaining': 0,
            'price': 'Free',
            'description': 'No license - FREE tier (1 profile only)'
        }
    
    # Load license and extract tier from key
    license_key = load_license()
    if not license_key:
        # Fallback to FREE
        return LICENSE_TIERS['FREE'].copy()
    
    # Parse license key to detect tier
    # Format: HWID-EXPIRY-SIGNATURE or with tier prefix
    # We'll check license key format and message to determine tier
    
    # Method 1: Check if tier is in the license key itself
    # (Future enhancement: encode tier in license key)
    key_upper = license_key.upper()
    detected_tier = None
    
    for tier_name in LICENSE_TIERS.keys():
        if tier_name in key_upper or tier_name in message.upper():
            detected_tier = tier_name
            break
    
    # Method 2: Default to BASIC if activated but tier not detected
    if not detected_tier:
        # Check message for clues
        if "lifetime" in message.lower():
            detected_tier = "UNLIMITED"  # Lifetime = Unlimited
        else:
            detected_tier = "BASIC"  # Default for old licenses
    
    # Get tier features
    features = LICENSE_TIERS.get(detected_tier, LICENSE_TIERS['FREE']).copy()
    features['tier'] = detected_tier
    
    # Extract expiry info from validation message
    try:
        license_key = load_license()
        if license_key:
            key_clean = license_key.replace("-", "").strip()
            expiry = key_clean[8:16]
            
            if expiry == "LIFETIME":
                features['expiry_date'] = "Lifetime"
                features['days_remaining'] = 999999
            else:
                expiry_date = datetime.strptime(expiry, "%Y%m%d")
                features['expiry_date'] = expiry_date.strftime("%Y-%m-%d")
                features['days_remaining'] = (expiry_date - datetime.now()).days
    except:
        # Fallback values
        features['expiry_date'] = 'Unknown'
        features['days_remaining'] = 0
    
    return features


def get_max_characters() -> int:
    """
    Get maximum number of characters allowed based on current license
    
    Returns:
        int: Maximum characters (5, 25, 50, 75, 100, or 999999)
    
    Examples:
        >>> max_chars = get_max_characters()
        >>> print(f"Max characters: {max_chars}")
        Max characters: 50
    """
    features = get_license_features()
    return features.get('max_characters', 5)  # Default to FREE tier (5 chars)


def check_character_limit(current_count: int) -> Tuple[bool, str]:
    """
    Check if user can add more characters
    
    Args:
        current_count: Current number of characters in database
    
    Returns:
        Tuple[bool, str]: (can_add, message)
            - can_add: True if can add more characters, False if limit reached
            - message: Descriptive message about the limit
    
    Examples:
        >>> can_add, msg = check_character_limit(45)
        >>> if not can_add:
        >>>     print(msg)
        Character limit reached! Your license allows 50 characters. Upgrade to add more.
    """
    features = get_license_features()
    max_characters = features.get('max_characters', 10)
    tier = features.get('tier', 'FREE')
    
    # UNLIMITED tier check
    if max_characters >= 999999 or tier == 'UNLIMITED':
        return True, f"Unlimited characters (Current: {current_count})"
    
    # Check if limit reached
    if current_count >= max_characters:
        return False, (
            f"Character limit reached!\n\n"
            f"Your {tier} license allows {max_characters} characters.\n"
            f"Current count: {current_count}/{max_characters}\n\n"
            f"Upgrade your license to add more characters:\n"
            f"  • BASIC (5 profiles): 25 characters\n"
            f"  • PROFESSIONAL (10 profiles): 50 characters\n"
            f"  • ULTIMATE (20 profiles): 100 characters\n"
            f"  • UNLIMITED: No limits\n\n"
            f"Contact: Zalo 0789.535.888"
        )
    
    # Still have room
    remaining = max_characters - current_count
    return True, f"Characters: {current_count}/{max_characters} (Remaining: {remaining})"


# ============================================================================
# ACTIVATION DIALOG - GUI for end users
# ============================================================================

def show_activation_dialog(parent=None) -> bool:
    """Show activation dialog"""
    try:
        hwid = get_hardware_id()
    except Exception as e:
        messagebox.showerror(
            "Hardware Detection Error", 
            f"Cannot get Hardware ID:\n\n{str(e)}\n\n"
            "Please run as administrator or contact Zalo: 0789.535.888"
        )
        return False
    
    dialog = tk.Toplevel(parent) if parent else tk.Tk()
    dialog.title("Sora 2 AI - Software Activation")
    dialog.geometry("700x550")
    dialog.resizable(False, False)
    
    # Center window
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
    y = (dialog.winfo_screenheight() // 2) - (550 // 2)
    dialog.geometry(f"700x550+{x}+{y}")
    
    if parent:
        dialog.transient(parent)
        dialog.grab_set()
    
    activated = [False]
    
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill="both", expand=True)
    
    # Header
    ttk.Label(
        main_frame, 
        text="Sora 2 AI Video Generator - Activation", 
        font=("Segoe UI", 14, "bold")
    ).pack(pady=(0, 10))
    
    ttk.Label(
        main_frame,
        text="Trần Nguyên - Zalo: 0789.535.888",
        font=("Segoe UI", 10),
        foreground="blue"
    ).pack(pady=(0, 20))
    
    # Hardware ID Section
    hwid_frame = ttk.LabelFrame(main_frame, text="📋 Step 1: Your Hardware ID", padding=10)
    hwid_frame.pack(fill="x", pady=(0, 10))
    
    ttk.Label(
        hwid_frame, 
        text="Copy this Hardware ID and send to: Zalo 0789.535.888"
    ).pack(anchor="w")
    
    hwid_text = tk.Text(hwid_frame, height=3, wrap=tk.WORD, font=("Courier", 9))
    hwid_text.pack(fill="x", pady=5)
    hwid_text.insert("1.0", hwid)
    hwid_text.config(state="disabled", bg="#f0f0f0")
    
    def copy_hwid():
        dialog.clipboard_clear()
        dialog.clipboard_append(hwid)
        messagebox.showinfo("Copied", "✅ Hardware ID copied to clipboard!")
    
    ttk.Button(
        hwid_frame, 
        text="📋 Copy Hardware ID", 
        command=copy_hwid
    ).pack(pady=5)
    
    # License Key Section
    key_frame = ttk.LabelFrame(main_frame, text="🔑 Step 2: Enter License Key", padding=10)
    key_frame.pack(fill="x", pady=(0, 10))
    
    ttk.Label(
        key_frame, 
        text="Paste license key received from Zalo: 0789.535.888"
    ).pack(anchor="w")
    
    key_entry = ttk.Entry(key_frame, font=("Courier", 10))
    key_entry.pack(fill="x", pady=5)
    
    status_label = ttk.Label(key_frame, text="", foreground="gray")
    status_label.pack(pady=5)
    
    def activate():
        license_key = key_entry.get().strip()
        
        if not license_key:
            messagebox.showwarning("Warning", "⚠️ Please enter license key")
            return
        
        is_valid, message = validate_license_key(hwid, license_key)
        
        if is_valid:
            if save_license(license_key):
                status_label.config(text=f"✅ {message}", foreground="green")
                messagebox.showinfo(
                    "Activation Successful", 
                    f"✅ Activation successful!\n\n{message}\n\n"
                    "You can now use Sora 2 AI Video Generator."
                )
                activated[0] = True
                dialog.destroy()
            else:
                messagebox.showerror("Error", "❌ Failed to save license file")
        else:
            status_label.config(text=f"❌ {message}", foreground="red")
            messagebox.showerror("Activation Failed", f"❌ {message}")
    
    btn_frame = ttk.Frame(key_frame)
    btn_frame.pack(fill="x", pady=5)
    
    ttk.Button(
        btn_frame, 
        text="✅ Activate", 
        command=activate
    ).pack(side="left", padx=5)
    
    ttk.Button(
        btn_frame, 
        text="❌ Exit", 
        command=lambda: dialog.destroy()
    ).pack(side="left")
    
    # Information Section
    info_frame = ttk.LabelFrame(main_frame, text="ℹ️ Information", padding=10)
    info_frame.pack(fill="both", expand=True, pady=(0, 10))
    
    info_text = tk.Text(info_frame, height=10, wrap=tk.WORD, font=("Segoe UI", 9))
    info_text.pack(fill="both", expand=True)
    info_text.insert("1.0", 
        "📖 HOW TO ACTIVATE:\n\n"
        "1. Click '📋 Copy Hardware ID' button above\n"
        "2. Contact Zalo: 0789.535.888 (Trần Nguyên)\n"
        "3. Send your Hardware ID\n"
        "4. Receive License Key\n"
        "5. Paste License Key into the field above\n"
        "6. Click '✅ Activate' button\n\n"
        "⚠️ IMPORTANT NOTES:\n"
        "• License is tied to THIS computer's hardware\n"
        "• If you change major hardware, contact for new key\n"
        "• Keep your license key safe for reinstallation\n"
        "• One license = One computer only\n\n"
        "📧 SUPPORT:\n"
        "Zalo: 0789.535.888 - Trần Nguyên"
    )
    info_text.config(state="disabled", bg="#f9f9f9")
    
    dialog.protocol("WM_DELETE_WINDOW", lambda: dialog.destroy())
    
    dialog.mainloop()
    
    return activated[0]

# ============================================================================
# ✅ KEY GENERATOR TOOL (ENHANCED VERSION)
# ============================================================================

def create_key_generator():
    """Developer tool to generate license keys (ENHANCED WITH CUSTOM DAYS + REMAINING DAYS)"""
    root = tk.Tk()
    root.title("Sora 2 AI - License Key Generator (ENHANCED)")
    root.geometry("1100x900")  # ✅ FIXED: Tăng width lên 1100 để không bị tràn text
    root.resizable(True, True)  # ✅ FIXED: Cho phép resize window
    
    # Center window
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (1100 // 2)
    y = (root.winfo_screenheight() // 2) - (900 // 2)
    root.geometry(f"1100x900+{x}+{y}")
    
    # ✅ FIXED: Add scrollbar support
    main_canvas = tk.Canvas(root, borderwidth=0, background="#f0f0f0")
    main_frame = ttk.Frame(main_canvas, padding=20)
    vsb = ttk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
    main_canvas.configure(yscrollcommand=vsb.set)
    
    vsb.pack(side="right", fill="y")
    main_canvas.pack(side="left", fill="both", expand=True)
    main_canvas.create_window((0, 0), window=main_frame, anchor="nw")
    
    def on_frame_configure(event):
        main_canvas.configure(scrollregion=main_canvas.bbox("all"))
    
    main_frame.bind("<Configure>", on_frame_configure)
    
    # Header
    ttk.Label(
        main_frame, 
        text="🔑 Sora 2 AI - License Key Generator (ENHANCED)", 
        font=("Segoe UI", 14, "bold")
    ).pack(pady=(0, 10))
    
    ttk.Label(
        main_frame,
        text="⚠️ DEVELOPER TOOL - Trần Nguyên - Zalo: 0789.535.888",
        font=("Segoe UI", 10, "bold"),
        foreground="red"
    ).pack(pady=(0, 20))
    
    # Input Section
    input_frame = ttk.LabelFrame(main_frame, text="🔐 Generate License Key", padding=15)
    input_frame.pack(fill="x", pady=(0, 10))
    
    # Hardware ID input
    ttk.Label(
        input_frame, 
        text="Customer Hardware ID:", 
        font=("Segoe UI", 10, "bold")
    ).grid(row=0, column=0, sticky="w", pady=5)
    
    hwid_entry = ttk.Entry(input_frame, width=90, font=("Courier", 9))  # ✅ FIXED: Width 70→90
    hwid_entry.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
    
    # ✅ License Tier Selection
    ttk.Label(
        input_frame, 
        text="License Tier:", 
        font=("Segoe UI", 10, "bold")
    ).grid(row=2, column=0, sticky="w", pady=(10, 5))
    
    tier_frame = ttk.Frame(input_frame)
    tier_frame.grid(row=3, column=0, columnspan=4, sticky="w", pady=5)
    
    tier_var = tk.StringVar(value="BASIC")
    
    tiers = [
        ("FREE - 1 profile (30 videos/day)", "FREE"),
        ("BASIC - 5 profiles (150 videos/day) - $49/tháng", "BASIC"),
        ("PROFESSIONAL - 10 profiles (300 videos/day) - $99/tháng", "PROFESSIONAL"),
        ("ENTERPRISE - 15 profiles (450 videos/day) - $199/tháng", "ENTERPRISE"),
        ("ULTIMATE - 20 profiles (600 videos/day) - $399/tháng", "ULTIMATE"),
        ("UNLIMITED - Không giới hạn - $999/tháng", "UNLIMITED")
    ]
    
    for i, (label, value) in enumerate(tiers):
        ttk.Radiobutton(
            tier_frame, 
            text=label, 
            variable=tier_var, 
            value=value
        ).grid(row=i//2, column=i%2, padx=10, pady=3, sticky="w")
    
    # License Period Selection
    ttk.Label(
        input_frame, 
        text="License Period:", 
        font=("Segoe UI", 10, "bold")
    ).grid(row=4, column=0, sticky="w", pady=(10, 5))
    
    period_frame = ttk.Frame(input_frame)
    period_frame.grid(row=5, column=0, columnspan=4, sticky="w", pady=5)
    
    period_var = tk.StringVar(value="1_YEAR")
    
    periods = [
        ("1 Day (Test)", "1_DAY"),
        ("1 Week (Trial)", "1_WEEK"),
        ("1 Month", "1_MONTH"),
        ("2 Months", "2_MONTHS"),
        ("3 Months", "3_MONTHS"),
        ("6 Months", "6_MONTHS"),
        ("1 Year", "1_YEAR"),
        ("2 Years", "2_YEARS"),
        ("Lifetime", "LIFETIME"),
        ("✅ Custom Days", "CUSTOM")  # ✅ NEW OPTION
    ]
    
    for i, (label, value) in enumerate(periods):
        ttk.Radiobutton(
            period_frame, 
            text=label, 
            variable=period_var, 
            value=value
        ).grid(row=i//3, column=i%3, padx=10, pady=3, sticky="w")
    
    # ============================================================================
    # ✅ NEW: CUSTOM DAYS INPUT
    # ============================================================================
    custom_days_frame = ttk.LabelFrame(input_frame, text="✅ Custom Days (Chỉ dùng khi chọn 'Custom Days' ở trên)", padding=10)
    custom_days_frame.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(10, 5))
    
    ttk.Label(
        custom_days_frame,
        text="Nhập số ngày tùy ý:",
        font=("Segoe UI", 9)
    ).grid(row=0, column=0, sticky="w", padx=5)
    
    custom_days_entry = ttk.Entry(custom_days_frame, width=20, font=("Arial", 10))
    custom_days_entry.grid(row=0, column=1, padx=5)
    
    ttk.Label(
        custom_days_frame,
        text="(ví dụ: 14, 23, 45, 100, 365,...)",
        font=("Segoe UI", 8),
        foreground="gray"
    ).grid(row=0, column=2, sticky="w", padx=5)
    
    # ============================================================================
    # ✅ NEW: REMAINING DAYS EXTENSION (for HWID transfer)
    # ============================================================================
    remaining_days_frame = ttk.LabelFrame(input_frame, text="✅ Remaining Days Extension (Chuyển HWID giữ số ngày)", padding=10)
    remaining_days_frame.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(10, 5))
    
    ttk.Label(
        remaining_days_frame,
        text="Old License Key (để tính số ngày còn lại):",
        font=("Segoe UI", 9, "bold")
    ).grid(row=0, column=0, sticky="w", pady=5)
    
    old_license_entry = ttk.Entry(remaining_days_frame, width=90, font=("Courier", 9))  # ✅ FIXED: Width 70→90
    old_license_entry.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
    
    remaining_days_label = ttk.Label(
        remaining_days_frame,
        text="Số ngày còn lại sẽ được tự động tính",
        font=("Segoe UI", 8),
        foreground="blue"
    )
    remaining_days_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=3)
    
    def calculate_remaining():
        """Calculate remaining days from old license key"""
        old_key = old_license_entry.get().strip()
        if not old_key:
            remaining_days_label.config(
                text="⚠️ Chưa nhập Old License Key",
                foreground="red"
            )
            return
        
        remaining = get_remaining_days_from_license(old_key)
        
        if remaining is None:
            remaining_days_label.config(
                text="❌ Không thể tính remaining days (key không hợp lệ)",
                foreground="red"
            )
        elif remaining == -1:
            remaining_days_label.config(
                text="✅ Remaining: LIFETIME (không hết hạn)",
                foreground="green"
            )
        elif remaining <= 0:
            remaining_days_label.config(
                text="❌ License đã HẾT HẠN (0 ngày)",
                foreground="red"
            )
        else:
            remaining_days_label.config(
                text=f"✅ Remaining: {remaining} ngày",
                foreground="green"
            )
    
    ttk.Button(
        remaining_days_frame,
        text="🔄 Calculate Remaining Days",
        command=calculate_remaining
    ).grid(row=3, column=0, pady=5, sticky="w")
    
    ttk.Label(
        remaining_days_frame,
        text="💡 Cách dùng: Paste old license key → Click Calculate → Click Generate Key",
        font=("Segoe UI", 8, "italic"),
        foreground="gray"
    ).grid(row=4, column=0, columnspan=3, sticky="w", padx=5, pady=3)
    
    # ✅ FIXED: Configure grid weights để responsive
    input_frame.columnconfigure(0, weight=1)
    input_frame.columnconfigure(1, weight=1)
    input_frame.columnconfigure(2, weight=1)
    input_frame.columnconfigure(3, weight=1)
    custom_days_frame.columnconfigure(0, weight=0)
    custom_days_frame.columnconfigure(1, weight=0)
    custom_days_frame.columnconfigure(2, weight=1)
    remaining_days_frame.columnconfigure(0, weight=1)
    
    # Output Section
    output_frame = ttk.LabelFrame(main_frame, text="📜 Generated License Keys History", padding=10)
    output_frame.pack(fill="both", expand=True, pady=(0, 10))
    
    output_text = scrolledtext.ScrolledText(output_frame, height=15, font=("Courier", 9), wrap=tk.WORD)  # ✅ FIXED: Add word wrap
    output_text.pack(fill="both", expand=True)
    
    def generate():
        hwid = hwid_entry.get().strip()
        
        if not hwid:
            messagebox.showwarning("Warning", "⚠️ Please enter Customer Hardware ID")
            return
        
        if len(hwid.replace("-", "")) != 32:
            messagebox.showwarning(
                "Warning", 
                "⚠️ Invalid Hardware ID format\n\n"
                "Expected format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"
            )
            return
        
        try:
            period_key = period_var.get()
            tier = tier_var.get()
            
            # ============================================================================
            # ✅ NEW: HANDLE CUSTOM DAYS + REMAINING DAYS
            # ============================================================================
            
            custom_days = None
            remaining_days = None
            
            # Priority 1: Check if using REMAINING DAYS EXTENSION
            old_key = old_license_entry.get().strip()
            if old_key:
                remaining_days = get_remaining_days_from_license(old_key)
                
                if remaining_days is None:
                    messagebox.showerror(
                        "Error",
                        "❌ Không thể tính remaining days từ Old License Key\n\n"
                        "Key không hợp lệ hoặc bị lỗi format"
                    )
                    return
                
                if remaining_days == 0:
                    messagebox.showerror(
                        "Error",
                        "❌ Old License Key đã HẾT HẠN\n\n"
                        "Không thể tạo key mới với 0 ngày"
                    )
                    return
                
                # Generate with remaining days
                license_key = generate_license_key(
                    hwid, 
                    period_key="CUSTOM",  # Use CUSTOM mode
                    tier=tier,
                    remaining_days=remaining_days
                )
                
                if remaining_days == -1:
                    period_display = "LIFETIME (from old key)"
                    expiry_display = "Never expires"
                else:
                    expiry_date = datetime.now() + timedelta(days=remaining_days)
                    period_display = f"{remaining_days} days (transferred from old key)"
                    expiry_display = expiry_date.strftime("%Y-%m-%d")
            
            # Priority 2: Check if using CUSTOM DAYS
            elif period_key == "CUSTOM":
                custom_days_str = custom_days_entry.get().strip()
                
                if not custom_days_str:
                    messagebox.showwarning(
                        "Warning",
                        "⚠️ Vui lòng nhập số ngày vào ô 'Custom Days'\n\n"
                        "Hoặc chọn period khác (1 Month, 1 Year, etc.)"
                    )
                    return
                
                try:
                    custom_days = int(custom_days_str)
                    
                    if custom_days <= 0:
                        messagebox.showerror(
                            "Error",
                            "❌ Custom Days phải là số nguyên dương (> 0)"
                        )
                        return
                    
                    # Generate with custom days
                    license_key = generate_license_key(
                        hwid, 
                        period_key="CUSTOM",
                        tier=tier,
                        custom_days=custom_days
                    )
                    
                    expiry_date = datetime.now() + timedelta(days=custom_days)
                    period_display = f"{custom_days} days (custom)"
                    expiry_display = expiry_date.strftime("%Y-%m-%d")
                
                except ValueError:
                    messagebox.showerror(
                        "Error",
                        "❌ Custom Days phải là SỐ NGUYÊN\n\n"
                        f"Bạn nhập: '{custom_days_str}'"
                    )
                    return
            
            # Priority 3: STANDARD PERIODS
            else:
                license_key = generate_license_key(hwid, period_key, tier)
                
                days = LICENSE_PERIODS[period_key]
                if days == -1:
                    period_display = "Lifetime (No expiration)"
                    expiry_display = "Never expires"
                else:
                    expiry_date = datetime.now() + timedelta(days=days)
                    period_display = f"{days} days"
                    expiry_display = expiry_date.strftime("%Y-%m-%d")
            
            # Get tier info
            tier_info = LICENSE_TIERS.get(tier, {})
            tier_desc = tier_info.get('description', '')
            max_profiles = tier_info.get('max_profiles', 5)
            max_videos = tier_info.get('max_videos_per_day', 150)
            
            # Log to output
            output_text.insert(tk.END, "="*80 + "\n")
            output_text.insert(tk.END, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            output_text.insert(tk.END, f"Customer HWID: {hwid}\n")
            output_text.insert(tk.END, f"License Tier: {tier}\n")
            output_text.insert(tk.END, f"  - {tier_desc}\n")
            output_text.insert(tk.END, f"  - Max Profiles: {max_profiles}\n")
            output_text.insert(tk.END, f"  - Max Videos/Day: {max_videos}\n")
            output_text.insert(tk.END, f"License Period: {period_display}\n")
            output_text.insert(tk.END, f"Expiry Date: {expiry_display}\n")
            
            # ✅ Show if using custom days or remaining days
            if remaining_days is not None:
                output_text.insert(tk.END, f"✅ MODE: Remaining Days Extension (Old Key: {old_key[:20]}...)\n")
            elif custom_days is not None:
                output_text.insert(tk.END, f"✅ MODE: Custom Days ({custom_days} days)\n")
            
            output_text.insert(tk.END, f"\n🔑 LICENSE KEY:\n{license_key}\n")
            output_text.insert(tk.END, "="*80 + "\n\n")
            output_text.see(tk.END)
            
            # Copy to clipboard
            root.clipboard_clear()
            root.clipboard_append(license_key)
            
            messagebox.showinfo(
                "Success", 
                f"✅ License key generated and copied!\n\n"
                f"Tier: {tier}\n"
                f"Profiles: {max_profiles}\n"
                f"Videos/Day: {max_videos}\n"
                f"Period: {period_display}\n"
                f"Expires: {expiry_display}\n\n"
                f"Key: {license_key}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"❌ Generation failed:\n\n{str(e)}")
    
    def clear_log():
        if messagebox.askyesno("Confirm", "🗑️ Clear all generated keys history?"):
            output_text.delete("1.0", tk.END)
    
    def save_log():
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sora_license_keys_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(output_text.get("1.0", tk.END))
            
            messagebox.showinfo("Saved", f"💾 Log saved to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Error", f"❌ Failed to save:\n\n{str(e)}")
    
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill="x")
    
    ttk.Button(btn_frame, text="🔑 Generate Key", command=generate).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="🗑️ Clear Log", command=clear_log).pack(side="left", padx=5)
    ttk.Button(btn_frame, text="💾 Save Log", command=save_log).pack(side="left", padx=5)
    
    root.mainloop()

# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "keygen":
            create_key_generator()
        
        elif command == "test":
            print("="*60)
            print("SORA 2 AI LICENSE SYSTEM - TEST MODE (ENHANCED)")
            print("="*60)
            
            try:
                hwid = get_hardware_id()
                print(f"\n✅ Hardware ID: {hwid}")
            except Exception as e:
                print(f"\n❌ Hardware ID Error: {e}")
                sys.exit(1)
            
            is_activated, message = check_activation()
            
            print(f"\n{'='*60}")
            if is_activated:
                print(f"Status: ✅ ACTIVATED")
                print(f"  {message}")
            else:
                print(f"Status: ❌ NOT ACTIVATED")
                print(f"  {message}")
            print("="*60)
            
            if not is_activated:
                if messagebox.askyesno(
                    "Activation Required", 
                    "Software is not activated.\n\nOpen activation dialog?"
                ):
                    show_activation_dialog()
        
        elif command == "genhwid":
            try:
                hwid = get_hardware_id()
                print("="*60)
                print("HARDWARE ID:")
                print("="*60)
                print(hwid)
                print("="*60)
            except Exception as e:
                print(f"❌ Error: {e}")
        
        else:
            print(f"❌ Unknown command: {command}")
            print("\nAvailable commands:")
            print("  keygen  - Open key generator")
            print("  test    - Test activation status")
            print("  genhwid - Generate hardware ID")
    
    else:
        print("="*60)
        print("Sora 2 AI - License System (ENHANCED)")
        print("Trần Nguyên - Zalo: 0789.535.888")
        print("="*60)
        print("\n✅ NEW FEATURES:")
        print("  • Custom Days - Nhập số ngày bất kỳ (14, 23, 100,...)")
        print("  • Remaining Days Extension - Giữ số ngày khi đổi HWID")
        print("\nUsage:")
        print("  python sora2_license_system.py keygen   - Open key generator")
        print("  python sora2_license_system.py test     - Test activation")
        print("  python sora2_license_system.py genhwid  - Get hardware ID")
