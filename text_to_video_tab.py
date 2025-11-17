#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Text-to-Video Tab Module - FIXED VERSION
========================================
Tách riêng để dễ maintain và tích hợp vào App chính

CHANGELOG v28_FIXED:
-------------------
✅ FIXED: Added _generation_thread_wrapper() method (like Image-to-Video)
✅ FIXED: Profile rotation logic - check availability per video
✅ FIXED: Increment profile usage after each successful video
✅ FIXED: API client initialization for POST mode per profile
✅ FIXED: Proper state management and cleanup in finally block
✅ DEPRECATED: Old do_batch_generation() method removed

KEY IMPROVEMENTS:
----------------
1. Profile Management:
   - Check available profile before each video
   - Auto-switch when quota reached
   - Increment usage correctly after success
   
2. Token Handling:
   - Proper token retrieval per profile
   - API client init only when profile changes
   - Better error messages for missing tokens
   
3. State Management:
   - Proper cleanup in finally block
   - Thread-safe UI updates
   - Stop signal handling

4. Consistency:
   - Now matches Image-to-Video tab logic 100%
   - Same methods, same flow, same error handling
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import threading
import time
import os
import logging
from pathlib import Path
from language_config import lang_manager

# ✅ THÊM 1 DÒNG NÀY
from watermark_free_downloader import PostURLExtractor, WatermarkFreeIntegration
from video_merger import VideoMergerIntegration
logger = logging.getLogger(__name__)


