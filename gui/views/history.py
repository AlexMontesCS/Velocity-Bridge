import customtkinter as ctk
import platform
import subprocess
import threading
import time
from datetime import datetime
from PIL import Image
from gui.utils.config import load_history, HISTORY_FILE

# Modern Theme Colors
COLOR_SURFACE = "#1E1E1E"
COLOR_BG = "#121212"
COLOR_BORDER = "#333333"
COLOR_HOVER = "#2D2D2D"
COLOR_ACCENT = "#00E676"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#AAAAAA"
COLOR_TEXT_META = "#666666"

def filter_items(items, query):
    if not query:
        return items
    query = query.lower()
    return [
        h for h in items
        if query in h.get("preview", "").lower() 
        or query in h.get("content", "").lower()
        or query in h.get("type", "").lower()
    ]

class HistoryFrame(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.current_items = {} # Map timestamp -> widget instance
        self.current_page = 1
        self.items_per_page = 15
        self.all_display_items = []
        
        self._setup_ui()
        
        # Initial load
        self.after(100, self.refresh)
        
        # Schedule observer
        if hasattr(app, 'observer'):
            app.observer.schedule_file(HISTORY_FILE, lambda: self.after(0, self.refresh))

    def _setup_ui(self):
        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=30, pady=(30, 20))
        
        # Title & Count
        title_box = ctk.CTkFrame(self.header, fg_color="transparent")
        title_box.pack(side="left")
        
        ctk.CTkLabel(title_box, text="Clipboard History", 
                   font=ctk.CTkFont(size=28, weight="bold"),
                   text_color=COLOR_TEXT_PRIMARY).pack(side="left")
                   
        self.count_label = ctk.CTkLabel(title_box, text="", 
                                      font=ctk.CTkFont(size=14),
                                      text_color=COLOR_TEXT_META)
        self.count_label.pack(side="left", padx=(15, 0), pady=(5, 0))

        # Right control area
        controls = ctk.CTkFrame(self.header, fg_color="transparent")
        controls.pack(side="right")

        # Search
        self.app.history_search_var = ctk.StringVar()
        try:
            self.app.history_search_var.trace_add("write", lambda *args: self.on_search())
        except AttributeError:
            self.app.history_search_var.trace("w", lambda *args: self.on_search())

        self.search_entry = ctk.CTkEntry(controls, placeholder_text="Type to search...", 
                                       width=250, height=38,
                                       textvariable=self.app.history_search_var,
                                       font=ctk.CTkFont(size=13),
                                       fg_color=COLOR_SURFACE,
                                       border_color=COLOR_BORDER,
                                       text_color=COLOR_TEXT_PRIMARY)
        self.search_entry.pack(side="left", padx=10)

        # Refresh Action
        self.refresh_btn = ctk.CTkButton(controls, text="Refresh", width=80, height=38,
                                       command=lambda: self.refresh(force=True),
                                       fg_color=COLOR_SURFACE, 
                                       hover_color=COLOR_HOVER,
                                       text_color=COLOR_TEXT_PRIMARY,
                                       border_width=1,
                                       border_color=COLOR_BORDER)
        self.refresh_btn.pack(side="left")

        # Scrollable Container
        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=30, pady=(0, 20))
        
        # Pagination Controls
        self.controls_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        
        # We need to pack this AFTER items, but since items are packed dynamically, 
        # let's just create it. `refresh` will manage its position.
        
        self.btn_prev = ctk.CTkButton(self.controls_frame, text="< Prev", width=80, height=32,
                                    fg_color=COLOR_SURFACE, hover_color=COLOR_HOVER,
                                    command=self.prev_page)
        self.btn_prev.pack(side="left", padx=5)
        
        self.lbl_page = ctk.CTkLabel(self.controls_frame, text="Page 1", 
                                   font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_META)
        self.lbl_page.pack(side="left", padx=10)
        
        self.btn_next = ctk.CTkButton(self.controls_frame, text="Next >", width=80, height=32,
                                    fg_color=COLOR_SURFACE, hover_color=COLOR_HOVER,
                                    command=self.next_page)
        self.btn_next.pack(side="left", padx=5)

        # Smooth Scroll
        self._setup_smooth_scroll()

    def _setup_smooth_scroll(self):
        """Configure smooth scrolling."""
        canvas = self.container._parent_canvas
        canvas.configure(yscrollincrement=5)
        
        def _scroll(event):
            try:
                if self.container.winfo_containing(event.x_root, event.y_root):
                    direction = -1 * (1 if event.delta > 0 or event.num == 4 else -1)
                    canvas.yview_scroll(direction * 3, "units")
                    return "break"
            except: pass

        system = platform.system()
        bind_key = "<MouseWheel>" if system != "Linux" else ["<Button-4>", "<Button-5>"]
        
        if isinstance(bind_key, list):
            for k in bind_key:
                self.app.bind_all(k, _scroll)
        else:
            self.app.bind_all(bind_key, _scroll)

    def on_search(self):
        # Reset to page 1 on search
        self.current_page = 1
        if hasattr(self, '_search_job'):
            self.after_cancel(self._search_job)
        self._search_job = self.after(200, self.refresh)

    def next_page(self):
        self.current_page += 1
        self.refresh()

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh()

    def refresh(self, force=False):
        """Smart Refresh: Diffs content with Pagination."""
        full_history = load_history()
        query = self.app.history_search_var.get().lower()
        
        # Filter first
        self.all_display_items = filter_items(full_history, query)
        total_items = len(self.all_display_items)
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page
        if total_pages < 1: total_pages = 1
        
        # Clamp page
        if self.current_page > total_pages: self.current_page = total_pages
        if self.current_page < 1: self.current_page = 1
        
        # Slice for current page
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        
        # Remember: Newest items at END of logic, but we render reversed?
        # Let's keep logic consistent with previous step.
        # We reversed `all_display_items` (which comes from oldest->newest file)
        # So `reversed_all[0]` is the newest.
        
        reversed_all = list(reversed(self.all_display_items))
        visible_items = reversed_all[start_idx:end_idx]
        
        # Update Labels
        self.count_label.configure(text=f"Page {self.current_page} of {total_pages} ({total_items} items)")
        self.lbl_page.configure(text=f"Page {self.current_page} of {total_pages}")
        
        # Update Buttons
        self.btn_prev.configure(state="normal" if self.current_page > 1 else "disabled")
        self.btn_next.configure(state="normal" if self.current_page < total_pages else "disabled")

        # Diffing Logic
        new_ids = {item.get("timestamp"): item for item in visible_items}
        current_ids = set(self.current_items.keys())
        
        to_add = [item for ts, item in new_ids.items() if ts not in current_ids]
        to_remove = current_ids - set(new_ids.keys())
        
        # Remove items not in current page
        for ts in to_remove:
            if ts in self.current_items:
                widget = self.current_items.pop(ts)
                widget.destroy()

        # Add items
        # Sort additions by timestamp ASC (Oldest->Newest within usage)
        # so when we pack `before=first`, they stack correctly?
        # Actually logic is tricky when jumping pages.
        # Simplest consistent visual:
        # If we just switched pages, `to_remove` is EVERYTHING from old page.
        # `to_add` is EVERYTHING from new page.
        # We effectively clear and rebuild.
        # BUT Diffing saves us if existing items overlap (rare in pagination unless 1 item shift).
        
        # Sorted Add: Oldest first in the current selection
        sorted_add = sorted(to_add, key=lambda x: x.get("timestamp", ""))
        
        # Get anchor
        first_child = None
        children = self.container.winfo_children()
        # Ignore pagination controls for logic
        content_children = [c for c in children if c != self.controls_frame]
        if content_children:
            first_child = content_children[0]
            
        for item in sorted_add:
            card = self.create_card(item)
            if first_child:
                try:
                    card.pack(fill="x", pady=6, before=first_child)
                    first_child = card
                except:
                    card.pack(fill="x", pady=6)
            else:
                card.pack(fill="x", pady=6)
                first_child = card
            self.current_items[item.get("timestamp")] = card

        # Manage Controls Frame position (Always bottom)
        self.controls_frame.pack_forget()
        if total_pages > 1:
            self.controls_frame.pack(pady=20)
            
        self.container.update_idletasks()

    def create_card(self, item):
        content = item.get("content", "")
        item_type = item.get("type", "text")
        timestamp = item.get("timestamp", "")
        
        card = ctk.CTkFrame(self.container, fg_color=COLOR_SURFACE, 
                          corner_radius=10, border_width=1, border_color=COLOR_BORDER)
        
        # Hover
        def on_enter(e): card.configure(border_color=COLOR_ACCENT, fg_color=COLOR_HOVER)
        def on_leave(e): card.configure(border_color=COLOR_BORDER, fg_color=COLOR_SURFACE)
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        card.grid_columnconfigure(1, weight=1)
        
        # Icon
        icon_char = "📝"
        if item_type == "url": icon_char = "🔗"
        elif item_type == "image": icon_char = "🖼️"
        
        ctk.CTkLabel(card, text=icon_char, font=ctk.CTkFont(size=22)).grid(
            row=0, column=0, rowspan=2, padx=15, pady=15)
        
        # Content
        preview = item.get("preview", "") or content[:100]
        preview = preview.replace("\n", " ").strip()
        if len(preview) > 50: preview = preview[:47] + "..."
        
        ctk.CTkLabel(card, text=preview, 
                   font=ctk.CTkFont(size=14, weight="bold"),
                   text_color=COLOR_TEXT_PRIMARY, anchor="w").grid(
                       row=0, column=1, sticky="w", pady=(12, 2))
        
        # Meta
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%H:%M • %b %d")
        except:
            time_str = ""
            
        meta_text = f"{item_type.upper()}"
        if time_str: meta_text += f" • {time_str}"
            
        ctk.CTkLabel(card, text=meta_text, 
                   font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_META).grid(
                       row=1, column=1, sticky="w", pady=(0, 12))
        
        # Actions
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, padx=15)
        
        # Small buttons
        btn_copy = ctk.CTkButton(actions, text="Copy", width=50, height=26,
                               font=ctk.CTkFont(size=11, weight="bold"),
                               fg_color=COLOR_BORDER, hover_color=COLOR_HOVER,
                               command=lambda: copy_history_item(self.app, content))
        btn_copy.pack(side="right", padx=3)
        
        if item_type in ["url", "image"] or (item_type == "text" and content.startswith("http")):
             btn_open = ctk.CTkButton(actions, text="Open", width=50, height=26,
                                    font=ctk.CTkFont(size=11, weight="bold"),
                                    fg_color=COLOR_BORDER, hover_color=COLOR_HOVER,
                                    command=lambda: open_file(content))
             btn_open.pack(side="right", padx=3)

        return card

def create_history_frame(app):
    app.history_frame = HistoryFrame(app.main_frame, app)
    return app.history_frame

def copy_history_item(app, content):
    app.clipboard_clear()
    app.clipboard_append(content)
    app.update()
    app.status_label.configure(text="Copied!", text_color="#00E676")
    app.after(2000, lambda: app.status_label.configure(text="● Active", text_color="#00E676"))

def open_file(path_or_url):
    try:
        if platform.system() == 'Linux':
            subprocess.call(['xdg-open', path_or_url])
        elif platform.system() == 'Darwin':
            subprocess.call(['open', path_or_url])
        elif platform.system() == 'Windows':
            os.startfile(path_or_url)
    except Exception as e:
        print(f"Error opening: {e}")
