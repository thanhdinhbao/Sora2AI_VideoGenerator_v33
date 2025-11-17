#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sora2 Character Manager Tab - 8 COLUMNS VERSION
================================================
Simple optimization: More columns with auto-scaling

Changes from original:
- Grid columns: 3 → 8 (default for large screens)
- Auto-scale: 8 → 6 → 4 → 3 → 2 columns based on window width
- Thumbnail size: Keep original 150x150px
- All other features: Same as original

Author: Tran Nguyen - Zalo: 0789.535.888
Optimized: 8-column responsive layout
"""

import os
import sys
import json
import logging
import time
import webbrowser
from typing import Optional, List, Dict, Any, Tuple, Callable
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk

from sora2_character_manager import Sora2CharacterManager
from language_config import lang_manager

# Import license system functions for character limit
try:
    from sora2_license_system import get_max_characters, check_character_limit
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("License system not found, character limits disabled")
    def get_max_characters(): return 999999
    def check_character_limit(count): return (True, "Unlimited")

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

class UIConfig:
    """UI Configuration Constants"""
    # Layout
    LEFT_PANEL_WIDTH = 350  # Keep original size
    THUMBNAIL_SIZE = (150, 150)  # Keep original size
    PREVIEW_SIZE = (150, 150)
    VIEW_DIALOG_SIZE = (200, 200)
    
    # ✅ RESPONSIVE GRID COLUMNS
    GRID_COLUMNS_DEFAULT = 8  # Default to 8 columns
    
    # Auto-scale breakpoints: {min_width: columns}
    COLUMNS_BREAKPOINTS = {
        2200: 9,  # Ultra-wide screens - 9 columns
        1920: 8,  # Full HD (1920×1080) - 8 columns
        1700: 7,  # Large screens - 7 columns
        1400: 6,  # Medium screens - 6 columns
        1200: 5,  # Laptop - 5 columns
        1000: 4,  # Small desktop - 4 columns
        800: 3,   # Tablet - 3 columns
        0: 2      # Mobile - 2 columns
    }
    
    # Fonts
    FONT_TITLE = ("Segoe UI", 12, "bold")
    FONT_NORMAL = ("Arial", 9)
    FONT_SMALL = ("Arial", 8)
    FONT_BOLD = ("Arial", 9, "bold")
    FONT_LABEL = ("Segoe UI", 10, "bold")
    
    # Colors
    COLOR_PRIMARY = "blue"
    COLOR_SUCCESS = "green"
    COLOR_ERROR = "red"
    COLOR_GRAY = "gray"
    COLOR_WHITE = "white"
    
    # Padding
    PADDING_SMALL = 5
    PADDING_MEDIUM = 8
    PADDING_LARGE = 10
    
    # Card sizing
    CARD_MIN_WIDTH = 160  # Minimum card width
    CARD_MAX_WIDTH = 250  # Maximum card width
    
    # Text
    TEXT_NO_IMAGE = "[No Image]"
    TEXT_NO_CHARS = "No characters yet. Add one to get started!"
    TEXT_NO_RESULTS = "No results for '{}'"


class VideoType(Enum):
    """Video generation type"""
    IMAGE_TO_VIDEO = "i2v"
    TEXT_TO_VIDEO = "t2v"


@dataclass
class CharacterData:
    """Character data structure"""
    character_id: str
    display_name: str
    username: str
    cameo_id: str
    thumbnail_local_path: Optional[str] = None
    instruction_text: Optional[str] = None
    created_at: Optional[str] = None
    profile_url: Optional[str] = None
    visibility: str = "public"


# ============================================================================
# UTILITY CLASSES
# ============================================================================

class ThumbnailManager:
    """Manages thumbnail images and caching"""
    
    def __init__(self):
        self.cache: Dict[str, ImageTk.PhotoImage] = {}
    
    def load_thumbnail(self, path: str, size: Tuple[int, int]) -> Optional[ImageTk.PhotoImage]:
        """Load and cache thumbnail image"""
        cache_key = f"{path}_{size[0]}x{size[1]}"
        
        # Check cache first
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Load new image
        try:
            if not os.path.exists(path):
                return None
            
            img = Image.open(path)
            img.thumbnail(size)
            photo = ImageTk.PhotoImage(img)
            
            # Cache it
            self.cache[cache_key] = photo
            return photo
            
        except Exception as e:
            logger.error(f"Failed to load thumbnail: {path}, error: {e}")
            return None
    
    def clear_cache(self):
        """Clear thumbnail cache"""
        self.cache.clear()


class PromptWidgetFinder:
    """Helper class to find prompt widget in app"""
    
    @staticmethod
    def find_prompt_widget(app, video_type: VideoType) -> Optional[tk.Widget]:
        """Find prompt widget for specified video type"""
        # Method 1: Direct attribute access
        attr_map = {
            VideoType.IMAGE_TO_VIDEO: 'txt_prompt',
            VideoType.TEXT_TO_VIDEO: 'txt_t2v_prompt'
        }
        
        attr_name = attr_map.get(video_type)
        if attr_name and hasattr(app, attr_name):
            return getattr(app, attr_name)
        
        # Method 2: Search through notebook tabs
        if hasattr(app, 'notebook'):
            tab_names = {
                VideoType.IMAGE_TO_VIDEO: ["Image-to-Video", "I2V"],
                VideoType.TEXT_TO_VIDEO: ["Text-to-Video", "T2V"]
            }
            
            search_names = tab_names.get(video_type, [])
            return PromptWidgetFinder._search_tab_for_widget(app.notebook, search_names)
        
        return None
    
    @staticmethod
    def _search_tab_for_widget(notebook: ttk.Notebook, tab_names: List[str]) -> Optional[tk.Widget]:
        """Search notebook tabs for prompt widget"""
        for tab_id in notebook.tabs():
            tab_name = notebook.tab(tab_id, "text")
            
            if any(name in tab_name for name in tab_names):
                tab_frame = notebook.nametowidget(tab_id)
                
                # Find Text widget (depth 1-2 levels)
                for widget in tab_frame.winfo_children():
                    if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                        return widget
        
        return None


class PromptUpdater:
    """Handles updating prompt fields"""
    
    @staticmethod
    def update_prompt(widget: tk.Widget, usernames: List[str]) -> bool:
        """Update prompt widget with usernames"""
        try:
            # Get current prompt
            if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                current = widget.get("1.0", "end").strip()
            else:
                current = widget.get().strip()
            
            # Build new prompt
            username_str = " ".join(usernames)
            new_prompt = f"{current} {username_str}" if current else username_str
            
            # Update widget
            if isinstance(widget, (tk.Text, scrolledtext.ScrolledText)):
                widget.delete("1.0", "end")
                widget.insert("1.0", new_prompt)
            else:
                widget.delete(0, 'end')
                widget.insert(0, new_prompt)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update prompt: {e}")
            return False
    
    @staticmethod
    def copy_to_clipboard(parent: tk.Widget, text: str):
        """Copy text to clipboard"""
        parent.clipboard_clear()
        parent.clipboard_append(text)


# ============================================================================
# MAIN CHARACTER TAB CLASS
# ============================================================================

class Sora2CharacterTab:
    """
    Character Manager Tab for Sora2 - 8 COLUMNS VERSION
    
    Features:
    - 8 columns on large screens (2000px+)
    - Auto-scale: 8 → 6 → 4 → 3 → 2 based on window width
    - Responsive layout
    - Original thumbnail size (150x150)
    """
    
    def __init__(self, parent_frame: tk.Frame, app_instance):
        """Initialize Character Manager Tab"""
        self.parent = parent_frame
        self.app = app_instance
        self.lang = lang_manager
        
        # Managers
        self.manager = Sora2CharacterManager()
        self.thumbnail_manager = ThumbnailManager()
        
        # State
        self.selected_characters: List[str] = []
        self.current_thumbnail_path: Optional[str] = None
        self.current_columns = UIConfig.GRID_COLUMNS_DEFAULT  # ✅ Track current columns
        
        # UI references
        self.ui_refs = {}
        
        # Build UI
        self._build_ui()
        
        # Setup responsive behavior
        self._setup_responsive_layout()
        
        # Initial load
        self.refresh_character_list()
    
    # ========================================================================
    # UI CONSTRUCTION
    # ========================================================================
    
    def _build_ui(self):
        """Build complete user interface"""
        # Main container - ensure it fills parent completely
        main_container = tk.Frame(self.parent, bg='SystemButtonFace')  # ✅ Use tk.Frame for bg
        main_container.pack(fill="both", expand=True, 
                          padx=UIConfig.PADDING_MEDIUM, 
                          pady=UIConfig.PADDING_MEDIUM)
        
        # Left panel: Add character
        left_frame = ttk.Frame(main_container, width=UIConfig.LEFT_PANEL_WIDTH)
        left_frame.pack(side="left", fill="y", padx=(0, UIConfig.PADDING_MEDIUM))
        left_frame.pack_propagate(False)
        self._build_add_section(left_frame)
        
        # Right panel: Character library - ensure full expansion
        right_frame = tk.Frame(main_container, bg='#e1e1e1')  # ✅ Light blue/gray bg
        right_frame.pack(side="left", fill="both", expand=True)
        self._build_library_section(right_frame)
    
    def _setup_responsive_layout(self):
        """Setup responsive column adjustment"""
        def check_window_size(event=None):
            """Check window width and adjust columns"""
            try:
                window_width = self.parent.winfo_width()
                
                # Determine columns based on width
                new_columns = UIConfig.GRID_COLUMNS_DEFAULT
                for min_width in sorted(UIConfig.COLUMNS_BREAKPOINTS.keys(), reverse=True):
                    if window_width >= min_width:
                        new_columns = UIConfig.COLUMNS_BREAKPOINTS[min_width]
                        break
                
                # Update if changed
                if new_columns != self.current_columns:
                    self.current_columns = new_columns
                    self.refresh_character_list()
                    self._log_to_app(f"Adjusted to {new_columns} columns (width: {window_width}px)")
            except Exception as e:
                logger.error(f"Responsive layout error: {e}")
        
        # Bind to window resize
        self.parent.bind("<Configure>", check_window_size)
        
        # Initial check after a delay (to get actual size)
        self.parent.after(500, check_window_size)
    
    def _build_add_section(self, parent: tk.Frame):
        """Build add character section"""
        # Title with help button
        self._create_section_header(
            parent, 
            self.lang.get('add_character'), 
            self._show_add_help
        )
        
        # Scrollable content
        canvas, content_frame = self._create_scrollable_frame(parent)
        
        # Form
        form_frame = self._create_add_form(content_frame)
        
        # Add button
        self.ui_refs['btn_add'] = ttk.Button(
            content_frame,
            text=self.lang.get('add_to_library'),
            command=self._add_character,
            style="Accent.TButton"
        )
        self.ui_refs['btn_add'].pack(fill="x", pady=UIConfig.PADDING_LARGE)
        
        # Status label
        self.ui_refs['lbl_status'] = ttk.Label(
            content_frame,
            text="",
            font=UIConfig.FONT_NORMAL,
            foreground=UIConfig.COLOR_PRIMARY
        )
        self.ui_refs['lbl_status'].pack(fill="x")
        
        # Statistics
        self._create_stats_section(content_frame)
    
    def _create_section_header(self, parent: tk.Frame, title: str, help_command: Callable):
        """Create section header with title and help button"""
        header = ttk.Frame(parent)
        header.pack(fill="x", pady=(0, UIConfig.PADDING_LARGE))
        
        ttk.Label(header, text=title, font=UIConfig.FONT_TITLE).pack(side="left")
        
        ttk.Button(
            header,
            text="?",
            width=3,
            command=help_command
        ).pack(side="right")
    
    def _create_add_form(self, parent: tk.Frame) -> ttk.LabelFrame:
        """Create character input form"""
        form = ttk.LabelFrame(parent, text=self.lang.get('character_info'), 
                            padding=UIConfig.PADDING_LARGE)
        form.pack(fill="x", pady=(0, UIConfig.PADDING_LARGE))
        
        row = 0
        
        # STT (Auto)
        row = self._add_form_field(form, row, self.lang.get('stt') + ":", is_label=True)
        self.ui_refs['lbl_stt'] = ttk.Label(
            form, 
            text="1",
            font=UIConfig.FONT_BOLD,
            foreground=UIConfig.COLOR_PRIMARY
        )
        self.ui_refs['lbl_stt'].grid(row=row, column=0, sticky="w", 
                                    pady=UIConfig.PADDING_SMALL)
        row += 1
        
        # Character Name
        row = self._add_form_field(form, row, self.lang.get('character_name') + ":", 
                                   self.lang.get('character_name_hint'))
        self.ui_refs['txt_name'] = ttk.Entry(form, width=35)
        self.ui_refs['txt_name'].grid(row=row, column=0, sticky="ew", 
                                     pady=UIConfig.PADDING_SMALL)
        row += 2
        
        # Username
        row = self._add_form_field(form, row, self.lang.get('cameo_id') + ":", 
                                   self.lang.get('cameo_id_hint'))
        self.ui_refs['txt_username'] = ttk.Entry(form, width=35)
        self.ui_refs['txt_username'].grid(row=row, column=0, sticky="ew", 
                                         pady=UIConfig.PADDING_SMALL)
        row += 2
        
        # Description
        row = self._add_form_field(form, row, self.lang.get('description_optional') + ":", 
                                   self.lang.get('description_hint'))
        self.ui_refs['txt_desc'] = scrolledtext.ScrolledText(form, height=3, width=35, wrap="word")
        self.ui_refs['txt_desc'].grid(row=row, column=0, sticky="ew", 
                                     pady=UIConfig.PADDING_SMALL)
        row += 2
        
        # Thumbnail
        row = self._add_form_field(form, row, self.lang.get('thumbnail_image') + ":")
        thumbnail_row = ttk.Frame(form)
        thumbnail_row.grid(row=row, column=0, sticky="ew", pady=UIConfig.PADDING_SMALL)
        
        self.ui_refs['txt_thumbnail'] = ttk.Entry(thumbnail_row, state="readonly")
        self.ui_refs['txt_thumbnail'].pack(side="left", fill="x", expand=True, 
                                          padx=(0, UIConfig.PADDING_SMALL))
        
        ttk.Button(
            thumbnail_row,
            text=self.lang.get('browse'),
            width=10,
            command=self._browse_thumbnail
        ).pack(side="left")
        row += 1
        
        # Preview
        self.ui_refs['preview_frame'] = ttk.Frame(form)
        self.ui_refs['preview_frame'].grid(row=row, column=0, pady=UIConfig.PADDING_LARGE)
        
        self.ui_refs['lbl_preview'] = ttk.Label(
            self.ui_refs['preview_frame'],
            text=self.lang.get('no_image_selected'),
            foreground=UIConfig.COLOR_GRAY
        )
        self.ui_refs['lbl_preview'].pack()
        
        form.columnconfigure(0, weight=1)
        return form
    
    def _add_form_field(self, parent: tk.Frame, row: int, label: str, 
                       hint: str = None, is_label: bool = False) -> int:
        """Add form field with label and optional hint"""
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="w", pady=UIConfig.PADDING_SMALL
        )
        row += 1
        
        if hint:
            ttk.Label(
                parent,
                text=hint,
                font=UIConfig.FONT_SMALL,
                foreground=UIConfig.COLOR_GRAY
            ).grid(row=row + 1, column=0, sticky="w")
        
        return row
    
    def _create_stats_section(self, parent: tk.Frame):
        """Create statistics section"""
        stats_frame = ttk.LabelFrame(parent, text=self.lang.get('statistics'), 
                                    padding=UIConfig.PADDING_LARGE)
        stats_frame.pack(fill="x", pady=UIConfig.PADDING_LARGE)
        
        self.ui_refs['lbl_stats'] = ttk.Label(
            stats_frame,
            text="",
            font=UIConfig.FONT_NORMAL,
            justify="left"
        )
        self.ui_refs['lbl_stats'].pack(fill="x")
        
        self._update_stats()
    
    def _build_library_section(self, parent: tk.Frame):
        """Build character library section"""
        # Top controls
        top_frame = self._create_library_controls(parent)
        
        # Search bar
        search_frame = self._create_search_bar(parent)
        
        # Character grid
        canvas, grid_frame = self._create_scrollable_frame(parent, is_grid=True)
        self.ui_refs['grid_frame'] = grid_frame
    
    def _create_library_controls(self, parent: tk.Frame) -> tk.Frame:
        """Create library control buttons"""
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill="x", pady=(0, UIConfig.PADDING_LARGE))
        
        # Title with responsive indicator
        title_frame = ttk.Frame(top_frame)
        title_frame.pack(side="left")
        
        ttk.Label(
            title_frame,
            text=self.lang.get('character_library'),
            font=UIConfig.FONT_TITLE
        ).pack(side="left")
        
        # ✅ Show current columns
        self.ui_refs['lbl_columns'] = ttk.Label(
            title_frame,
            text=f"({self.current_columns} cols)",
            font=UIConfig.FONT_SMALL,
            foreground=UIConfig.COLOR_GRAY
        )
        self.ui_refs['lbl_columns'].pack(side="left", padx=10)
        
        # Buttons
        btn_frame = ttk.Frame(top_frame)
        btn_frame.pack(side="right")
        
        buttons = [
            (self.lang.get('refresh'), self.refresh_character_list, 12),
            (self.lang.get('delete_selected'), self._delete_selected, 15),
        ]
        
        for text, command, width in buttons:
            ttk.Button(
                btn_frame,
                text=text,
                command=command,
                width=width
            ).pack(side="left", padx=2)
        
        # Import buttons
        self.ui_refs['btn_import_i2v'] = ttk.Button(
            btn_frame,
            text=self.lang.get('import_to_i2v'),
            command=lambda: self._import_to_video(VideoType.IMAGE_TO_VIDEO),
            width=15,
            style="Accent.TButton"
        )
        self.ui_refs['btn_import_i2v'].pack(side="left", padx=2)
        
        self.ui_refs['btn_import_t2v'] = ttk.Button(
            btn_frame,
            text=self.lang.get('import_to_t2v'),
            command=lambda: self._import_to_video(VideoType.TEXT_TO_VIDEO),
            width=15,
            style="Accent.TButton"
        )
        self.ui_refs['btn_import_t2v'].pack(side="left", padx=2)
        
        return top_frame
    
    def _create_search_bar(self, parent: tk.Frame) -> tk.Frame:
        """Create search bar"""
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill="x", pady=(0, UIConfig.PADDING_LARGE))
        
        ttk.Label(search_frame, text=self.lang.get('search') + ":").pack(
            side="left", padx=(0, UIConfig.PADDING_SMALL))
        
        self.ui_refs['txt_search'] = ttk.Entry(search_frame)
        self.ui_refs['txt_search'].pack(side="left", fill="x", expand=True, 
                                       padx=(0, UIConfig.PADDING_SMALL))
        self.ui_refs['txt_search'].bind('<KeyRelease>', lambda e: self._search_characters())
        
        ttk.Button(
            search_frame,
            text=self.lang.get('clear'),
            command=self._clear_search,
            width=8
        ).pack(side="left")
        
        ttk.Label(
            search_frame,
            text=self.lang.get('search_hint'),
            font=UIConfig.FONT_SMALL,
            foreground=UIConfig.COLOR_GRAY
        ).pack(side="left", padx=UIConfig.PADDING_SMALL)
        
        return search_frame
    
    def _create_scrollable_frame(self, parent: tk.Frame, is_grid: bool = False) -> Tuple[tk.Canvas, tk.Frame]:
        """Create scrollable frame with canvas"""
        canvas = tk.Canvas(parent, bg=UIConfig.COLOR_WHITE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        content_frame = ttk.Frame(canvas)
        
        content_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Mouse wheel scrolling
        self._bind_mousewheel(canvas)
        
        return canvas, content_frame
    
    def _bind_mousewheel(self, canvas: tk.Canvas):
        """Bind mousewheel scrolling to canvas"""
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
    
    # ========================================================================
    # CHARACTER ACTIONS
    # ========================================================================
    
    def _add_character(self):
        """Add new character to library"""
        try:
            # Get form data
            name = self.ui_refs['txt_name'].get().strip()
            username = self.ui_refs['txt_username'].get().strip()
            description = self.ui_refs['txt_desc'].get("1.0", "end").strip()
            thumbnail_path = self.current_thumbnail_path
            
            # Validate
            if not name or not username:
                messagebox.showwarning(
                    self.lang.get('warning'),
                    self.lang.get('name_username_required')
                )
                return
            
            if not thumbnail_path or not os.path.exists(thumbnail_path):
                messagebox.showwarning(
                    self.lang.get('warning'),
                    "Please select a valid thumbnail image"
                )
                return
            
            # Check license limit
            current_count = len(self.manager.list_all())
            can_add, msg = check_character_limit(current_count + 1)
            
            if not can_add:
                messagebox.showerror(
                    self.lang.get('limit_reached'),
                    msg
                )
                return
            
            # Auto add @ prefix
            if not username.startswith('@'):
                username = f"@{username}"
            
            # Generate character ID
            character_id = f"local_char_{int(time.time())}"
            profile_url = f"https://sora.chatgpt.com/{username}"
            
            # Set status
            self._set_status(self.lang.get('adding_character'), UIConfig.COLOR_PRIMARY)
            
            # ✅ Add character - using correct parameters from original file
            success, error = self.manager.add_character(
                character_id=character_id,
                cameo_id=username,
                username=username,
                display_name=name,
                profile_url=profile_url,
                thumbnail_url="",
                thumbnail_source_path=thumbnail_path,  # ✅ CORRECT PARAMETER NAME
                generation_id=None,
                visibility="public",
                instruction_text=description if description else None
            )
            
            if success:
                self._set_status(
                    self.lang.get('character_added_success'), 
                    UIConfig.COLOR_SUCCESS
                )
                
                # Clear form
                self._clear_add_form()
                
                # Refresh list
                self.refresh_character_list()
                
                # Update stats
                self._update_stats()
                
                # Log
                self._log_to_app(f"Added character: {name} ({username})")
                
            else:
                self._set_status(
                    self.lang.get('character_add_failed'), 
                    UIConfig.COLOR_ERROR
                )
                if error:
                    messagebox.showerror(
                        self.lang.get('error'),
                        f"Failed to add character:\n{error}"
                    )
                
        except Exception as e:
            logger.error(f"Add character failed: {e}", exc_info=True)
            messagebox.showerror(
                self.lang.get('error'),
                f"{self.lang.get('add_failed')}\n\n{str(e)}"
            )
    
    def _delete_single(self, character_id: str):
        """Delete single character"""
        if not messagebox.askyesno(
            self.lang.get('confirm_delete'),
            self.lang.get('delete_single_confirm')
        ):
            return
        
        try:
            success = self.manager.delete_character(character_id)
            
            if success:
                self._set_status(
                    self.lang.get('delete_success'), 
                    UIConfig.COLOR_SUCCESS
                )
                self.refresh_character_list()
                self._update_stats()
                self._log_to_app(f"Deleted character ID: {character_id}")
            else:
                messagebox.showerror(
                    self.lang.get('error'),
                    self.lang.get('delete_failed')
                )
                
        except Exception as e:
            logger.error(f"Delete character failed: {e}", exc_info=True)
            messagebox.showerror(
                self.lang.get('error'),
                f"{self.lang.get('delete_failed')}\n\n{str(e)}"
            )
    
    def _delete_selected(self):
        """Delete multiple selected characters"""
        if not self.selected_characters:
            messagebox.showinfo(
                self.lang.get('no_selection'),
                self.lang.get('please_select_characters')
            )
            return
        
        count = len(self.selected_characters)
        
        if not messagebox.askyesno(
            self.lang.get('confirm_delete'),
            self.lang.get('delete_multiple_confirm').format(count)
        ):
            return
        
        try:
            deleted = 0
            
            for char_id in self.selected_characters[:]:
                if self.manager.delete_character(char_id):
                    deleted += 1
            
            self.selected_characters.clear()
            
            self._set_status(
                self.lang.get('deleted_count').format(deleted, count),
                UIConfig.COLOR_SUCCESS
            )
            
            self.refresh_character_list()
            self._update_stats()
            self._log_to_app(f"Deleted {deleted}/{count} characters")
            
        except Exception as e:
            logger.error(f"Delete multiple failed: {e}", exc_info=True)
            messagebox.showerror(
                self.lang.get('error'),
                f"{self.lang.get('delete_failed')}\n\n{str(e)}"
            )
    
    def _import_to_video(self, video_type: VideoType):
        """Import selected characters to video generation prompt"""
        if not self.selected_characters:
            messagebox.showinfo(
                self.lang.get('no_selection'),
                self.lang.get('please_select_characters_import')
            )
            return
        
        try:
            # Get usernames
            usernames = []
            
            for char_id in self.selected_characters:
                char = self.manager.get_character(char_id)
                if char:
                    usernames.append(char['username'])
            
            if not usernames:
                messagebox.showwarning(
                    self.lang.get('warning'),
                    self.lang.get('no_valid_characters')
                )
                return
            
            username_str = " ".join(usernames)
            
            # Find prompt widget
            prompt_widget = PromptWidgetFinder.find_prompt_widget(self.app, video_type)
            
            if prompt_widget:
                # Update prompt directly
                success = PromptUpdater.update_prompt(prompt_widget, usernames)
                
                if success:
                    video_name = "I2V" if video_type == VideoType.IMAGE_TO_VIDEO else "T2V"
                    
                    messagebox.showinfo(
                        self.lang.get('import_success'),
                        self.lang.get('imported_to_prompt').format(len(usernames), video_name)
                    )
                    
                    self._log_to_app(f"Imported {len(usernames)} characters to {video_name}")
                else:
                    raise Exception("Failed to update prompt widget")
            else:
                # Fallback: Copy to clipboard
                video_name = "Image-to-Video" if video_type == VideoType.IMAGE_TO_VIDEO else "Text-to-Video"
                
                messagebox.showinfo(
                    self.lang.get('copied_to_clipboard'),
                    self.lang.get('prompt_widget_not_found').format(
                        username_str, video_name
                    )
                )
                
                PromptUpdater.copy_to_clipboard(self.parent, username_str)
                self._log_to_app(f"Usernames copied to clipboard")
                
        except Exception as e:
            logger.error(f"Failed to import to video: {e}", exc_info=True)
            messagebox.showerror(
                self.lang.get('error'),
                self.lang.get('import_failed').format(str(e), username_str if 'username_str' in locals() else '')
            )
    
    # ========================================================================
    # CHARACTER DISPLAY
    # ========================================================================
    
    def refresh_character_list(self):
        """Refresh character list display with current column count"""
        # Clear existing
        grid_frame = self.ui_refs['grid_frame']
        for widget in grid_frame.winfo_children():
            widget.destroy()
        
        self.thumbnail_manager.clear_cache()
        self.selected_characters.clear()
        
        # Update column indicator
        if 'lbl_columns' in self.ui_refs:
            self.ui_refs['lbl_columns'].config(text=f"({self.current_columns} cols)")
        
        # Get characters
        characters = self.manager.list_all()
        
        if not characters:
            ttk.Label(
                grid_frame,
                text=self.lang.get('no_characters'),
                font=UIConfig.FONT_NORMAL,
                foreground=UIConfig.COLOR_GRAY
            ).pack(pady=50)
            return
        
        # Display in grid with current column count
        for idx, char in enumerate(characters):
            row = idx // self.current_columns  # ✅ Use responsive columns
            col = idx % self.current_columns
            self._create_character_card(grid_frame, char, idx + 1, row, col)
    
    def _create_character_card(self, parent: tk.Frame, char_data: Dict, 
                              stt: int, row: int, col: int):
        """Create character card widget"""
        card = ttk.Frame(parent, relief="ridge", borderwidth=1)
        card.grid(row=row, column=col, 
                 padx=UIConfig.PADDING_SMALL, 
                 pady=UIConfig.PADDING_SMALL, 
                 sticky="nsew")  # ✅ Important: sticky to expand
        
        # Header (STT + Checkbox)
        self._create_card_header(card, char_data, stt)
        
        # Thumbnail
        self._create_card_thumbnail(card, char_data)
        
        # Info
        self._create_card_info(card, char_data)
        
        # Buttons
        self._create_card_buttons(card, char_data)
        
        # ✅ Configure grid to expand cards equally
        parent.columnconfigure(col, weight=1, uniform="cards")
        parent.rowconfigure(row, weight=0)
    
    def _create_card_header(self, card: tk.Frame, char_data: Dict, stt: int):
        """Create card header with STT and checkbox"""
        header_frame = ttk.Frame(card)
        header_frame.pack(fill="x", padx=UIConfig.PADDING_SMALL, 
                         pady=UIConfig.PADDING_SMALL)
        
        # STT badge
        ttk.Label(
            header_frame,
            text=f"#{stt}",
            font=UIConfig.FONT_BOLD,
            foreground=UIConfig.COLOR_WHITE,
            background=UIConfig.COLOR_PRIMARY,
            padding=3
        ).pack(side="left")
        
        # Checkbox
        var_selected = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(
            header_frame,
            variable=var_selected,
            command=lambda: self._toggle_selection(char_data['character_id'], 
                                                   var_selected.get())
        )
        chk.pack(side="right")
    
    def _create_card_thumbnail(self, card: tk.Frame, char_data: Dict):
        """Create card thumbnail"""
        thumbnail_frame = ttk.Frame(card)
        thumbnail_frame.pack(pady=UIConfig.PADDING_SMALL, expand=True, fill="both")
        
        thumbnail_path = char_data.get('thumbnail_local_path')
        
        if thumbnail_path:
            photo = self.thumbnail_manager.load_thumbnail(
                thumbnail_path, 
                UIConfig.THUMBNAIL_SIZE  # Original 150x150
            )
            if photo:
                lbl_img = ttk.Label(thumbnail_frame, image=photo, anchor="center")
                lbl_img.image = photo  # Keep reference
                lbl_img.pack(expand=True)
                return
        
        # Fallback: No image
        ttk.Label(
            thumbnail_frame,
            text=self.lang.get('no_image'),
            foreground=UIConfig.COLOR_GRAY,
            anchor="center"
        ).pack(expand=True)
    
    def _create_card_info(self, card: tk.Frame, char_data: Dict):
        """Create card info section"""
        info_frame = ttk.Frame(card)
        info_frame.pack(fill="x", padx=UIConfig.PADDING_SMALL, 
                       pady=UIConfig.PADDING_SMALL)
        
        # Name
        ttk.Label(
            info_frame,
            text=char_data['display_name'],
            font=UIConfig.FONT_LABEL,
            wraplength=200,  # Increased from 160 for wider cards
            justify="center",
            anchor="center"
        ).pack(fill="x")
        
        # Username
        ttk.Label(
            info_frame,
            text=char_data['username'],
            font=UIConfig.FONT_NORMAL,
            foreground=UIConfig.COLOR_PRIMARY,
            justify="center",
            anchor="center"
        ).pack(fill="x")
        
        # Description preview
        description = char_data.get('instruction_text', '')
        if description:
            preview = description[:30] + "..." if len(description) > 30 else description
            ttk.Label(
                info_frame,
                text=preview,
                font=UIConfig.FONT_SMALL,
                foreground=UIConfig.COLOR_GRAY,
                wraplength=200,  # Increased from 160
                justify="center",
                anchor="center"
            ).pack(fill="x")
    
    def _create_card_buttons(self, card: tk.Frame, char_data: Dict):
        """Create card action buttons"""
        btn_frame = ttk.Frame(card)
        btn_frame.pack(fill="x", padx=UIConfig.PADDING_SMALL, 
                      pady=UIConfig.PADDING_SMALL)
        
        # Create inner frame to center buttons
        inner_btn = ttk.Frame(btn_frame)
        inner_btn.pack(expand=True)
        
        ttk.Button(
            inner_btn,
            text=self.lang.get('view'),
            command=lambda: self._view_character(char_data),
            width=8
        ).pack(side="left", padx=2)
        
        ttk.Button(
            inner_btn,
            text=self.lang.get('delete'),
            command=lambda: self._delete_single(char_data['character_id']),
            width=8
        ).pack(side="left", padx=2)
    
    def _view_character(self, char_data: Dict):
        """Show character details dialog"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(f"Character: {char_data['display_name']}")
        dialog.transient(self.parent)
        dialog.grab_set()
        
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        
        # Thumbnail
        thumbnail_path = char_data.get('thumbnail_local_path')
        if thumbnail_path:
            photo = self.thumbnail_manager.load_thumbnail(
                thumbnail_path, 
                UIConfig.VIEW_DIALOG_SIZE
            )
            if photo:
                lbl_img = ttk.Label(frame, image=photo)
                lbl_img.image = photo
                lbl_img.pack(pady=UIConfig.PADDING_LARGE)
        
        # Info text
        info_text = self._format_character_info(char_data)
        
        txt_info = scrolledtext.ScrolledText(frame, height=12, width=50, wrap="word")
        txt_info.pack(pady=UIConfig.PADDING_LARGE)
        txt_info.insert("1.0", info_text)
        txt_info.config(state="disabled")
        
        # Close button
        ttk.Button(
            frame,
            text=self.lang.get('close'),
            command=dialog.destroy,
            width=15
        ).pack(pady=UIConfig.PADDING_LARGE)
        
        # Center dialog
        self._center_window(dialog)
    
    def _format_character_info(self, char_data: Dict) -> str:
        """Format character info for display"""
        info_lines = [
            f"Character Name: {char_data['display_name']}",
            f"Username: {char_data['username']}",
            f"Character ID: {char_data['character_id']}",
            f"Cameo ID: {char_data['cameo_id']}",
            f"Created: {char_data.get('created_at', 'N/A')}",
            ""
        ]
        
        description = char_data.get('instruction_text', '')
        if description:
            info_lines.extend([
                "Description:",
                description,
                ""
            ])
        
        return "\n".join(info_lines)
    
    # ========================================================================
    # SEARCH & FILTER
    # ========================================================================
    
    def _search_characters(self):
        """Search characters by keyword"""
        keyword = self.ui_refs['txt_search'].get().strip()
        
        if not keyword:
            self.refresh_character_list()
            return
        
        # Clear grid
        grid_frame = self.ui_refs['grid_frame']
        for widget in grid_frame.winfo_children():
            widget.destroy()
        
        # Search
        results = self.manager.search(keyword)
        
        if not results:
            ttk.Label(
                grid_frame,
                text=self.lang.get('no_results').format(keyword),
                font=UIConfig.FONT_NORMAL,
                foreground=UIConfig.COLOR_GRAY
            ).pack(pady=50)
            return
        
        # Display results
        for idx, char in enumerate(results):
            row = idx // self.current_columns  # ✅ Use responsive columns
            col = idx % self.current_columns
            self._create_character_card(grid_frame, char, idx + 1, row, col)
    
    def _clear_search(self):
        """Clear search and refresh"""
        self.ui_refs['txt_search'].delete(0, 'end')
        self.refresh_character_list()
    
    # ========================================================================
    # UI HELPERS
    # ========================================================================
    
    def _browse_thumbnail(self):
        """Browse for thumbnail image"""
        filetypes = [
            ("Image files", "*.jpg *.jpeg *.png"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Select Thumbnail Image",
            filetypes=filetypes
        )
        
        if filename:
            self.current_thumbnail_path = filename
            
            # Update entry
            entry = self.ui_refs['txt_thumbnail']
            entry.config(state="normal")
            entry.delete(0, 'end')
            entry.insert(0, filename)
            entry.config(state="readonly")
            
            # Show preview
            self._show_thumbnail_preview(filename)
    
    def _show_thumbnail_preview(self, image_path: str):
        """Show thumbnail preview"""
        photo = self.thumbnail_manager.load_thumbnail(image_path, UIConfig.PREVIEW_SIZE)
        
        if photo:
            self.ui_refs['lbl_preview'].config(image=photo, text="")
            self.ui_refs['lbl_preview'].image = photo
        else:
            self.ui_refs['lbl_preview'].config(
                text=self.lang.get('preview_error'),
                foreground=UIConfig.COLOR_ERROR
            )
    
    def _clear_add_form(self):
        """Clear add character form"""
        self.ui_refs['txt_name'].delete(0, 'end')
        self.ui_refs['txt_username'].delete(0, 'end')
        self.ui_refs['txt_desc'].delete("1.0", "end")
        
        entry = self.ui_refs['txt_thumbnail']
        entry.config(state="normal")
        entry.delete(0, 'end')
        entry.config(state="readonly")
        
        # Clear preview
        self.ui_refs['lbl_preview'].config(image="", 
                                           text=self.lang.get('no_image_selected'))
        if hasattr(self.ui_refs['lbl_preview'], 'image'):
            delattr(self.ui_refs['lbl_preview'], 'image')
        
        # Update STT
        self.ui_refs['lbl_stt'].config(text=str(len(self.manager.list_all()) + 1))
    
    def _toggle_selection(self, character_id: str, is_selected: bool):
        """Toggle character selection"""
        if is_selected:
            if character_id not in self.selected_characters:
                self.selected_characters.append(character_id)
        else:
            if character_id in self.selected_characters:
                self.selected_characters.remove(character_id)
        
        # Update button texts
        count = len(self.selected_characters)
        if count > 0:
            self.ui_refs['btn_import_i2v'].config(
                text=self.lang.get('import_count_to_i2v').format(count)
            )
            self.ui_refs['btn_import_t2v'].config(
                text=self.lang.get('import_count_to_t2v').format(count)
            )
        else:
            self.ui_refs['btn_import_i2v'].config(text=self.lang.get('import_to_i2v'))
            self.ui_refs['btn_import_t2v'].config(text=self.lang.get('import_to_t2v'))
    
    def _update_stats(self):
        """Update statistics display with license limits"""
        stats = self.manager.get_stats()
        
        # Get license limits
        max_chars = get_max_characters()
        current = stats['total']
        
        # Color based on usage
        if max_chars >= 999999:
            limit_text = f"Characters: {current} (Unlimited)"
            color = UIConfig.COLOR_SUCCESS
        else:
            remaining = max_chars - current
            limit_text = f"Characters: {current}/{max_chars}"
            
            # Set color based on usage percentage
            usage_pct = (current / max_chars) if max_chars > 0 else 0
            if usage_pct >= 1.0:
                color = UIConfig.COLOR_ERROR
            elif usage_pct >= 0.9:
                color = "orange"
            else:
                color = UIConfig.COLOR_SUCCESS
        
        stats_text = (
            f"{limit_text}\n"
            f"Public: {stats['public']} | Private: {stats['private']}\n"
            f"Storage: {stats['thumbnails_dir_size']}"
        )
        
        self.ui_refs['lbl_stats'].config(text=stats_text, foreground=color)
    
    def _set_status(self, message: str, color: str):
        """Set status message"""
        self.ui_refs['lbl_status'].config(text=message, foreground=color)
        self.parent.update()
    
    def _log_to_app(self, message: str):
        """Log message to main app"""
        if hasattr(self.app, 'log'):
            self.app.log(f"[CHARACTER] {message}", "ok")
    
    def _show_add_help(self):
        """Show help dialog for adding character"""
        messagebox.showinfo(
            self.lang.get('add_character_help_title'), 
            self.lang.get('add_character_help_content')
        )
    
    @staticmethod
    def _center_window(window: tk.Toplevel):
        """Center window on screen"""
        window.update_idletasks()
        x = (window.winfo_screenwidth() // 2) - (window.winfo_width() // 2)
        y = (window.winfo_screenheight() // 2) - (window.winfo_height() // 2)
        window.geometry(f"+{x}+{y}")


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("Sora2 Character Manager Tab - 8 COLUMNS VERSION")
    print("=" * 70)
    print("\nFEATURES:")
    print("  ✅ 8 columns on large screens (2000px+)")
    print("  ✅ Auto-scale: 8 → 6 → 4 → 3 → 2 based on window width")
    print("  ✅ Responsive layout - adjusts automatically")
    print("  ✅ Original thumbnail size (150x150px)")
    print("  ✅ All original features preserved")
    print("\nOPTIMIZED FOR MORE COLUMNS:")
    print("  • Reduced left panel: 350px → 280px (saves 70px)")
    print("  • More space for character cards")
    print("  • Can fit 8-9 columns on Full HD!")
    print("\nBREAKPOINTS:")
    print("  • 2200px+ → 9 columns (Ultra-wide)")
    print("  • 1850px+ → 8 columns (Full HD with space)")
    print("  • 1600px+ → 7 columns")
    print("  • 1280px+ → 6 columns (HD)")
    print("  • 1024px+ → 5 columns")
    print("  • 800px+  → 4 columns")
    print("  • 600px+  → 3 columns")
    print("  • <600px  → 2 columns")
    print("\nUSAGE:")
    print("  Replace: from sora2_character_tab import Sora2CharacterTab")
    print("  With:    from sora2_character_tab_8cols import Sora2CharacterTab")