# ============================================================================
# AUTO-CLOSE MESSAGEBOX - COPIED FROM MAIN
# ============================================================================
# AutoCloseMessageBox removed - using standard messagebox
class TextToVideoTab:
    """Text-to-Video Tab - 100% API with Concurrent Mode"""
    
    def __init__(self, parent_frame, app_instance, lang):
        """
        Args:
            parent_frame: ttk.Frame - container cho tab
            app_instance: App - instance của App chính để access browser, log, etc.
        """
        self.frame = parent_frame
        self.app = app_instance
        self.lang = lang
        self.prompts_t2v = []  # Danh sách prompts riêng cho T2V

        self.build_ui()
        
    def build_ui(self):
        """Xây dựng UI cho tab Text-to-Video với scrollable left panel"""
        main_frame = ttk.Frame(self.frame)
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # ========================================================================
        # LEFT PANEL - SCROLLABLE CONTAINER
        # ========================================================================
        left_container = ttk.Frame(main_frame, width=420)
        left_container.pack(side="left", fill="both", padx=(0, 8))
        left_container.pack_propagate(False)
        
        # Canvas for scrolling
        self.canvas_left_t2v = tk.Canvas(left_container, highlightthickness=0)
        scrollbar_left = ttk.Scrollbar(left_container, orient="vertical", 
                                       command=self.canvas_left_t2v.yview)
        
        # Scrollable frame inside canvas
        self.scrollable_left_frame = ttk.Frame(self.canvas_left_t2v)
        
        # Configure canvas
        self.canvas_left_t2v.configure(yscrollcommand=scrollbar_left.set)
        
        # Pack scrollbar and canvas
        scrollbar_left.pack(side="right", fill="y")
        self.canvas_left_t2v.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas
        self.canvas_window_left = self.canvas_left_t2v.create_window(
            (0, 0), 
            window=self.scrollable_left_frame, 
            anchor="nw"
        )
        
        # Configure scrolling
        def configure_scroll_region(event=None):
            self.canvas_left_t2v.configure(scrollregion=self.canvas_left_t2v.bbox("all"))
        
        def configure_canvas_width(event):
            canvas_width = event.width
            self.canvas_left_t2v.itemconfig(self.canvas_window_left, width=canvas_width)
        
        self.scrollable_left_frame.bind("<Configure>", configure_scroll_region)
        self.canvas_left_t2v.bind("<Configure>", configure_canvas_width)
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            self.canvas_left_t2v.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                bind_mousewheel(child)
        
        bind_mousewheel(self.scrollable_left_frame)
        self.canvas_left_t2v.bind("<MouseWheel>", on_mousewheel)
        
        # ========================================================================
        # NỘI DUNG LEFT PANEL (Tất cả thêm vào scrollable_left_frame)
        # ========================================================================
        
        # ===== Settings Frame =====
        settings_frame = ttk.LabelFrame(self.scrollable_left_frame, 
                                        text="⚙️ " + self.lang.get('generation_settings'), 
                                        padding=10)
        settings_frame.pack(fill="x", pady=(0, 8), padx=5)

        # Orientation
        ttk.Label(settings_frame, text=self.lang.get('orientation') + ":").grid(
            row=0, column=0, sticky="w", pady=5)
        self.cmb_orientation_t2v = ttk.Combobox(
            settings_frame, 
            values=["landscape", "portrait"], 
            state="readonly", 
            width=30
        )
        self.cmb_orientation_t2v.grid(row=1, column=0, sticky="ew", pady=5)
        self.cmb_orientation_t2v.set("landscape")

        # Duration
        ttk.Label(settings_frame, text=self.lang.get('duration') + ":").grid(
            row=2, column=0, sticky="w", pady=5)
        self.cmb_duration_t2v = ttk.Combobox(
            settings_frame,
            values=["10s", "15s"],
            state="readonly",
            width=30
        )
        self.cmb_duration_t2v.grid(row=3, column=0, sticky="ew", pady=5)
        self.cmb_duration_t2v.set("10s")

        settings_frame.columnconfigure(0, weight=1)
        
        # ===== Draft Action Frame =====
        draft_frame = ttk.LabelFrame(self.scrollable_left_frame, 
                                     text="📤 " + self.lang.get('after_download'), 
                                     padding=10)
        draft_frame.pack(fill="x", pady=(0, 8), padx=5)
        
        ttk.Label(draft_frame, text=self.lang.get('draft_action') + ":").grid(
            row=0, column=0, sticky="w", pady=(0, 5))
        
        self.draft_action_t2v = tk.StringVar(value="delete")
        
        ttk.Radiobutton(
            draft_frame,
            text="🗑️ " + self.lang.get('delete_draft'),
            variable=self.draft_action_t2v,
            value="delete"
        ).grid(row=1, column=0, sticky="w", pady=2)
        
        ttk.Radiobutton(
            draft_frame,
            text="📤 " + self.lang.get('post_to_public'),
            variable=self.draft_action_t2v,
            value="post"
        ).grid(row=2, column=0, sticky="w", pady=2)
        
        ttk.Label(
            draft_frame,
            text="💡 " + self.lang.get('draft_action_note'),
            font=("Segoe UI", 8),
            foreground="gray"
        ).grid(row=3, column=0, sticky="w", pady=(5, 0))
        
        draft_frame.columnconfigure(0, weight=1)

        # ===== Watermark-Free Download =====
        ttk.Separator(draft_frame, orient="horizontal").grid(
            row=4, column=0, sticky="ew", pady=10)

        self.var_enable_wf_download_t2v = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            draft_frame,
            text=self.lang.get('download_no_watermark'),
            variable=self.var_enable_wf_download_t2v,
            command=self.toggle_wf_download_t2v
        ).grid(row=5, column=0, sticky="w", pady=5)

        wf_info_t2v = (
            "Only works with 'POST to Public' mode\n"
            "Videos saved to: ./downloads_no_watermark"
        )
        ttk.Label(
            draft_frame,
            text=wf_info_t2v,
            font=("Arial", 8),
            foreground="gray",
            wraplength=280,
            justify="left"
        ).grid(row=6, column=0, sticky="w", pady=(5, 0))

        self.lbl_wf_stats_t2v = ttk.Label(
            draft_frame,
            text=self.lang.get('wf_stats_initial'),
            font=("Arial", 8),
            foreground="blue"
        )
        self.lbl_wf_stats_t2v.grid(row=7, column=0, sticky="w", pady=(5, 0))

        def update_wf_stats_t2v():
            if hasattr(self.app, 'wf_integration'):
                stats = self.app.wf_integration.get_stats()
                self.lbl_wf_stats_t2v.config(
                    text=f"Stats: {stats['total']} total | "
                         f"{stats['completed']} completed | "
                         f"{stats['failed']} failed"
                )
            self.frame.after(2000, update_wf_stats_t2v)

        update_wf_stats_t2v()

        # ===== Video Merger =====
        ttk.Separator(draft_frame, orient="horizontal").grid(
            row=8, column=0, sticky="ew", pady=10)

        self.var_enable_merge_t2v = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            draft_frame,
            text="🎬 " + self.lang.get('enable_video_merger'),
            variable=self.var_enable_merge_t2v,
            command=self.toggle_video_merger_t2v
        ).grid(row=9, column=0, sticky="w", pady=5)

        batch_frame = ttk.Frame(draft_frame)
        batch_frame.grid(row=10, column=0, sticky="w", pady=5, padx=20)
        ttk.Label(batch_frame, text=self.lang.get('batch_size') + ":").pack(
            side="left", padx=(0, 5))
        self.var_merge_batch_size_t2v = tk.IntVar(value=2)
        ttk.Spinbox(
            batch_frame,
            from_=2,
            to=10,
            textvariable=self.var_merge_batch_size_t2v,
            width=5
        ).pack(side="left")
        ttk.Label(batch_frame, text=self.lang.get('videos_per_batch')).pack(
            side="left", padx=(5, 0))

        merger_info_t2v = (
            "Auto-merge downloaded videos\n"
            "Output: ./downloads_merged"
        )
        ttk.Label(
            draft_frame,
            text=merger_info_t2v,
            font=("Arial", 8),
            foreground="gray",
            wraplength=280,
            justify="left"
        ).grid(row=11, column=0, sticky="w", pady=(5, 0))

        self.lbl_merger_stats_t2v = ttk.Label(
            draft_frame,
            text=self.lang.get('merger_disabled'),
            font=("Arial", 9, "bold"),
            foreground="purple"
        )
        self.lbl_merger_stats_t2v.grid(row=12, column=0, sticky="w", pady=(5, 0))

        # ===== Concurrent Mode =====
        ttk.Separator(draft_frame, orient="horizontal").grid(
            row=13, column=0, sticky="ew", pady=10)

        self.var_concurrent_mode_t2v = tk.BooleanVar(value=True)  # ✅ Mặc định TRUE
        ttk.Checkbutton(
            draft_frame,
            text="⚡ Enable Concurrent Mode (2 workers parallel)",
            variable=self.var_concurrent_mode_t2v,
            command=self._on_concurrent_toggle_t2v
        ).grid(row=14, column=0, sticky="w", pady=5)

        # ✅ BỎ WORKER FRAME - CỐ ĐỊNH 2 WORKERS
        self.var_concurrent_workers_t2v = tk.IntVar(value=2)  # Cố định = 2

        ttk.Label(
            draft_frame,
            text="✅ Faster but needs more CPU/RAM",
            font=("Arial", 8),
            foreground="green"
        ).grid(row=16, column=0, sticky="w", pady=5)


        def update_merger_stats_t2v():
            if hasattr(self.app, 'video_merger') and self.app.video_merger:
                stats = self.app.video_merger.get_stats()
                buffer_size = len(self.app.video_merger.video_buffer)
                batch_size = self.var_merge_batch_size_t2v.get()
                
                self.lbl_merger_stats_t2v.config(
                    text=f"Merger: {stats['total']} batches | "
                         f"{stats['completed']} merged | "
                         f"{stats['pending']} pending | "
                         f"Buffer: {buffer_size}/{batch_size}"
                )
            else:
                self.lbl_merger_stats_t2v.config(
                    text=self.lang.get('merger_not_initialized')
                )
            
            self.frame.after(2000, update_merger_stats_t2v)

        update_merger_stats_t2v()

        # ===== Prompts Frame =====
        prompt_frame = ttk.LabelFrame(self.scrollable_left_frame, 
                                      text="📝 " + self.lang.get('motion_prompts'), 
                                      padding=10)
        prompt_frame.pack(fill="both", expand=True, pady=(0, 8), padx=5)
        
        # Import buttons
        import_row = ttk.Frame(prompt_frame)
        import_row.pack(fill="x", pady=(0, 5))

        ttk.Button(import_row, text="📄 " + self.lang.get('import_txt'), 
                  command=self.import_prompts_txt, width=12).pack(side="left", padx=2)

        ttk.Button(import_row, text="📊 " + self.lang.get('import_excel'), 
                  command=self.import_prompts_excel, width=12).pack(side="left", padx=2)

        ttk.Button(import_row, text="📋 " + self.lang.get('import_json'), 
                  command=self.import_prompts_json, width=12).pack(side="left", padx=2)
        
        # Text area
        self.txt_t2v_prompt = tk.Text(prompt_frame, height=10, wrap=tk.WORD, 
                                      font=("Segoe UI", 10))
        self.txt_t2v_prompt.pack(fill="both", expand=True, pady=(0, 10))
        self.app.txt_t2v_prompt = self.txt_t2v_prompt
        
        # Control buttons
        ctrl_frame = ttk.Frame(prompt_frame)
        ctrl_frame.pack(fill="x")
        
        ttk.Button(ctrl_frame, text=self.lang.get('import_to_queue'), 
                  command=self.import_to_queue).pack(side="left", padx=2)
        ttk.Button(ctrl_frame, text=self.lang.get('start_generation'),
                  style="Accent.TButton",
                  command=self.start_generation).pack(side="left", padx=2)
        self.btn_stop_t2v = ttk.Button(ctrl_frame, text=self.lang.get('stop'), 
                                       command=self.stop_generation_process,
                                       state="disabled")
        self.btn_stop_t2v.pack(side="left", padx=2)
        
        # ========================================================================
        # RIGHT PANEL (GIỮ NGUYÊN CODE CŨ)
        # ========================================================================
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side="right", fill="both", expand=True)
        
        # Table controls
        table_controls = ttk.Frame(right_panel)
        table_controls.pack(fill="x", pady=(0, 5))
        
        ttk.Button(table_controls, text=self.lang.get('select_all'), 
                  command=self.table_select_all).pack(side="left", padx=2)
        ttk.Button(table_controls, text=self.lang.get('deselect_all'), 
                  command=self.table_deselect_all).pack(side="left", padx=2)
        ttk.Button(table_controls, text=self.lang.get('delete_selected'), 
                  command=self.table_delete_selected).pack(side="left", padx=2)
        ttk.Button(table_controls, text=self.lang.get('clear_all'), 
                  command=self.table_clear_all).pack(side="left", padx=2)
        
        # Canvas table
        table_container = ttk.Frame(right_panel)
        table_container.pack(fill="both", expand=True, pady=(0, 8))
        
        self.canvas_t2v = tk.Canvas(table_container, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(table_container, orient="vertical", 
                                 command=self.canvas_t2v.yview)
        self.table_frame_t2v = ttk.Frame(self.canvas_t2v)
        
        self.canvas_t2v.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas_t2v.pack(side="left", fill="both", expand=True)
        
        self.canvas_window_t2v = self.canvas_t2v.create_window(
            (0, 0), window=self.table_frame_t2v, anchor="nw"
        )
        
        def configure_canvas(event):
            self.canvas_t2v.configure(scrollregion=self.canvas_t2v.bbox("all"))
            self.canvas_t2v.itemconfig(self.canvas_window_t2v, width=event.width)
        
        self.canvas_t2v.bind("<Configure>", configure_canvas)
        self.table_frame_t2v.bind("<Configure>", 
            lambda e: self.canvas_t2v.configure(scrollregion=self.canvas_t2v.bbox("all")))
        self.canvas_t2v.bind("<MouseWheel>", 
            lambda e: self.canvas_t2v.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Table header
        header = ttk.Frame(self.table_frame_t2v, relief="raised", borderwidth=1)
        header.pack(fill="x", pady=(0, 2))
        header.columnconfigure(2, weight=1)
        
        ttk.Label(header, text="[ ]", width=3, anchor="center", 
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, padx=5, pady=8)
        ttk.Label(header, text=self.lang.get('no'), width=5, anchor="center", 
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=1, padx=5, pady=8)
        ttk.Label(header, text=self.lang.get('prompt_column'), anchor="w", 
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=2, padx=10, pady=8, sticky="ew")
        ttk.Label(header, text=self.lang.get('status_column'), anchor="center", 
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=3, padx=5, pady=8)
        ttk.Label(header, text=self.lang.get('video_preview'), anchor="center", 
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=4, padx=5, pady=8)
        ttk.Label(header, text=self.lang.get('actions_column'), width=10, anchor="center", 
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=5, padx=5, pady=8)
        
        # Generation log
        log_frame = ttk.LabelFrame(right_panel, text="📋 " + self.lang.get('generation_log'), 
                                  padding=10)
        log_frame.pack(fill="x")
        
        self.log_text_t2v = ScrolledText(log_frame, height=6, font=("Consolas", 9))
        self.log_text_t2v.pack(fill="both", expand=True)
        self.log_text_t2v.tag_config("ok", foreground="green")
        self.log_text_t2v.tag_config("err", foreground="red")
        self.log_text_t2v.tag_config("info", foreground="blue")
    
    # ========================================================================
    # IMPORT METHODS
    # ========================================================================
    
    def import_prompts_txt(self):
        """Import prompts từ TXT - CHỈ HIỂN THỊ TRONG TEXT AREA"""
        filepath = filedialog.askopenfilename(
            title="Select TXT file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                prompts = [line.strip() for line in f if line.strip()]
            
            if prompts:
                # ✅ CHỈ ADD VÀO TEXT AREA - KHÔNG TỰ ĐỘNG ADD VÀO BẢNG
                current = self.txt_t2v_prompt.get("1.0", "end").strip()
                if current:
                    self.txt_t2v_prompt.insert("end", "\n" + "\n".join(prompts))
                else:
                    self.txt_t2v_prompt.insert("1.0", "\n".join(prompts))
                
                # ✅ THÔNG BÁO: CẦN BẤM "IMPORT TO QUEUE"
                messagebox.showinfo(
                    "Success", 
                    f"✅ Loaded {len(prompts)} prompts to text area\n\n"
                    f"📋 Please review and click 'Import to Queue' to add them to generation table"
                )
                
                self.log(f"📄 Loaded {len(prompts)} prompts from TXT (not added to queue yet)", "info")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file:\n{str(e)}")
    
    def import_prompts_excel(self):
        """Import prompts từ Excel - HỖ TRỢ SETTINGS RIÊNG CHO TỪNG VIDEO"""
        filepath = filedialog.askopenfilename(
            title="Select Excel file",
            filetypes=[("Excel files", "*.xlsx;*.xls"), ("All files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filepath)
            ws = wb.active
            
            # ✅ STORE EXCEL DATA với orientation + duration riêng
            self.excel_data_t2v = []  # [(prompt, orientation, duration), ...]
            
            prompts_only = []  # Chỉ prompts để hiển thị trong text area
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                
                # Column A: Prompt
                prompt = str(row[0]).strip()
                
                # Column B: Orientation (landscape/portrait)
                orientation = "landscape"
                if len(row) > 1 and row[1]:
                    orientation_str = str(row[1]).strip().lower()
                    if orientation_str in ["portrait", "9:16"]:
                        orientation = "portrait"
                
                # Column C: Duration (10s/15s)
                duration = "10s"
                if len(row) > 2 and row[2]:
                    duration_str = str(row[2]).strip().lower()
                    if "15" in duration_str:
                        duration = "15s"
                
                # Store full data
                self.excel_data_t2v.append((prompt, orientation, duration))
                prompts_only.append(prompt)
            
            wb.close()
            
            if prompts_only:
                # ✅ CHỈ ADD VÀO TEXT AREA
                current = self.txt_t2v_prompt.get("1.0", "end").strip()
                if current:
                    self.txt_t2v_prompt.insert("end", "\n" + "\n".join(prompts_only))
                else:
                    self.txt_t2v_prompt.insert("1.0", "\n".join(prompts_only))
                
                self.log(f"📊 Loaded {len(prompts_only)} prompts from Excel (not added to queue yet)", "info")
                
                # ✅ THÔNG BÁO: CẦN BẤM "IMPORT TO QUEUE"
                summary = f"✅ Loaded {len(prompts_only)} prompts from Excel\n\n"
                summary += f"📊 Data includes:\n"
                summary += f"  • Prompts\n"
                summary += f"  • Orientation (landscape/portrait)\n"
                summary += f"  • Duration (10s/15s)\n\n"
                summary += f"📋 Please review and click 'Import to Queue'\n"
                summary += f"   to add them to generation table"
                
                messagebox.showinfo("Excel Import", summary)
                
        except ImportError:
            messagebox.showerror("Error", "openpyxl not installed.\nRun: pip install openpyxl")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read Excel:\n{str(e)}")


    # ============================================================================
    # ✅ THÊM METHOD MỚI TẠI ĐÂY - JSON IMPORT FOR TEXT-TO-VIDEO
    # ============================================================================
    def import_prompts_json(self):
        """Import prompts from JSON - CHỈ HIỂN THỊ TRONG TEXT AREA"""
        filepath = filedialog.askopenfilename(
            title="Select JSON File",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            import json
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            prompts_to_add = []
            
            # ================================================================
            # DETECT FORMAT TYPE (giữ nguyên logic cũ)
            # ================================================================
            
            # Format A: Video Script (complex JSON with numbered keys)
            if isinstance(data, dict) and any(k.startswith(("1_", "2_", "3_")) for k in data.keys()):
                self.log("📋 Detected: Video Script JSON format", "info")
                
                if hasattr(self.app, 'convert_video_script_to_prompt'):
                    prompt_text = self.app.convert_video_script_to_prompt(data)
                else:
                    prompt_text = data.get("ad_title", "") + ". " + data.get("1_Style_Mood_Theme", {}).get("theme", "")
                
                if prompt_text:
                    # Extract duration
                    raw_duration = data.get("duration")
                    if raw_duration is None or str(raw_duration).strip() == "":
                        duration = "10s"
                    else:
                        duration_str = str(raw_duration).strip().lower()
                        if "15" in duration_str or "20" in duration_str:
                            duration = "15s"
                        else:
                            duration = "10s"
                    
                    # Detect orientation
                    orientation = "landscape"
                    try:
                        camera_data = data.get("2_Camera_Lighting_ColorTone", {})
                        if camera_data and isinstance(camera_data, dict):
                            camera_info = camera_data.get("camera", "")
                            if camera_info:
                                camera_str = str(camera_info).lower()
                                if "portrait" in camera_str or "vertical" in camera_str:
                                    orientation = "portrait"
                    except:
                        pass
                    
                    prompts_to_add.append({
                        "prompt": prompt_text,
                        "orientation": orientation,
                        "duration": duration
                    })
            
            # Format B: Array of scripts
            elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                if any(k.startswith(("1_", "2_", "3_")) for k in data[0].keys()):
                    self.log("📋 Detected: Array of Video Scripts", "info")
                    
                    for script in data:
                        if hasattr(self.app, 'convert_video_script_to_prompt'):
                            prompt_text = self.app.convert_video_script_to_prompt(script)
                        else:
                            prompt_text = script.get("ad_title", "") + ". " + script.get("1_Style_Mood_Theme", {}).get("theme", "")
                        
                        if prompt_text:
                            raw_duration = script.get("duration")
                            if raw_duration is None or str(raw_duration).strip() == "":
                                duration = "10s"
                            else:
                                duration_str = str(raw_duration).strip().lower()
                                if "15" in duration_str or "20" in duration_str:
                                    duration = "15s"
                                else:
                                    duration = "10s"
                            
                            orientation = "landscape"
                            try:
                                camera_data = script.get("2_Camera_Lighting_ColorTone", {})
                                if camera_data and isinstance(camera_data, dict):
                                    camera_info = camera_data.get("camera", "")
                                    if camera_info:
                                        camera_str = str(camera_info).lower()
                                        if "portrait" in camera_str:
                                            orientation = "portrait"
                            except:
                                pass
                            
                            prompts_to_add.append({
                                "prompt": prompt_text,
                                "orientation": orientation,
                                "duration": duration
                            })
                
                # Format C: Simple array of prompts
                else:
                    self.log("📄 Detected: Simple prompt array", "info")
                    
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        
                        raw_prompt = item.get("prompt")
                        if raw_prompt is None or str(raw_prompt).strip() == "":
                            continue
                        
                        prompt = str(raw_prompt).strip()
                        
                        raw_orientation = item.get("orientation")
                        if raw_orientation is None or str(raw_orientation).strip() == "":
                            orientation = "landscape"
                        else:
                            orientation_str = str(raw_orientation).strip().lower()
                            if orientation_str in ["9:16", "portrait"]:
                                orientation = "portrait"
                            else:
                                orientation = "landscape"
                        
                        raw_duration = item.get("duration")
                        if raw_duration is None or str(raw_duration).strip() == "":
                            duration = "10s"
                        else:
                            duration_str = str(raw_duration).strip().lower()
                            if "15" in duration_str:
                                duration = "15s"
                            else:
                                duration = "10s"
                        
                        prompts_to_add.append({
                            "prompt": prompt,
                            "orientation": orientation,
                            "duration": duration
                        })
            
            # Format D: Object with "prompts" array
            elif isinstance(data, dict) and "prompts" in data:
                self.log("📄 Detected: Object with prompts array", "info")
                
                for item in data["prompts"]:
                    if not isinstance(item, dict):
                        continue
                    
                    raw_prompt = item.get("prompt")
                    if raw_prompt is None or str(raw_prompt).strip() == "":
                        continue
                    
                    prompt = str(raw_prompt).strip()
                    
                    raw_orientation = item.get("orientation")
                    if raw_orientation is None or str(raw_orientation).strip() == "":
                        orientation = "landscape"
                    else:
                        orientation_str = str(raw_orientation).strip().lower()
                        if orientation_str in ["9:16", "portrait"]:
                            orientation = "portrait"
                        else:
                            orientation = "landscape"
                    
                    raw_duration = item.get("duration")
                    if raw_duration is None or str(raw_duration).strip() == "":
                        duration = "10s"
                    else:
                        duration_str = str(raw_duration).strip().lower()
                        if "15" in duration_str:
                            duration = "15s"
                        else:
                            duration = "10s"
                    
                    prompts_to_add.append({
                        "prompt": prompt,
                        "orientation": orientation,
                        "duration": duration
                    })
            
            # Format E: Single prompt object
            elif isinstance(data, dict) and "prompt" in data:
                self.log("📄 Detected: Single prompt object", "info")
                
                raw_prompt = data.get("prompt")
                if raw_prompt and str(raw_prompt).strip():
                    prompt = str(raw_prompt).strip()
                    
                    raw_orientation = data.get("orientation")
                    if raw_orientation is None or str(raw_orientation).strip() == "":
                        orientation = "landscape"
                    else:
                        orientation_str = str(raw_orientation).strip().lower()
                        if orientation_str in ["9:16", "portrait"]:
                            orientation = "portrait"
                        else:
                            orientation = "landscape"
                    
                    raw_duration = data.get("duration")
                    if raw_duration is None or str(raw_duration).strip() == "":
                        duration = "10s"
                    else:
                        duration_str = str(raw_duration).strip().lower()
                        if "15" in duration_str:
                            duration = "15s"
                        else:
                            duration = "10s"
                    
                    prompts_to_add.append({
                        "prompt": prompt,
                        "orientation": orientation,
                        "duration": duration
                    })
            
            else:
                raise ValueError("Unsupported JSON format")
            
            # ================================================================
            # ✅ CHỈ ADD VÀO TEXT AREA - KHÔNG TỰ ĐỘNG ADD VÀO BẢNG
            # ================================================================
            
            if not prompts_to_add:
                messagebox.showwarning("No Data", 
                    "⚠️ No valid prompts found in JSON file")
                return
            
            # Store full data
            self.json_data_t2v = prompts_to_add
            
            # Get prompts for text area
            prompts = [p["prompt"] for p in prompts_to_add]
            
            if not prompts:
                messagebox.showwarning("No Data", 
                    "⚠️ No valid prompts found in JSON file")
                return
            
            # Get current text
            current_text = self.txt_t2v_prompt.get("1.0", "end").strip()
            
            # Prepare new text (chỉ lấy prompt, bỏ orientation/duration)
            new_prompts = [p["prompt"] for p in prompts_to_add]
            
            if current_text:
                self.txt_t2v_prompt.insert("end", "\n" + "\n".join(new_prompts))
            else:
                self.txt_t2v_prompt.insert("1.0", "\n".join(new_prompts))
            
            # ✅ THÔNG BÁO: CẦN BẤM "IMPORT TO QUEUE"
            summary = f"✅ Loaded {len(prompts_to_add)} prompts from JSON\n\n"
            summary += f"📋 Please review and click 'Import to Queue'\n"
            summary += f"   to add them to generation table\n\n"
            summary += f"⚙️ Settings (orientation/duration) will be\n"
            summary += f"   applied from UI when importing to queue"
            
            messagebox.showinfo("JSON Import", summary)
            
            self.log(f"📋 Loaded {len(prompts_to_add)} prompts from JSON (not added to queue yet)", "ok")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            messagebox.showerror("JSON Error", 
                f"Invalid JSON format!\n\n{str(e)[:200]}\n\nCheck JSON syntax.")
        
        except Exception as e:
            logger.error(f"Import JSON error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to import JSON:\n\n{str(e)[:200]}")
 
    def import_to_queue(self):
        """Import prompts vào queue - MỖI LẦN ADD NHẬN SETTINGS RIÊNG"""
        text = self.txt_t2v_prompt.get("1.0", "end").strip()
        prompts = [p.strip() for p in text.split('\n') if p.strip()] if text else []
        
        if not prompts:
            messagebox.showwarning("Warning", "⚠️ No prompts entered")
            return
        
        # ✅ LẤY SETTINGS TỪ UI NGAY TẠI THỜI ĐIỂM NÀY
        orientation = self.cmb_orientation_t2v.get()
        duration = self.cmb_duration_t2v.get()
        
        self.log(f"📋 Adding {len(prompts)} prompts with settings: {orientation}, {duration}", "info")
        
        # ✅ ADD TỪNG PROMPT VỚI SETTINGS RIÊNG
        for prompt in prompts:
            prompt_data = {
                "prompt": prompt,
                "orientation": orientation,  # ← Settings tại thời điểm add
                "duration": duration,        # ← Settings tại thời điểm add
                "status": "Pending"
            }
            self.table_add_prompt_row(prompt_data)
        
        # Clear text area
        self.txt_t2v_prompt.delete("1.0", "end")
        
        self.log(f"✅ Added {len(prompts)} prompts to queue", "ok")
        
    # ========================================================================
    # TABLE METHODS
    # ========================================================================
    
    def table_add_prompt_row(self, prompt_data):
        """Thêm prompt row (KHÔNG CÓ CỘT IMAGE)"""
        row_frame = ttk.Frame(self.table_frame_t2v, relief="solid", borderwidth=1)
        row_frame.pack(fill="x", pady=1)
        row_frame.columnconfigure(2, weight=1)  # Prompt column expand
        
        stt = len(self.prompts_t2v) + 1
        
        prompt_data["selected_var"] = tk.BooleanVar(value=False)
        prompt_data["video_data"] = None
        
        # Checkbox
        chk = ttk.Checkbutton(row_frame, variable=prompt_data["selected_var"])
        chk.grid(row=0, column=0, padx=5, pady=8)
        
        # Number
        ttk.Label(row_frame, text=str(stt), anchor="center").grid(
            row=0, column=1, padx=5, pady=8)
        
        # Prompt text
        prompt_short = (prompt_data["prompt"][:80] + "..." 
                       if len(prompt_data["prompt"]) > 80 
                       else prompt_data["prompt"])
        ttk.Label(row_frame, text=prompt_short, anchor="w").grid(
            row=0, column=2, padx=10, pady=8, sticky="w")
        
        # Status
        status_color = {
            "Success": "green", 
            "Failed": "red", 
            "Pending": "orange", 
            "Processing": "blue"
        }.get(prompt_data["status"], "gray")
        
        status_label = ttk.Label(row_frame, text=prompt_data["status"], 
                                anchor="center", foreground=status_color)
        status_label.grid(row=0, column=3, padx=5, pady=8)
        prompt_data["status_label"] = status_label
        
        # Video preview slot
        preview_frame = ttk.Frame(row_frame, width=165, height=95, 
                                 relief="sunken", borderwidth=1)
        preview_frame.grid(row=0, column=4, padx=5, pady=5)
        preview_frame.grid_propagate(False)
        
        ttk.Label(preview_frame, text=self.lang.get('status_pending'), foreground="gray", 
                 font=("Segoe UI", 8)).place(relx=0.5, rely=0.5, anchor="center")
        
        prompt_data["preview_frame"] = preview_frame
        
        # Actions
        action_frame = ttk.Frame(row_frame)
        action_frame.grid(row=0, column=5, padx=5, pady=5)
        prompt_data["action_frame"] = action_frame
        
        prompt_data["row_frame"] = row_frame
        prompt_data["stt"] = stt
        prompt_data["index"] = len(self.prompts_t2v)  # ✅ ADD INDEX HERE
        self.prompts_t2v.append(prompt_data)
    
    def table_select_all(self):
        """Select all prompts"""
        for prompt in self.prompts_t2v:
            if "selected_var" in prompt:
                prompt["selected_var"].set(True)
    
    def table_deselect_all(self):
        """Deselect all prompts"""
        for prompt in self.prompts_t2v:
            if "selected_var" in prompt:
                prompt["selected_var"].set(False)
    
    def table_delete_selected(self):
        """Delete selected prompts"""
        selected = [p for p in self.prompts_t2v 
                   if p.get("selected_var") and p["selected_var"].get()]
        
        if not selected:
            messagebox.showinfo("Info", "ℹ️ No prompts selected")
            return
        
        if not messagebox.askyesno("Confirm", f"🗑️ Delete {len(selected)} prompt(s)?"):
            return
        
        for prompt in selected:
            self.table_delete_prompt_row(prompt, confirm=False)
    
    def table_delete_prompt_row(self, prompt_data, confirm=True):
        """Delete single prompt row with proper cleanup"""
        if confirm and not messagebox.askyesno("Confirm", "🗑️ Delete this prompt?"):
            return
        
        # ✅ CLEANUP PREVIEW IMAGE (Prevent memory leak)
        preview_frame = prompt_data.get("preview_frame")
        if preview_frame and preview_frame.winfo_exists():
            for widget in preview_frame.winfo_children():
                if isinstance(widget, tk.Canvas):
                    # ✅ Release PhotoImage reference
                    if hasattr(widget, 'image'):
                        widget.image = None
                    widget.delete("all")
        
        # ✅ DELETE VIDEO FILES
        video_data = prompt_data.get("video_data")
        if video_data:
            for path_key in ["path", "thumbnail_path"]:
                if video_data.get(path_key) and os.path.exists(video_data[path_key]):
                    try:
                        os.remove(video_data[path_key])
                        logger.info(f"Deleted: {os.path.basename(video_data[path_key])}")
                    except Exception as e:
                        logger.warning(f"Cannot delete file: {e}")
        
        # ✅ REMOVE FROM LIST
        if prompt_data in self.prompts_t2v:
            self.prompts_t2v.remove(prompt_data)
        
        # ✅ DESTROY FRAME
        try:
            prompt_data["row_frame"].destroy()
        except Exception as e:
            logger.warning(f"Frame destroy error: {e}")
        
        # ✅ REFRESH ROW NUMBERS
        self.table_refresh_stt()
        
        # ✅ FORCE GARBAGE COLLECTION
        import gc
        gc.collect()
    
    def table_clear_all(self):
        """Clear all prompts - FIXED: Add image cleanup"""
        if not self.prompts_t2v:
            messagebox.showinfo("Info", "ℹ️ Table is already empty")
            return
        
        confirm = messagebox.askyesno("Confirm", 
            f"🗑️ Delete all {len(self.prompts_t2v)} prompt(s)?\n\n"
            f"This will also delete associated video files.")
        
        if not confirm:
            return
        
        # ✅ CLEANUP PREVIEW IMAGES (Prevent memory leaks)
        for prompt in self.prompts_t2v:
            # Cleanup preview canvas images
            preview_frame = prompt.get("preview_frame")
            if preview_frame and preview_frame.winfo_exists():
                for widget in preview_frame.winfo_children():
                    if isinstance(widget, tk.Canvas):
                        # ✅ Release PhotoImage memory
                        if hasattr(widget, 'image'):
                            widget.image = None
                        widget.delete("all")
            
            # ✅ Delete video files
            video_data = prompt.get("video_data")
            if video_data:
                for path_key in ["path", "thumbnail_path"]:
                    if video_data.get(path_key) and os.path.exists(video_data[path_key]):
                        try:
                            os.remove(video_data[path_key])
                            logger.info(f"Deleted file: {os.path.basename(video_data[path_key])}")
                        except Exception as e:
                            logger.warning(f"Cannot delete file: {e}")
        
        # ✅ Clear prompts list
        self.prompts_t2v.clear()
        
        # ✅ Destroy all row frames
        for widget in self.table_frame_t2v.winfo_children():
            if isinstance(widget, ttk.Frame) and widget.cget("relief") == "solid":
                try:
                    widget.destroy()
                except Exception as e:
                    logger.warning(f"Widget destroy error: {e}")
        
        # ✅ Force garbage collection
        import gc
        gc.collect()
        
        self.log(f"✅ Cleared all prompts and freed memory", "ok")
        messagebox.showinfo("Success", "✅ All prompts cleared!")
    
    def table_refresh_stt(self):
        """Refresh row numbers"""
        for idx, prompt in enumerate(self.prompts_t2v):
            prompt["stt"] = idx + 1
            row_frame = prompt.get("row_frame")
            if row_frame and row_frame.winfo_exists():
                for child in row_frame.winfo_children():
                    if isinstance(child, ttk.Label):
                        try:
                            grid_info = child.grid_info()
                            if grid_info and grid_info.get("column") == 1:
                                child.config(text=str(idx + 1))
                                break
                        except:
                            pass
    
    # ========================================================================
    # GENERATION METHODS
    # ========================================================================
    
    def start_generation(self):
        """Start generation - Text-to-Video mode with Multi-Profile"""
        # ========================================================================
        # STEP 1: VALIDATION CHECKS
        # ========================================================================
        
        # Check if already generating
        if self.app.is_generating:
            messagebox.showwarning("Warning", 
                "⚠️ Generation already in progress!\n\n"
                "Please wait for current generation to complete.")
            return
        
        # ========================================================================
        # STEP 2: GET PENDING PROMPTS
        # ========================================================================
        
        pending = [p for p in self.prompts_t2v if p["status"] == "Pending"]
        
        if not pending:
            messagebox.showinfo("Info", 
                "ℹ️ No pending prompts in queue\n\n"
                "Please:\n"
                "1. Enter prompts in text area\n"
                "2. Click 'Import to Queue'")
            return
        
        # ========================================================================
        # STEP 3: CHECK PROFILE AVAILABILITY
        # ========================================================================
        
        available_profile = self.app.profile_manager.get_next_available_profile()
        if not available_profile:
            stats = self.app.profile_manager.get_profile_stats()
            messagebox.showerror("Quota Exhausted", 
                "❌ All profiles have reached their daily quota!\n\n"
                f"Total profiles: {stats['total_profiles']}\n"
                f"Used today: {stats['used_today']}/{stats['total_quota']}\n"
                f"Daily limit: 30 videos per profile\n\n"
                "💡 Solutions:\n"
                "• Wait until tomorrow for quota reset\n"
                "• Upgrade license for more profiles")
            return
        
        # ========================================================================
        # STEP 4: ✅ COLLECT UNIQUE SETTINGS FOR CONFIRMATION
        # ========================================================================
        
        # Get draft action (same for all)
        draft_action = self.draft_action_t2v.get()
        draft_action_text = "POST to public" if draft_action == "post" else "DELETE draft"
        
        # ✅ Collect unique settings
        settings_summary = {}
        for p in pending:
            key = f"{p.get('orientation', 'landscape')}_{p.get('duration', '10s')}"
            if key not in settings_summary:
                settings_summary[key] = {
                    'orientation': p.get('orientation', 'landscape'),
                    'duration': p.get('duration', '10s'),
                    'count': 0
                }
            settings_summary[key]['count'] += 1
        
        # Build settings text
        settings_text = ""
        for setting in settings_summary.values():
            settings_text += f"    • {setting['count']} video(s): {setting['orientation']}, {setting['duration']}\n"
        
        # ========================================================================
        # STEP 5: USER CONFIRMATION
        # ========================================================================
        
        confirm_msg = (
            f"🎬 Generate {len(pending)} video(s)?\n\n"
            f"📋 Settings:\n"
            f"  • Mode: Text-to-Video\n"
            f"  • Selected: {len(pending)} prompts\n"
            f"  • Current profile: {available_profile.profile_name}\n"
            f"  • Credits: {available_profile.credits_used_today}/{available_profile.max_credits_per_day} used\n"
            f"  • Remaining: {available_profile.remaining_credits()} credits\n"
            f"\n"
            f"  📐 Video settings:\n"
            f"{settings_text}"
            f"\n"
            f"  • Draft action: {draft_action_text}\n"
            f"  • Estimated time: {len(pending) * 5}-{len(pending) * 15} minutes\n\n"
            f"⚠️ IMPORTANT:\n"
            f"  • Keep browser open during generation\n"
            f"  • Stable internet required\n"
            f"  • Auto-switch profiles when quota reached\n"
            f"  • Each video takes 5-15 minutes\n"
        )
        
        if draft_action == "post":
            confirm_msg += f"\n📤 POST Mode:\n  • Videos will be published to public\n  • Requires logged in browser\n"
        
        confirm_msg += "\nContinue?"
        
        if not messagebox.askyesno("Confirm Generation", confirm_msg):
            return
        
        # ========================================================================
        # STEP 6: SYNC CURRENT_PROFILE WITH API MANAGER
        # ========================================================================
        
        if self.app.api_manager and self.app.api_manager.current_account:
            profile_obj = self.app.profile_manager.get_profile_by_name(
                self.app.api_manager.current_account
            )
            if profile_obj:
                self.app.current_profile = profile_obj
                self.log(f"[SYNC] ✅ Synced profile: {profile_obj.profile_name}", "ok")
            else:
                self.log("[SYNC] ⚠️ Profile not found, using fallback", "warn")
        
        # ========================================================================
        # STEP 7: SET STATE
        # ========================================================================
        
        self.app.is_generating = True
        self.app.stop_generation = False
        self.btn_stop_t2v.config(state="normal")
        
        # ========================================================================
        # STEP 8: ✅ PREPARE PROMPT LIST - USE SETTINGS FROM prompt_data
        # ========================================================================
        
        prompt_list = []
        for prompt_data in pending:
            prompt_list.append({
                'prompt': prompt_data.get('prompt'),
                'orientation': prompt_data.get('orientation', 'landscape'),  # ✅ From prompt_data
                'duration': prompt_data.get('duration', '10s'),              # ✅ From prompt_data
                'image_path': None,
                'download_dir': self.app.var_download_dir.get() if hasattr(self.app, 'var_download_dir') else './downloads',
                'draft_action': draft_action,
                'ui_prompt_data': prompt_data,
                'row_id': prompt_data.get('row_id'),
                'index': prompt_data.get('index')
            })
        
        # ========================================================================
        # STEP 9: CHECK CONCURRENT MODE
        # ========================================================================
        
        use_concurrent = self.var_concurrent_mode_t2v.get()
        workers = 2 if use_concurrent else 1
        
        if use_concurrent:
            self.log("="*70, "ok")
            self.log("⚡ CONCURRENT MODE - 2 Workers Parallel", "ok")
            self.log("="*70, "ok")
        else:
            self.log("="*70, "info")
            self.log("🌀 SEQUENTIAL MODE - 1 Worker", "info")
            self.log("="*70, "info")
        
        # ========================================================================
        # STEP 10: CREATE CONCURRENT MANAGER (✅ FIXED)
        # ========================================================================
        
        from concurrent_generation_manager import ConcurrentGenerationManager
        
        # ✅ VALIDATION: Check api_manager
        if not self.app.api_manager:
            self.log("="*70, "err")
            self.log("❌ CRITICAL ERROR: API Manager not initialized!", "err")
            self.log("="*70, "err")
            messagebox.showerror(
                "Error",
                "API Manager not initialized!\n\n"
                "Please restart the application."
            )
            self.app.is_generating = False
            self.btn_stop_t2v.config(state="disabled")
            return
        
        # ✅ VALIDATION: Check profile_manager
        if not self.app.profile_manager:
            self.log("="*70, "err")
            self.log("❌ CRITICAL ERROR: Profile Manager not initialized!", "err")
            self.log("="*70, "err")
            messagebox.showerror(
                "Error",
                "Profile Manager not initialized!\n\n"
                "Please restart the application."
            )
            self.app.is_generating = False
            self.btn_stop_t2v.config(state="disabled")
            return
        
        # ✅ DEBUG: Log current state
        self.log("="*70, "info")
        self.log("[DEBUG] Concurrent Manager Initialization", "info")
        self.log(f"[DEBUG] api_manager: {type(self.app.api_manager).__name__}", "info")
        self.log(f"[DEBUG] current_account: {self.app.api_manager.current_account}", "info")
        self.log(f"[DEBUG] profile_manager: {type(self.app.profile_manager).__name__}", "info")
        self.log(f"[DEBUG] workers: {workers}", "info")
        self.log("="*70, "info")
        
        # Define UI refresh callback
        def ui_refresh_callback(prompt_data):
            """Update UI when video completes"""
            try:
                index = prompt_data.get('index')
                
                if index is None:
                    self.log(f"[CALLBACK] ⚠️ index is None!", "warn")
                    return
                
                if index >= len(self.prompts_t2v):
                    self.log(f"[CALLBACK] ⚠️ index {index} >= {len(self.prompts_t2v)}", "warn")
                    return
                
                # Get original prompt_data from self.prompts_t2v
                original_prompt_data = self.prompts_t2v[index]
                
                # Update status and video_data
                status = prompt_data.get('status', 'Unknown')
                video_data = prompt_data.get('video_data', {})
                
                # ✅ LOG: Status change
                self.log(f"[CALLBACK] Video {index+1}: {status}", "info")
                
                # Update UI in main thread
                def update_ui():
                    try:
                        # Update status first
                        original_prompt_data['status'] = status
                        original_prompt_data['video_data'] = video_data
                        
                        # Update status label
                        if 'status_label' in original_prompt_data and original_prompt_data['status_label'].winfo_exists():
                            status_color = {"Success": "green", "Failed": "red", "Pending": "orange", 
                                          "Processing": "blue"}.get(status, "gray")
                            original_prompt_data['status_label'].config(text=status, foreground=status_color)
                        
                        # Update preview
                        self.table_update_video_preview_t2v(original_prompt_data, video_data)
                        
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).error(f"UI update error: {e}")
                
                self.app.schedule_gui_update(update_ui)
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Refresh callback error: {e}")
                self.log(f"[CALLBACK] ❌ Error: {str(e)[:100]}", "err")
        
        # ✅ CREATE MANAGER
        try:
            self.concurrent_manager = ConcurrentGenerationManager(
                api_manager=self.app.api_manager,
                profile_manager=self.app.profile_manager,
                max_workers=workers,
                callback=self.log,
                ui_refresh_callback=ui_refresh_callback
            )
            self.log("[MANAGER] ✅ Concurrent Manager created successfully", "ok")
        except Exception as e:
            self.log("="*70, "err")
            self.log(f"❌ Failed to create Concurrent Manager: {str(e)[:200]}", "err")
            self.log("="*70, "err")
            import logging
            logging.getLogger(__name__).error(f"Concurrent Manager init error: {e}", exc_info=True)
            messagebox.showerror(
                "Error",
                f"Failed to initialize Concurrent Manager!\n\n{str(e)[:200]}"
            )
            self.app.is_generating = False
            self.btn_stop_t2v.config(state="disabled")
            return
        
        # ========================================================================
        # STEP 11: START BACKGROUND THREAD
        # ========================================================================
        
        thread = threading.Thread(
            target=self._concurrent_generation_thread,
            args=(prompt_list,),
            daemon=True
        )
        thread.start()
    

    def _concurrent_generation_thread(self, prompt_list):
        """Background thread for concurrent generation"""
        try:
            # Start workers
            self.concurrent_manager.start(prompt_list)
            
            # Wait for all complete
            self.concurrent_manager.wait_completion()
            
            # Get final stats
            stats = self.concurrent_manager.get_stats()
            
            # Log summary
            self.log("="*70, "info")
            self.log("🎉 ALL WORKERS COMPLETE!", "ok")
            self.log(f"   ✅ Success: {stats['completed']}", "ok")
            self.log(f"   ❌ Failed: {stats['failed']}", "err")
            self.log(f"   📊 Total: {stats['total']}", "info")
            self.log("="*70, "info")
            
            # Show dialog
            self.app.schedule_gui_update(
                lambda: messagebox.showinfo(
                    "Complete",
                    f"🎉 Generation finished!\n\n"
                    f"✅ Success: {stats['completed']}\n"
                    f"❌ Failed: {stats['failed']}\n"
                    f"📊 Total: {stats['total']}"
                )
            )
        
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"[CONCURRENT] Thread error: {e}", exc_info=True)
            self.log(f"[ERROR] {str(e)[:100]}", "err")
        
        finally:
            # Reset UI
            self.app.is_generating = False
            self.app.schedule_gui_update(lambda: self.btn_stop_t2v.config(state="disabled"))
    
    def stop_generation_process(self):
        """Stop generation"""
        if not self.app.is_generating:
            messagebox.showinfo("Info", "ℹ️ No generation in progress")
            return
        
        confirm = messagebox.askyesno("Stop Generation", 
            "⏹️ Stop after current video?\n\n"
            "Current video will complete before stopping.\n"
            "Already downloaded videos will be kept.\n\n"
            "Continue?")
        
        if confirm:
            self.app.stop_generation = True
            self.log("⚠️ Stop signal sent - will stop after current video...", "info")
            self.app.schedule_gui_update(lambda: self.app.status_bar.config(
                text=self.lang.get('stopping_generation')))
        else:
            self.log("ℹ️ Stop cancelled - continuing generation", "info")
    
    # ========================================================================
    # OLD METHOD - REPLACED BY _generation_thread_wrapper above
    # ========================================================================
    # def do_batch_generation(self, pending_prompts):
    #     """OLD METHOD - DO NOT USE - Use _generation_thread_wrapper instead"""
    #     pass
    
    def do_single_generation_t2v(self, prompt_data) -> bool:
        """
        Generate single video (TEXT-TO-VIDEO MODE - KHÔNG UPLOAD ẢNH)
        QUOTA COUNTED IMMEDIATELY AFTER GENERATION STARTS
        """
        try:
            # Update status
            prompt_data["status"] = "Processing"
            self.app.schedule_gui_update(lambda pd=prompt_data: 
                pd["status_label"].config(text="Processing", foreground="blue") 
                if "status_label" in pd and pd["status_label"].winfo_exists() else None)
            
            # ====================================================================
            # [1/7] Navigate to Sora
            # ====================================================================
            self.log("[1/7] 🌐 Opening Sora page...", "info")
            # Browser code block removed (lines 1478-1650)
            # TODO: Restore browser automation code
            return False  # Temporary - browser code removed
                    
            # Dead code below (kept for reference)
            if False:
                img.save(thumb_path)
                # except:
                #     pass
            
            # ====================================================================
            # Handle success case
            # ====================================================================
            if video_path:
                self.log(f"✅ Downloaded: {Path(video_path).name}", "ok")
                
                # Handle draft action (POST or DELETE)
                self.draft_handling_t2v(
                    prompt_data=prompt_data,
                    video_path=video_path,
                    draft_id=draft_id,
                    generation_id=generation_id
                )
                
                # Update video data for UI
                video_data = {
                    "status": "Success",
                    "prompt": prompt_data["prompt"],
                    "orientation": prompt_data["orientation"],
                    "path": video_path,
                    "thumbnail_path": thumb_path,
                    "draft_id": draft_id,
                    "generation_id": generation_id
                }
                
                # Update table preview
                self.app.schedule_gui_update(lambda pd=prompt_data, vd=video_data: 
                    self.table_update_video_preview(pd, vd))
                
                return True
            else:
                # ⚠️ Download failed, but quota already counted
                self.log("❌ Download failed", "err")
                self.log("⚠️ Note: Quota already counted (generation started successfully)", "warn")
                return False
        
        except Exception as e:
            logger.error(f"T2V generation error: {e}", exc_info=True)
            self.log(f"❌ ERROR: {str(e)[:200]}", "err")
            # ⚠️ Exception occurred, but quota may have been counted if generation started
            return False
    
    def draft_handling_t2v(self, prompt_data, video_path, draft_id, generation_id):
        """
        Handle draft action after video download - TEXT-TO-VIDEO VERSION (OPTIMIZED)
        
        Args:
            prompt_data: Prompt data dict
            video_path: Downloaded video file path
            draft_id: Draft ID (for DELETE)
            generation_id: Generation ID (for POST)
        
        Returns:
            bool: True if action successful
        """
        try:
            # Get user's choice: DELETE or POST
            draft_action = self.draft_action_t2v.get()
            
            self.log("="*60, "info")
            self.log(f"[DRAFT] Action: {draft_action.upper()}", "info")
            self.log("="*60, "info")
            
            # ====================================================================
            # OPTION 1: POST VIDEO TO PUBLIC
            # ====================================================================
            if draft_action == "post":
                self.log("[DRAFT] 📤 Posting video to public...", "info")
                
                # Validate generation_id
                if not generation_id:
                    self.log("[DRAFT] ⚠️ No generation_id, cannot POST", "warn")
                    self.log("[DRAFT] 💡 Falling back to DELETE", "info")
                    
                    if draft_id and hasattr(self.app, 'current_profile') and self.app.current_profile:
                        profile_name = self.app.current_profile.profile_name
                        bearer_token = self.app.get_token_for_profile(profile_name)
                        
                        if bearer_token:
                            return self.app.browser.delete_draft_by_id(
                                draft_id, 
                                bearer_token,
                                callback=self.log
                            )
                        else:
                            self.log("[DELETE] ❌ No token available", "err")
                            return False
                    
                    return False
                
                self.log(f"[DRAFT] 🎯 Generation ID: {generation_id}", "info")
                
                # ================================================================
                # ✅ INJECT INTERCEPTOR TRƯỚC KHI NAVIGATE
                # ================================================================
                if hasattr(self, 'var_enable_wf_download_t2v') and self.var_enable_wf_download_t2v.get():
                    self.log("="*60, "info")
                    self.log("[WFD] 🎯 INJECTING INTERCEPTOR (Step 1/5)...", "info")
                    self.log("="*60, "info")
                    
        # success = PostURLExtractor.inject_post_interceptor(self.app.browser.driver)
                    
                    if success:
                        self.log("[WFD] ✅ Interceptor injected successfully", "ok")
                        time.sleep(2)
                        self.log("[WFD] ✅ Interceptor is now monitoring all requests", "ok")
                    else:
                        self.log("[WFD] ❌ Interceptor injection failed", "err")
                    
                    self.log("="*60, "info")
                
                # ================================================================
                # Step 2: Navigate to draft page
                # ================================================================
                draft_url = f"https://sora.chatgpt.com/d/{generation_id}"
                self.log(f"[POST] 🌐 Opening draft page (Step 2/5)...", "info")
                self.log(f"[POST] URL: {draft_url[:60]}...", "info")

        # self.app.browser.driver.get(draft_url)
                time.sleep(5)

                # Re-inject interceptor after navigation
                if hasattr(self, 'var_enable_wf_download_t2v') and self.var_enable_wf_download_t2v.get():
                    self.log("[POST] 🔄 Re-injecting interceptor after navigation...", "info")
        # PostURLExtractor.inject_post_interceptor(self.app.browser.driver)
                    time.sleep(1)
                    self.log("[POST] ✅ Interceptor ready to capture POST response", "ok")

                # Wait for draft page to fully load
                self.log("[POST] ⏳ Waiting for draft page to fully load...", "info")
                time.sleep(5)

        # initial_url = self.app.browser.driver.current_url
                self.log(f"[POST] 📍 Current URL: {initial_url[:60]}...", "info")

                # Check if redirected away from draft page
                if '/d/' not in initial_url:
                    self.log("[POST] ⚠️ Not on draft page - redirected!", "warn")
                    self.log(f"[POST] Actual URL: {initial_url}", "warn")
                    self.log("[POST] Draft may not exist or already deleted", "warn")
                    return False
                
                # ================================================================
                # Step 3: Fill caption (optional)
                # ================================================================
                self.log("[POST] ✍️ Filling caption (Step 3/5)...", "info")
                
                if prompt_data.get("prompt"):
                    try:
                        from selenium.webdriver.common.by import By
                        text_selectors = [
                            (By.CSS_SELECTOR, "textarea[placeholder*='caption']"),
                            (By.CSS_SELECTOR, "textarea[placeholder*='description']"),
                            (By.CSS_SELECTOR, "textarea"),
                        ]
                        
                        text_input = None
                        for by, selector in text_selectors:
                            try:
        # elements = self.app.browser.driver.find_elements(by, selector)
                                visible = [el for el in elements if el.is_displayed()]
                                if visible:
                                    text_input = visible[0]
                                    break
                            except:
                                continue
                        
                        if text_input:
                            text_input.clear()
                            text_input.send_keys(prompt_data["prompt"][:500])
                            self.log("[POST] ✅ Caption filled", "ok")
                            time.sleep(1)
                        else:
                            self.log("[POST] ⚠️ Caption input not found, skipping", "warn")
                    except Exception as e:
                        self.log(f"[POST] ⚠️ Caption error: {str(e)[:100]}", "warn")
                
                # ================================================================
                # Step 4: Find and click POST button
                # ================================================================
                self.log("[POST] 🔍 Finding POST button (Step 4/5)...", "info")
                
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                
                post_button = None
                post_selectors = [
                    (By.XPATH, "//button[translate(normalize-space(text()), 'POST', 'post')='post']"),
                    (By.XPATH, "//button[contains(translate(., 'POST', 'post'), 'post')]"),
                ]
                
                for by, selector in post_selectors:
                    try:
        # wait = WebDriverWait(self.app.browser.driver, 5)
                        elements = wait.until(EC.presence_of_all_elements_located((by, selector)))
                        visible = [el for el in elements if el.is_displayed() and el.is_enabled()]
                        if visible:
                            post_button = visible[0]
                            self.log(f"[POST] ✅ Found POST button: '{post_button.text}'", "ok")
                            break
                    except:
                        continue
                
                if not post_button:
                    self.log("[POST] ❌ POST button not found", "err")
                    return False
                
                # Click POST button
                self.log("[POST] 🖱️ Clicking POST button...", "info")
                self.log("[POST] 🎯 Interceptor is monitoring the request...", "info")
                
                try:
                    # Scroll into view
                    self.app.browser.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', behavior:'smooth'});",
                        post_button
                    )
                    time.sleep(1)
                    
                    # Click
                    post_button.click()
                    self.log("[POST] ✅ POST button clicked", "ok")
                    
                    # Wait for POST response
                    self.log("[POST] ⏳ Waiting for POST response...", "info")
                    time.sleep(5)
                    
                except Exception as e:
                    self.log(f"[POST] ❌ Click failed: {str(e)[:100]}", "err")
                    return False

                # ================================================================
                # EXTRACT POST ID FROM INTERCEPTOR
                # ================================================================
                self.log("[EXTRACT] 🔍 Checking interceptor data...", "info")

                post_data = self.app.browser.driver.execute_script(
                    "return window.__SORA_POST_DATA__;"
                )

                if post_data:
                    self.log("[EXTRACT] ✅ Interceptor captured data!", "ok")
                    
                    post_id_from_interceptor = post_data.get('post_id')
                    post_url_from_interceptor = post_data.get('post_url')
                    
                    if post_id_from_interceptor:
                        post_url = f"https://sora.chatgpt.com/p/{post_id_from_interceptor}"
                        self.log("="*60, "info")
                        self.log(f"[EXTRACT] ✅✅✅ POST ID: {post_id_from_interceptor}", "ok")
                        self.log(f"[EXTRACT] 🌐 POST URL: {post_url}", "ok")
                        self.log("="*60, "info")
                        
                        # ✅ ĐÃ CÓ ID → NHẢY THẲNG ĐẾN WATERMARK-FREE DOWNLOAD
                        self.log("[DRAFT] ✅ Video posted to public!", "ok")
                        self.log("[DRAFT] 💡 Draft automatically removed", "info")
                        
                        # Trigger watermark-free download
                        if hasattr(self, 'var_enable_wf_download_t2v') and self.var_enable_wf_download_t2v.get():
                            self.log("="*60, "info")
                            self.log("[WFD] 🎬 Triggering watermark-free download...", "info")
                            self.log("="*60, "info")
                            
                            time.sleep(3)
                            
                            self.app.wf_integration.handle_post_success(
        # browser=self.app.browser,
                                prompt=prompt_data["prompt"],
                                mode="t2v",
                                stt=prompt_data.get("stt", 1)
                            )
                        
                        # ✅ THÊM ĐOẠN NÀY - ADD VIDEO TO MERGER
                        if hasattr(self, 'var_enable_merge_t2v') and self.var_enable_merge_t2v.get():
                            self.log("[MERGER] ⏳ Waiting for watermark-free download...", "info")
                            time.sleep(5)  # Wait for WF download
                            
                            # Find latest completed task
                            if hasattr(self.app.wf_integration, 'tasks'):
                                for task_id, task in self.app.wf_integration.tasks.items():
                                    if task.get('prompt') == prompt_data["prompt"] and task.get('status') == 'completed':
                                        wf_video_path = task.get('output_path')
                                        if wf_video_path and os.path.exists(wf_video_path):
                                            self.log(f"[MERGER] 📦 Adding video to merger queue...", "info")
                                            self.log(f"[MERGER]    File: {os.path.basename(wf_video_path)}", "info")
                                            
                                            # Add to merger
                                            self.app.add_video_to_merger(wf_video_path)
                                            
                                            # Get merger stats
                                            if hasattr(self.app, 'video_merger') and self.app.video_merger:
                                                stats = self.app.video_merger.get_stats()
                                                buffer_size = len(self.app.video_merger.video_buffer)
                                                batch_size = self.var_merge_batch_size_t2v.get()
                                                
                                                self.log(f"[MERGER] ✅ Added to queue (Buffer: {buffer_size}/{batch_size})", "ok")
                                                self.log(f"[MERGER] 📊 Stats: {stats['completed']} merged | {stats['pending']} pending", "info")
                                            
                                            break
                                else:
                                    self.log("[MERGER] ⚠️ Video not found in watermark-free tasks", "warn")
                        
                        
                        return True  # ← RETURN LUÔN, SKIP HẾT PHẦN DƯỚI
                    else:
                        self.log("[EXTRACT] ⚠️ Interceptor has data but no post_id", "warn")
                else:
                    self.log("[EXTRACT] ⚠️ No data in interceptor", "warn")

                # ================================================================
                # FALLBACK: Nếu interceptor thất bại → dùng phương pháp cũ
                # ================================================================
                self.log("[POST] ⚠️ Interceptor failed, using fallback method...", "warn")
                self.log("[POST] 🔍 Verifying POST success (Step 5/5)...", "info")

                time.sleep(2)
        # final_url = self.app.browser.driver.current_url

                url_changed = final_url != initial_url
                self.log(f"[POST] 📍 Final URL: {final_url[:60]}...", "info")

                if url_changed:
                    self.log("[POST] ✅ URL changed - POST successful!", "ok")
                    post_success = True
                    
                    # Method 1: Extract from URL
                    import re
                    post_id = None
                    match = re.search(r'/p/(s_[a-f0-9]+)', final_url)
                    
                    if match:
                        post_id = match.group(1)
                        self.log(f"[POST] ✅ Extracted ID from URL: {post_id}", "ok")
                    else:
                        # Method 2: Call API
                        self.log("[POST] 🌐 URL method failed, trying API...", "info")
                        
                        if hasattr(self.app, 'current_profile') and self.app.current_profile:
                            bearer_token = self.app.get_token_for_profile(self.app.current_profile.profile_name)
                            
                            if bearer_token:
                                post_id = self.app.get_latest_post_id(bearer_token)
                    
                    if post_id:
                        post_url = f"https://sora.chatgpt.com/p/{post_id}"
                        self.log("="*60, "info")
                        self.log(f"[POST] ✅✅✅ POST ID: {post_id}", "ok")
                        self.log(f"[POST] 🌐 POST URL: {post_url}", "ok")
                        self.log("="*60, "info")
                    else:
                        self.log("[POST] ❌ Cannot get post ID", "err")

                else:
                    # Check success indicators
                    success_indicators = [
                        (By.XPATH, "//*[contains(translate(text(), 'POSTED', 'posted'), 'posted')]"),
                        (By.XPATH, "//*[contains(translate(text(), 'SUCCESS', 'success'), 'success')]"),
                        (By.XPATH, "//*[contains(translate(text(), 'PUBLISHED', 'published'), 'published')]"),
                    ]
                    
                    post_success = False
                    for by, selector in success_indicators:
                        try:
        # elements = self.app.browser.driver.find_elements(by, selector)
                            if any(el.is_displayed() for el in elements):
                                self.log(f"[POST] ✅ Success indicator found", "ok")
                                post_success = True
                                break
                        except:
                            continue

                if post_success:
                    self.log("[DRAFT] ✅ Video posted to public!", "ok")
                    self.log("[DRAFT] 💡 Draft automatically removed", "info")
                    
                    # Trigger watermark-free download
                    if hasattr(self, 'var_enable_wf_download_t2v') and self.var_enable_wf_download_t2v.get():
                        self.log("="*60, "info")
                        self.log("[WFD] 🎬 Triggering watermark-free download...", "info")
                        self.log("="*60, "info")
                        
                        time.sleep(3)
                        
                        self.app.wf_integration.handle_post_success(
        # browser=self.app.browser,
                            prompt=prompt_data["prompt"],
                            mode="t2v",
                            stt=prompt_data.get("stt", 1)
                        )
                    
                    return True
                else:
                    self.log("[DRAFT] ⚠️ POST status unclear", "warn")
                    self.log("[DRAFT] 💡 Trying DELETE as fallback...", "info")
                    
                    if draft_id and hasattr(self.app, 'current_profile') and self.app.current_profile:
                        profile_name = self.app.current_profile.profile_name
                        bearer_token = self.app.get_token_for_profile(profile_name)
                        
                        if bearer_token:
                            return self.app.browser.delete_draft_by_id(
                                draft_id,
                                bearer_token,
                                callback=self.log
                            )
                        else:
                            self.log("[DELETE] ❌ No token available", "err")
                            return False
                    
                    return False
            
            # ====================================================================
            # OPTION 2: DELETE DRAFT (DEFAULT)
            # ====================================================================
            else:  # draft_action == "delete"
                self.log("[DRAFT] 🗑️ Deleting draft...", "info")
                
                if not draft_id:
                    self.log("[DRAFT] ⚠️ No draft_id to delete", "warn")
                    return False
                
                self.log(f"[DRAFT] 🎯 Draft ID: {draft_id}", "info")
                
                if not hasattr(self.app, 'current_profile') or not self.app.current_profile:
                    self.log("[DELETE] ❌ No current profile", "err")
                    return False
                
                profile_name = self.app.current_profile.profile_name
                self.log(f"[DELETE] 👤 Profile: {profile_name}", "info")
                
                bearer_token = self.app.get_token_for_profile(profile_name)
                
                if not bearer_token:
                    self.log(f"[DELETE] ❌ No token for {profile_name}", "err")
                    return False
                
                self.log(f"[DELETE] ✅ Using token ({len(bearer_token)} chars)", "ok")
                
                delete_success = self.app.browser.delete_draft_by_id(
                    draft_id,
                    bearer_token,
                    callback=self.log
                )
                
                if delete_success:
                    self.log("[DRAFT] ✅ Draft deleted successfully!", "ok")
                    return True
                else:
                    self.log("[DRAFT] ⚠️ DELETE failed", "warn")
                    return False
        
        except Exception as e:
            logger.error(f"[DRAFT] ❌ Exception: {e}", exc_info=True)
            self.log(f"[DRAFT] ❌ Error: {str(e)[:200]}", "err")
            return False
    
    
    def table_update_video_preview(self, prompt_data, video_data):
        """Update video preview slot"""
        preview_frame = prompt_data.get("preview_frame")
        if not preview_frame or not preview_frame.winfo_exists():
            return
        
        for w in preview_frame.winfo_children():
            w.destroy()
        
        prompt_data["video_data"] = video_data
        
        if video_data["status"] == "Success" and video_data.get("path"):
            # Try to display thumbnail
            try:
                from PIL import Image, ImageTk
                if video_data.get("thumbnail_path") and os.path.exists(video_data["thumbnail_path"]):
                    img = Image.open(video_data["thumbnail_path"])
                    
                    # === SỬA PHẦN NÀY (GIỐNG FILE 1) ===
                    # Lấy orientation
                    orientation = video_data.get("orientation", "landscape").lower()
                    is_portrait = "portrait" in orientation or "9:16" in orientation
                    
                    # Container: 165x95
                    container_w, container_h = 165, 95
                    
                    # Thumbnail size
                    thumb_w, thumb_h = img.size
                    
                    # Scale giữ tỷ lệ
                    scale = min(container_w / thumb_w, container_h / thumb_h)
                    new_w = int(thumb_w * scale)
                    new_h = int(thumb_h * scale)
                    
                    # Resize
                    img_resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    
                    # Canvas với background đen
                    canvas = tk.Canvas(preview_frame, width=container_w, height=container_h, 
                                     bg='#1a1a1a', highlightthickness=0)
                    canvas.pack(fill="both", expand=True)
                    
                    # Canh giữa
                    center_x = container_w // 2
                    center_y = container_h // 2
                    
                    # Vẽ ảnh
                    photo = ImageTk.PhotoImage(img_resized)
                    canvas.create_image(center_x, center_y, image=photo, anchor="center")
                    canvas.image = photo
                    
                    # Click handler
                    canvas.bind("<Button-1>", 
                               lambda e, d=video_data: self.open_video_file(d["path"]))
                    canvas.config(cursor="hand2")
                    
                    # Play button
                    play_btn = tk.Button(preview_frame, text="▶", 
                                       font=("Segoe UI", 10, "bold"),
                                       bg="black", fg="white", relief="flat", cursor="hand2",
                                       command=lambda p=video_data["path"]: self.open_video_file(p))
                    play_btn.place(x=5, y=70, width=30, height=20)
                    
                    # Ratio badge
                    ratio_text = "9:16" if is_portrait else "16:9"
                    ratio_label = tk.Label(preview_frame, text=ratio_text, 
                                          font=("Segoe UI", 7, "bold"),
                                          bg="#333", fg="white", padx=3, pady=1)
                    ratio_label.place(x=container_w - 30, y=5)
                    # === HẾT PHẦN SỬA ===
                    
                else:
                    ttk.Button(preview_frame, text="▶ " + self.lang.get('play'), 
                             command=lambda p=video_data["path"]: self.open_video_file(p)).pack(pady=30)
            except:
                ttk.Button(preview_frame, text="▶ Play", 
                         command=lambda p=video_data["path"]: self.open_video_file(p)).pack(pady=30)
            
            # Update status
            prompt_data["status"] = "Success"
            if "status_label" in prompt_data and prompt_data["status_label"].winfo_exists():
                prompt_data["status_label"].config(text=self.lang.get('status_success'), foreground="green")
            
            # Add Regen button
            self.add_regen_button(prompt_data)
        
        elif video_data["status"] == "Failed":
            ttk.Label(preview_frame, text="Failed", foreground="red", 
                     font=("Segoe UI", 8)).place(relx=0.5, rely=0.5, anchor="center")
            
            prompt_data["status"] = "Failed"
            if "status_label" in prompt_data and prompt_data["status_label"].winfo_exists():
                prompt_data["status_label"].config(text="Failed", foreground="red")
            
            # Add Regen button
            self.add_regen_button(prompt_data)
    
    # ✅ ALIAS - Để tương thích với callback
    def table_update_video_preview_t2v(self, prompt_data, video_data):
        """Alias for table_update_video_preview"""
        return self.table_update_video_preview(prompt_data, video_data)
    
    def add_regen_button(self, prompt_data):
        """Add Regen button to action frame"""
        action_frame = prompt_data.get("action_frame")
        if not action_frame or not action_frame.winfo_exists():
            return
        
        has_regen = any(isinstance(w, ttk.Button) and w.cget("text") == "Regen" 
                       for w in action_frame.winfo_children())
        
        if not has_regen:
            ttk.Button(action_frame, text=self.lang.get('regen'), width=7,
                      command=lambda d=prompt_data: self.table_regen(d)).pack(pady=2)
    
    def table_regen(self, prompt_data):
        """Regenerate video"""
        # Reuse RegenDialog from main app
        from tkinter import Toplevel
        
        dialog = Toplevel(self.frame)
        dialog.title("Regenerate Video")
        dialog.geometry("600x450")  # ✅ TĂNG CHIỀU CAO
        
        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text=self.lang.get('prompt_column') + ":", 
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        txt_prompt = tk.Text(main_frame, height=6, wrap=tk.WORD, font=("Segoe UI", 10))
        txt_prompt.pack(fill="x", pady=(0, 10))
        txt_prompt.insert("1.0", prompt_data.get("prompt", ""))
        
        settings_frame = ttk.LabelFrame(main_frame, text=self.lang.get('settings'), padding=10)
        settings_frame.pack(fill="x", pady=(0, 10))
        
        # Orientation row
        row1 = ttk.Frame(settings_frame)
        row1.pack(fill="x", pady=5)
        ttk.Label(row1, text=self.lang.get('orientation') + ":", width=15).pack(side="left")
        cmb_orientation = ttk.Combobox(row1, values=["landscape", "portrait"], state="readonly")
        cmb_orientation.pack(side="left", fill="x", expand=True)
        cmb_orientation.set(prompt_data.get("orientation", "landscape"))
        
        # ✅ THÊM DURATION ROW
        row2 = ttk.Frame(settings_frame)
        row2.pack(fill="x", pady=5)
        ttk.Label(row2, text=self.lang.get('duration') + ":", width=15).pack(side="left")
        cmb_duration = ttk.Combobox(row2, values=["10s", "15s"], state="readonly")
        cmb_duration.pack(side="left", fill="x", expand=True)
        cmb_duration.set(prompt_data.get("duration", "10s"))
        
        result = {"data": None}
        
        def on_ok():
                result["data"] = {
                    "prompt": txt_prompt.get("1.0", "end").strip(),
                    "orientation": cmb_orientation.get(),
                    "duration": cmb_duration.get(),  # ✅ THÊM DÒNG NÀY
                }
                dialog.destroy()
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=10)
        
        ttk.Button(btn_frame, text=self.lang.get('regenerate'), style="Accent.TButton", 
                  command=on_ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=self.lang.get('cancel'), command=dialog.destroy).pack(side="left")
        
        self.frame.wait_window(dialog)
        
        if not result["data"]:
            return
        
        # Update prompt_data
        prompt_data["prompt"] = result["data"]["prompt"]
        prompt_data["orientation"] = result["data"]["orientation"]
        prompt_data["duration"] = result["data"]["duration"]  # ✅ THÊM DÒNG NÀY
        prompt_data["status"] = "Pending"
        
        # Update UI
        if "status_label" in prompt_data and prompt_data["status_label"].winfo_exists():
            prompt_data["status_label"].config(text=self.lang.get('status_pending'), foreground="orange")
        
        preview_frame = prompt_data.get("preview_frame")
        if preview_frame and preview_frame.winfo_exists():
            for w in preview_frame.winfo_children():
                w.destroy()
            ttk.Label(preview_frame, text="Pending", foreground="gray", 
                     font=("Segoe UI", 8)).place(relx=0.5, rely=0.5, anchor="center")
        
        # Start regeneration
        threading.Thread(target=self.do_single_generation_t2v, 
                        args=(prompt_data,), daemon=True).start()
    
    def open_video_file(self, video_path):
        """Open video with default player"""
        import subprocess
        import sys
        try:
            if sys.platform == "win32":
                os.startfile(video_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", video_path])
            else:
                subprocess.run(["xdg-open", video_path])
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open video:\n{str(e)}")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def toggle_wf_download_t2v(self):
        """Toggle watermark-free download for Text-to-Video"""
        if self.var_enable_wf_download_t2v.get():
            # Check if POST mode is selected
            if self.draft_action_t2v.get() == "delete":
                messagebox.showwarning(
                    "POST Mode Required",
                    "Watermark-free download requires POST mode!\n\n"
                    "Please select 'POST to Public' in Draft Action."
                )
                self.var_enable_wf_download_t2v.set(False)
                return
            
            # Enable
            if hasattr(self.app, 'wf_integration'):
                self.app.wf_integration.enable(output_folder="./downloads_no_watermark")
                self.log("Watermark-free download ENABLED (Text-to-Video)", "ok")
        else:
            # Disable
            if hasattr(self.app, 'wf_integration'):
                self.app.wf_integration.disable()
                self.log("Watermark-free download DISABLED", "info")

    def _on_concurrent_toggle_t2v(self):
        """Toggle concurrent mode controls"""
        is_enabled = self.var_concurrent_mode_t2v.get()
        
        # ✅ LUÔN GIỮ SPINBOX DISABLED - KHÔNG CHO CHỈNH SỬA SỐ LUỒNG
        # self.concurrent_workers_spin_t2v.config(state="disabled")
        
        if is_enabled:
            self.log("⚡ Concurrent mode: ENABLED (2 workers)", "ok")
        else:
            self.log("🐌 Sequential mode: ENABLED (1 worker)", "info")
    
    def toggle_video_merger_t2v(self):
        """Toggle video merger for Text-to-Video - WITH LOGGING"""
        if self.var_enable_merge_t2v.get():
            # Check watermark-free enabled
            if not self.var_enable_wf_download_t2v.get():
                messagebox.showwarning(
                    "Watermark-Free Required",
                    "⚠️ Video merger requires watermark-free download!\n\n"
                    "Please enable 'Download video no watermark' first."
                )
                self.var_enable_merge_t2v.set(False)
                return
            
            try:
                batch_size = self.var_merge_batch_size_t2v.get()
                
                self.log("="*60, "info")
                self.log("[MERGER] 🎬 Initializing Video Merger...", "info")
                self.log(f"[MERGER]    Batch size: {batch_size} videos", "info")
                self.log(f"[MERGER]    Output: ./merged_videos", "info")
                self.log("="*60, "info")
                
                # Initialize VideoMerger if not exists
                if not hasattr(self.app, 'video_merger') or not self.app.video_merger:
                    from video_merger import VideoMerger
                    self.app.video_merger = VideoMerger(
                        app_instance=self.app,
                        output_folder="./merged_videos",
                        batch_size=batch_size
                    )
                    self.app.video_merger.start()
                    self.log("[MERGER] ✅ Video Merger started", "ok")
                else:
                    self.app.video_merger.set_batch_size(batch_size)
                    self.log("[MERGER] ✅ Batch size updated", "ok")
                
                # Update stats label immediately
                self.lbl_merger_stats_t2v.config(
                    text=f"Merger: ENABLED (batch={batch_size}) | Buffer: 0/{batch_size}",
                    foreground="green"
                )
                
            except Exception as e:
                logger.error(f"Enable merger error: {e}", exc_info=True)
                self.var_enable_merge_t2v.set(False)
                self.log(f"[MERGER] ❌ Failed to enable: {str(e)[:200]}", "err")
                messagebox.showerror("Error", f"Failed to enable merger:\n\n{str(e)[:200]}")
        else:
            # Disable
            self.log("[MERGER] ⏹️ Stopping Video Merger...", "info")
            
            if hasattr(self.app, 'video_merger') and self.app.video_merger:
                self.app.video_merger.stop()
                self.log("[MERGER] ✅ Video Merger stopped", "ok")
            
            # Update stats label
            self.lbl_merger_stats_t2v.config(
                text=self.lang.get('merger_disabled'),
                foreground="gray"
            )

    def log(self, message: str, tag=None):
        """Thread-safe logging"""
        def _log():
            try:
                timestamp = time.strftime("%H:%M:%S")
                self.log_text_t2v.configure(state="normal")
                self.log_text_t2v.insert("end", f"[{timestamp}] {message}\n")
                if tag:
                    start = f"end-{len(message)+1}c"
                    self.log_text_t2v.tag_add(tag, start, "end-1c")
                self.log_text_t2v.see("end")
                self.log_text_t2v.configure(state="disabled")
                self.log_text_t2v.update_idletasks()
            except Exception as e:
                pass
        
        if threading.current_thread() == threading.main_thread():
            _log()
        else:
            self.app.schedule_gui_update(_log)