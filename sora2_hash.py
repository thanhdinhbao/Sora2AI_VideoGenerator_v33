#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora 2 - Executable Hash Storage
Expected hash for integrity verification
Author: Trần Nguyên - Zalo: 0789.535.888
"""

EXPECTED_EXE_HASH = "a34c39ce22aa554ad66c067b2a07530a1d99950a9ba01aef408335bdbba566d4"

__version__ = "1.0.0"
__author__ = "Trần Nguyên"

if __name__ == "__main__":
    print("Sora 2 Hash Configuration")
    print(f"Expected Hash: {EXPECTED_EXE_HASH if EXPECTED_EXE_HASH else '(Not set)'}")