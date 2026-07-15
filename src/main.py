"""Secret Shop AutoAccept Bot — desktop UI."""

from __future__ import annotations

import ctypes
import json
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

# Allow `import bot` when running from source (or analyzing with PyInstaller)
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bot.actions.telegram import TelegramCommandPoller, apply_bot_profile  # noqa: E402
from bot.core.engine import AcceptEngine  # noqa: E402

BG = "#0b0b10"
RAIL = "#0c0c12"
PANEL = "#101016"
LINE = "#23232c"
TEXT = "#f2f2f2"
MUTED = "#8a8a8a"
ICON_MUTED = "#7a8499"
BLUE = "#4ea5ff"
BLUE_ACTIVE = "#3d9eff"
GREEN = "#2f9e44"
GREEN_HOVER = "#3db554"
RED = "#d64545"
RED_HOVER = "#e85a5a"
IDLE_DOT = "#6a6a6a"
TITLEBAR = "#0c0c12"
SCROLL_TROUGH = "#101016"
SCROLL_THUMB = "#2a2a34"
SCROLL_THUMB_HOVER = "#3a3a48"
SCROLL_ARROW = "#6e6e78"

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_SYSMENU = 0x00080000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_DLGMODALFRAME = 0x00000001
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
SW_MINIMIZE = 6
RDW_INVALIDATE = 0x0001
RDW_ERASE = 0x0004
RDW_FRAME = 0x0400
RDW_ALLCHILDREN = 0x0080

WIN_W = 600
WIN_H = 450

ERROR_ALREADY_EXISTS = 183
MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
SINGLE_INSTANCE_MUTEX = "Local\\SecretShop_AutoAccept_Bot_SingleInstance"
_mutex_handle = None


def ensure_single_instance() -> bool:
    """Return False (and show error dialog) if another instance is already running."""
    global _mutex_handle
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.windll.kernel32
    kernel32.SetLastError(0)
    handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX)
    if not handle:
        return True
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.user32.MessageBoxW(
            None,
            "Бот уже запущен.",
            "AutoAccept Bot",
            MB_OK | MB_ICONERROR,
        )
        kernel32.CloseHandle(handle)
        return False
    _mutex_handle = handle  # keep mutex until process exit
    return True


def app_dir() -> Path:
    """Writable directory next to the exe (or project root when run from source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def settings_path() -> Path:
    """Always resolve settings next to the exe / project root (not a stale import-time path)."""
    return app_dir() / "settings.json"


def resource_path(*parts: str) -> Path:
    """Resolve asset path for both source run and PyInstaller onefile."""
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[1]
    return base.joinpath(*parts)


def round_rect(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int, r: int = 10, **kwargs):
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class NavButton(tk.Frame):
    """Sidebar nav item with baked icon tiles — centering is in the PNG itself."""

    WIDTH = 56
    HEIGHT = 48
    TILE = 36
    _tiles: dict[str, dict[str, tk.PhotoImage]] = {}

    def __init__(self, master, kind: str, command):
        super().__init__(master, width=self.WIDTH, height=self.HEIGHT, bg=RAIL, cursor="hand2")
        self.pack_propagate(False)
        self.kind = kind
        self.command = command
        self.active = False
        self._hover = False

        self._ensure_tiles(kind)

        self.indicator = tk.Frame(self, width=3, bg=RAIL)
        self.indicator.place(x=0, y=10, width=3, height=self.HEIGHT - 20)

        self.tile = tk.Label(self, bg=RAIL, bd=0, highlightthickness=0)
        self.tile.place(relx=0.5, rely=0.5, x=2, anchor="center")

        for w in (self, self.tile, self.indicator):
            w.bind("<Button-1>", lambda _e: self.command())
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

        self._paint()

    @classmethod
    def _ensure_tiles(cls, kind: str) -> None:
        if kind in cls._tiles:
            return
        mapping = {
            "play": {
                "idle": "nav_play_idle.png",
                "hover": "nav_play_hover.png",
                "active": "nav_play_active.png",
            },
            "gear": {
                "idle": "nav_gear_idle.png",
                "hover": "nav_gear_hover.png",
                "active": "nav_gear_active.png",
            },
        }
        loaded: dict[str, tk.PhotoImage] = {}
        for state, name in mapping[kind].items():
            path = resource_path("assets", name)
            if path.exists():
                loaded[state] = tk.PhotoImage(file=str(path))
        cls._tiles[kind] = loaded

    def set_active(self, active: bool) -> None:
        self.active = active
        self._paint()

    def _on_enter(self, _event) -> None:
        self._hover = True
        self._paint()

    def _on_leave(self, _event) -> None:
        # Leaving child widgets can flicker; only clear if pointer left the whole button
        x, y = self.winfo_pointerxy()
        rx, ry = self.winfo_rootx(), self.winfo_rooty()
        if not (rx <= x < rx + self.WIDTH and ry <= y < ry + self.HEIGHT):
            self._hover = False
            self._paint()

    def _paint(self) -> None:
        tiles = self._tiles.get(self.kind, {})
        if self.active:
            key = "active"
            self.indicator.configure(bg=BLUE_ACTIVE)
        elif self._hover:
            key = "hover"
            self.indicator.configure(bg=RAIL)
        else:
            key = "idle"
            self.indicator.configure(bg=RAIL)

        img = tiles.get(key) or tiles.get("idle")
        if img is not None:
            self.tile.configure(image=img, bg=RAIL)
            self._img_ref = img


class TitleButton(tk.Canvas):
    """Minimize / close controls for the custom title bar."""

    def __init__(self, master, kind: str, command):
        super().__init__(
            master,
            width=46,
            height=32,
            bg=TITLEBAR,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.kind = kind
        self.command = command
        self._hover = False
        self.bind("<Button-1>", lambda _e: self.command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._paint()

    def _on_enter(self, _event) -> None:
        self._hover = True
        self._paint()

    def _on_leave(self, _event) -> None:
        self._hover = False
        self._paint()

    def _paint(self) -> None:
        self.delete("all")
        if self.kind == "close":
            bg = "#e81123" if self._hover else TITLEBAR
            fg = "#ffffff" if self._hover else MUTED
        else:
            bg = "#1a1a22" if self._hover else TITLEBAR
            fg = TEXT if self._hover else MUTED

        self.configure(bg=bg)
        self.create_rectangle(0, 0, 46, 32, fill=bg, outline="")

        if self.kind == "min":
            self.create_line(16, 16, 30, 16, fill=fg, width=1)
        else:
            self.create_line(17, 10, 29, 22, fill=fg, width=1)
            self.create_line(29, 10, 17, 22, fill=fg, width=1)


class AutoAcceptApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        # Build while hidden so native caption never flashes over the custom title bar
        self.withdraw()
        self.overrideredirect(True)
        self.title("AutoAccept Bot")
        self.configure(bg=BG)
        self.resizable(False, False)

        self.running = False
        self.current_tab = "main"
        self._drag_x = 0
        self._drag_y = 0
        self._run_started: float | None = None
        self._timer_job: str | None = None
        self._scrollbar_visible = False
        self._settings_save_job: str | None = None
        self._settings_ready = False
        self.settings = self._load_settings()
        self.engine = AcceptEngine(
            template_path=resource_path("bot", "vision", "buttons", "accept.png"),
            get_settings=lambda: self.settings,
            on_status=self._on_engine_status,
        )
        self.tg_poller = TelegramCommandPoller(get_settings=lambda: self.settings)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_clipboard_shortcuts()

        self._fonts()
        self._style_scrollbar()
        self._set_icon()
        self._build()
        self._show_tab("main")

        # Create HWND, strip native chrome, lock final size — all before first paint
        self.update_idletasks()
        self.update()
        self._apply_borderless(lock_size=False)
        self._center()
        self._apply_borderless(lock_size=True)
        self.update_idletasks()
        self.deiconify()
        self.lift()
        # If Windows restores caption on Map, re-strip styles only (never resize again)
        self.bind("<Map>", self._on_map)
        # Listen for Telegram /start while the app is open
        self.tg_poller.start()

    def _on_map(self, _event=None) -> None:
        if self.state() == "iconic":
            return
        self.after_idle(lambda: self._apply_borderless(lock_size=False))

    def _bind_clipboard_shortcuts(self) -> None:
        """Make Ctrl+C/V/X/A work even with RU keyboard layout (keycode-based)."""

        def _is_text_widget(widget) -> bool:
            try:
                return widget.winfo_class() in ("Entry", "Text", "TEntry")
            except tk.TclError:
                return False

        def _entry_has_selection(widget) -> bool:
            try:
                return bool(widget.selection_present())
            except tk.TclError:
                return False

        def _clipboard_get() -> str:
            try:
                return self.clipboard_get()
            except tk.TclError:
                return ""

        def do_paste(widget) -> None:
            text = _clipboard_get()
            if not text:
                return
            if widget.winfo_class() == "Text":
                try:
                    if widget.tag_ranges("sel"):
                        widget.delete("sel.first", "sel.last")
                except tk.TclError:
                    pass
                widget.insert("insert", text)
                return
            if _entry_has_selection(widget):
                widget.delete("sel.first", "sel.last")
            widget.insert("insert", text)

        def do_copy(widget) -> None:
            try:
                if widget.winfo_class() == "Text":
                    if not widget.tag_ranges("sel"):
                        return
                    data = widget.get("sel.first", "sel.last")
                else:
                    if not _entry_has_selection(widget):
                        return
                    data = widget.selection_get()
            except tk.TclError:
                return
            self.clipboard_clear()
            self.clipboard_append(data)
            try:
                self.update()
            except tk.TclError:
                pass

        def do_cut(widget) -> None:
            do_copy(widget)
            try:
                if widget.winfo_class() == "Text":
                    if widget.tag_ranges("sel"):
                        widget.delete("sel.first", "sel.last")
                elif _entry_has_selection(widget):
                    widget.delete("sel.first", "sel.last")
            except tk.TclError:
                pass

        def do_select_all(widget) -> None:
            try:
                if widget.winfo_class() == "Text":
                    widget.tag_add("sel", "1.0", "end-1c")
                    widget.mark_set("insert", "1.0")
                    widget.see("insert")
                else:
                    widget.select_range(0, "end")
                    widget.icursor("end")
            except tk.TclError:
                pass

        handlers = {
            65: do_select_all,  # A / Ф
            67: do_copy,  # C / С
            86: do_paste,  # V / М
            88: do_cut,  # X / Ч
        }

        def on_ctrl_key(event):
            if not (event.state & 0x4):
                return None
            handler = handlers.get(event.keycode)
            if handler is None:
                return None
            widget = event.widget
            if not _is_text_widget(widget):
                return None
            handler(widget)
            return "break"

        # Only keycode-based binding — layout-independent (EN/RU) and Tk-safe.
        # Do NOT bind <Control-c> / Cyrillic keysyms: they crash Tk ("bad keysym").
        for cls in ("Entry", "Text", "TEntry"):
            self.bind_class(cls, "<Control-KeyPress>", on_ctrl_key, add="+")

    def _style_scrollbar(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Neutral.Vertical.TScrollbar",
            background=SCROLL_THUMB,
            troughcolor=SCROLL_TROUGH,
            bordercolor=SCROLL_TROUGH,
            lightcolor=SCROLL_THUMB,
            darkcolor=SCROLL_THUMB,
            arrowcolor=SCROLL_ARROW,
            relief="flat",
            borderwidth=0,
            width=10,
        )
        style.map(
            "Neutral.Vertical.TScrollbar",
            background=[
                ("active", SCROLL_THUMB_HOVER),
                ("pressed", SCROLL_THUMB_HOVER),
                ("disabled", SCROLL_TROUGH),
            ],
            arrowcolor=[
                ("disabled", MUTED),
                ("active", TEXT),
            ],
        )

    def _set_icon(self) -> None:
        icon = resource_path("assets", "icon.ico")
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except tk.TclError:
                try:
                    self.iconbitmap(str(icon))
                except tk.TclError:
                    pass

    def _hwnd(self) -> int:
        self.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        return hwnd or int(self.winfo_id())

    def _apply_borderless(self, lock_size: bool = False) -> None:
        """Keep custom-only chrome + taskbar presence; optionally lock outer size."""
        if sys.platform != "win32":
            return
        try:
            # Ensure Tk stays without native decorations even after restore from tray/taskbar
            if not bool(self.overrideredirect()):
                self.overrideredirect(True)

            hwnd = self._hwnd()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MAXIMIZEBOX | WS_BORDER | WS_DLGFRAME)
            style |= WS_MINIMIZEBOX | WS_SYSMENU
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            exstyle = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            exstyle &= ~(WS_EX_TOOLWINDOW | WS_EX_CLIENTEDGE | WS_EX_WINDOWEDGE | WS_EX_DLGMODALFRAME)
            exstyle |= WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)

            if lock_size:
                geo = self.geometry()
                parts = geo.replace("-", "+").split("+")
                try:
                    x = int(parts[1]) if len(parts) > 1 else self.winfo_x()
                    y = int(parts[2]) if len(parts) > 2 else self.winfo_y()
                except ValueError:
                    x, y = self.winfo_x(), self.winfo_y()
                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    0,
                    x,
                    y,
                    WIN_W,
                    WIN_H,
                    SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
                )
                self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")
            else:
                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    0,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
                )

            ctypes.windll.user32.RedrawWindow(
                hwnd,
                None,
                None,
                RDW_INVALIDATE | RDW_ERASE | RDW_FRAME | RDW_ALLCHILDREN,
            )
        except Exception:
            pass

    def _center(self) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth() - WIN_W) // 2
        y = (self.winfo_screenheight() - WIN_H) // 2
        self.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")
        self.minsize(WIN_W, WIN_H)
        self.maxsize(WIN_W, WIN_H)

    def _fonts(self) -> None:
        family = "Segoe UI"
        available = set(tkfont.families())
        mono = "Cascadia Mono" if "Cascadia Mono" in available else (
            "Consolas" if "Consolas" in available else "Courier New"
        )
        self.font_logo = tkfont.Font(family=family, size=11, weight="bold")
        self.font_title = tkfont.Font(family=family, size=22, weight="bold")
        self.font_body = tkfont.Font(family=family, size=10)
        self.font_label = tkfont.Font(family=family, size=11, weight="bold")
        self.font_small = tkfont.Font(family=family, size=9)
        btn_family = "Bahnschrift" if "Bahnschrift" in available else family
        self.font_button = tkfont.Font(family=btn_family, size=12, weight="bold")
        self.font_mono = tkfont.Font(family=mono, size=8)
        self.font_caption = tkfont.Font(family=family, size=9)

    def _build(self) -> None:
        shell = tk.Frame(self, bg=LINE, bd=0, highlightthickness=1, highlightbackground=LINE)
        shell.pack(fill="both", expand=True)

        titlebar = tk.Frame(shell, bg=TITLEBAR, height=36)
        titlebar.pack(fill="x", side="top")
        titlebar.pack_propagate(False)

        title_label = tk.Label(
            titlebar,
            text="AutoAccept Bot",
            bg=TITLEBAR,
            fg=MUTED,
            font=self.font_caption,
            anchor="w",
        )
        title_label.pack(side="left", padx=14)

        for widget in (titlebar, title_label):
            widget.bind("<ButtonPress-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._on_drag)

        btns = tk.Frame(titlebar, bg=TITLEBAR)
        btns.pack(side="right")
        TitleButton(btns, "min", self._minimize).pack(side="left")
        TitleButton(btns, "close", self._on_close).pack(side="left")

        tk.Frame(shell, bg=LINE, height=1).pack(fill="x")

        # Footer first — stays pinned at the bottom
        footer = tk.Frame(shell, bg="#08080c", height=34)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text="Secret Shop  |  @Zxqwezxc",
            bg="#08080c",
            fg="#6e6e78",
            font=self.font_mono,
        ).pack(expand=True)
        tk.Frame(shell, bg=LINE, height=1).pack(fill="x", side="bottom")

        body = tk.Frame(shell, bg=BG)
        body.pack(fill="both", expand=True)

        rail = tk.Frame(body, bg=RAIL, width=56)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        logo = tk.Label(rail, bg=RAIL, bd=0, highlightthickness=0)
        logo.pack(pady=(14, 10))
        self._place_logo(logo)

        self.tab_main = NavButton(rail, "play", lambda: self._show_tab("main"))
        self.tab_main.pack()
        self.tab_settings = NavButton(rail, "gear", lambda: self._show_tab("settings"))
        self.tab_settings.pack(pady=(4, 0))

        tk.Frame(body, bg=LINE, width=1).pack(side="left", fill="y")

        stage = tk.Frame(body, bg=PANEL)
        stage.pack(side="left", fill="both", expand=True)
        self.stage = stage

        self.scrollbar = ttk.Scrollbar(
            stage,
            orient="vertical",
            style="Neutral.Vertical.TScrollbar",
            command=self._on_scrollbar,
        )
        # Packed only on settings tab — hidden on main/control

        self.scroll_canvas = tk.Canvas(stage, bg=PANEL, highlightthickness=0, bd=0)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        self.scroll_canvas.configure(yscrollcommand=self._on_canvas_scroll)

        self.content = tk.Frame(self.scroll_canvas, bg=PANEL)
        self._scroll_window = self.scroll_canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", self._on_scroll_content_configure)
        self.scroll_canvas.bind("<Configure>", self._on_scroll_canvas_configure)

        pad = tk.Frame(self.content, bg=PANEL)
        pad.pack(fill="both", expand=True, padx=28, pady=(24, 16))
        self.main_panel = self._build_main(pad)
        self.settings_panel = self._build_settings(pad)
        self._bind_mousewheel_tree(self.stage)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _place_logo(self, label: tk.Label) -> None:
        rail_logo = resource_path("assets", "logo_rail.png")
        fallback = resource_path("assets", "logo.png")
        path = rail_logo if rail_logo.exists() else fallback
        if not path.exists():
            label.configure(text="S", fg=TEXT, font=self.font_logo, width=4, height=2)
            return
        try:
            self._logo_image = tk.PhotoImage(file=str(path))
            label.configure(image=self._logo_image)
        except tk.TclError:
            label.configure(text="S", fg=TEXT, font=self.font_logo, width=4, height=2)

    def _minimize(self) -> None:
        if sys.platform == "win32":
            try:
                ctypes.windll.user32.ShowWindow(self._hwnd(), SW_MINIMIZE)
                return
            except Exception:
                pass
        self.iconify()

    def _start_drag(self, event) -> None:
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag(self, event) -> None:
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _build_main(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL)

        tk.Label(
            frame,
            text="Управление",
            bg=PANEL,
            fg=TEXT,
            font=self.font_title,
            anchor="w",
        ).pack(fill="x")

        status_box = tk.Frame(frame, bg=PANEL)
        status_box.pack(fill="x", pady=(22, 18))
        tk.Frame(status_box, bg=LINE, height=1).pack(fill="x")

        row = tk.Frame(status_box, bg=PANEL)
        row.pack(fill="x", pady=12)

        self.status_dot = tk.Canvas(row, width=12, height=12, bg=PANEL, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 10))
        self._draw_dot(IDLE_DOT)

        self.status_label = tk.Label(row, text="Остановлен", bg=PANEL, fg=TEXT, font=self.font_label)
        self.status_label.pack(side="left")

        self.timer_label = tk.Label(row, text="00:00", bg=PANEL, fg=MUTED, font=self.font_mono)
        self.timer_label.pack(side="right")

        tk.Frame(status_box, bg=LINE, height=1).pack(fill="x")

        self.toggle_wrap = tk.Frame(frame, width=132, height=40, bg=GREEN, cursor="hand2")
        self.toggle_wrap.pack(anchor="w")
        self.toggle_wrap.pack_propagate(False)

        self.toggle_btn = tk.Label(
            self.toggle_wrap,
            text="▶  Start",
            bg=GREEN,
            fg="#ffffff",
            font=self.font_button,
            cursor="hand2",
            bd=0,
            padx=0,
            pady=0,
        )
        self.toggle_btn.place(relx=0.5, rely=0.5, x=-2, anchor="center")

        for w in (self.toggle_wrap, self.toggle_btn):
            w.bind("<Button-1>", lambda _e: self._toggle_running())
            w.bind("<Enter>", lambda _e: self._on_toggle_hover(True))
            w.bind("<Leave>", lambda _e: self._on_toggle_hover(False))

        return frame

    def _build_settings(self, parent: tk.Frame) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL)
        tk.Label(
            frame,
            text="Настройки",
            bg=PANEL,
            fg=TEXT,
            font=self.font_title,
            anchor="w",
        ).pack(fill="x")

        # --- General ---
        tk.Label(
            frame,
            text="Общие",
            bg=PANEL,
            fg=BLUE,
            font=self.font_label,
            anchor="w",
        ).pack(fill="x", pady=(22, 10))

        self.auto_accept_var = tk.BooleanVar(value=bool(self.settings.get("auto_accept", True)))
        self._settings_checkbox(
            frame,
            "Автопринятие игры",
            self.auto_accept_var,
            hint="Если выключено, бот не будет принимать игру, а только пришлёт уведомление, что она найдена.",
        )

        # --- Telegram ---
        tk.Label(
            frame,
            text="Telegram-бот",
            bg=PANEL,
            fg=BLUE,
            font=self.font_label,
            anchor="w",
        ).pack(fill="x", pady=(18, 4))

        tk.Label(
            frame,
            text="Подключи своего Telegram-бота, чтобы получать алерты о найденной и принятой игре.",
            bg=PANEL,
            fg=MUTED,
            font=self.font_body,
            anchor="w",
            wraplength=420,
            justify="left",
        ).pack(fill="x", pady=(0, 14))

        self.tg_enabled_var = tk.BooleanVar(value=bool(self.settings.get("tg_enabled", False)))
        self._settings_checkbox(
            frame,
            "Включить Telegram-бота",
            self.tg_enabled_var,
        )

        self.tg_screenshot_var = tk.BooleanVar(value=bool(self.settings.get("tg_screenshot", True)))
        self._settings_checkbox(
            frame,
            "Отправлять скриншот при нахождении игры",
            self.tg_screenshot_var,
            hint="Бот пришлёт скриншот экрана, когда найдёт кнопку принятия.",
        )

        self.tg_token_var = tk.StringVar(value=str(self.settings.get("tg_token", "")))
        self.tg_chat_var = tk.StringVar(value=str(self.settings.get("tg_chat_id", "")))
        self._token_visible = False

        self._settings_token_field(frame)
        self._settings_field(frame, "Chat ID", self.tg_chat_var)
        self._wire_settings_autosave()

        actions = tk.Frame(frame, bg=PANEL)
        actions.pack(fill="x", pady=(16, 0))

        self.tg_save_btn = tk.Label(
            actions,
            text="Сохранить",
            bg=BLUE,
            fg="#ffffff",
            font=self.font_button,
            cursor="hand2",
            padx=16,
            pady=8,
        )
        self.tg_save_btn.pack(side="left")
        self.tg_save_btn.bind("<Button-1>", lambda _e: self._save_settings())
        self.tg_save_btn.bind("<Enter>", lambda _e: self.tg_save_btn.configure(bg="#7ec8ff"))
        self.tg_save_btn.bind("<Leave>", lambda _e: self.tg_save_btn.configure(bg=BLUE))

        self.tg_status = tk.Label(actions, text="", bg=PANEL, fg=MUTED, font=self.font_mono)
        self.tg_status.pack(side="left", padx=(12, 0))

        guide = (
            "Как создать бота и получить данные:\n"
            "1. Открой Telegram и найди @BotFather.\n"
            "2. Отправь /newbot, задай имя и username бота.\n"
            "3. BotFather пришлёт Bot Token — вставь его в поле выше.\n"
            "4. Напиши своему боту любое сообщение (например /start).\n"
            "5. Chat ID узнай через @userinfobot или @getidsbot — "
            "отправь им /start и скопируй свой Id."
        )
        tk.Label(
            frame,
            text=guide,
            bg=PANEL,
            fg=MUTED,
            font=self.font_small,
            anchor="w",
            justify="left",
            wraplength=420,
        ).pack(fill="x", pady=(20, 8))

        return frame

    def _settings_checkbox(
        self,
        parent: tk.Frame,
        title: str,
        var: tk.BooleanVar,
        hint: str | None = None,
        enabled: bool = True,
    ) -> None:
        block = tk.Frame(parent, bg=PANEL)
        block.pack(fill="x", pady=(0, 14), anchor="w")
        fg = MUTED if not enabled else TEXT
        cb = tk.Checkbutton(
            block,
            text=title,
            variable=var,
            onvalue=True,
            offvalue=False,
            bg=PANEL,
            fg=fg,
            disabledforeground=MUTED,
            activebackground=PANEL,
            activeforeground=fg,
            selectcolor="#141418",
            highlightthickness=0,
            bd=0,
            relief="flat",
            font=self.font_label,
            cursor="arrow" if not enabled else "hand2",
            anchor="w",
            justify="left",
            command=(lambda: self._save_settings(silent=True)) if enabled else None,
            state="normal" if enabled else "disabled",
        )
        cb.pack(side="top", anchor="w")
        if hint:
            tk.Label(
                block,
                text=hint,
                bg=PANEL,
                fg=MUTED,
                font=self.font_small,
                anchor="w",
                justify="left",
                wraplength=400,
            ).pack(fill="x", padx=(22, 0), pady=(4, 0))

    def _settings_field(self, parent: tk.Frame, title: str, var: tk.StringVar, show: str | None = None) -> None:
        block = tk.Frame(parent, bg=PANEL)
        block.pack(fill="x", pady=(0, 12))
        tk.Label(block, text=title, bg=PANEL, fg=TEXT, font=self.font_label, anchor="w").pack(fill="x")
        entry = tk.Entry(
            block,
            textvariable=var,
            bg="#141418",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=BLUE,
            font=self.font_mono,
            show=show or "",
        )
        entry.pack(fill="x", ipady=8, pady=(6, 0))
        entry.bind("<FocusOut>", lambda _e: self._save_settings(silent=True), add="+")
        entry.bind("<KeyRelease>", lambda _e: self._schedule_settings_save(), add="+")

    def _settings_token_field(self, parent: tk.Frame) -> None:
        block = tk.Frame(parent, bg=PANEL)
        block.pack(fill="x", pady=(0, 12))
        tk.Label(block, text="Bot Token", bg=PANEL, fg=TEXT, font=self.font_label, anchor="w").pack(fill="x")

        row = tk.Frame(block, bg=PANEL)
        row.pack(fill="x", pady=(6, 0))

        self.tg_token_entry = tk.Entry(
            row,
            textvariable=self.tg_token_var,
            bg="#141418",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=BLUE,
            font=self.font_mono,
            show="•",
        )
        self.tg_token_entry.pack(side="left", fill="x", expand=True, ipady=8)
        self.tg_token_entry.bind("<FocusOut>", lambda _e: self._save_settings(silent=True), add="+")
        self.tg_token_entry.bind("<KeyRelease>", lambda _e: self._schedule_settings_save(), add="+")

        self.tg_token_toggle = tk.Label(
            row,
            text="Показать",
            bg="#1a1a22",
            fg=MUTED,
            font=self.font_small,
            cursor="hand2",
            padx=10,
            pady=10,
        )
        self.tg_token_toggle.pack(side="left", padx=(8, 0))
        self.tg_token_toggle.bind("<Button-1>", lambda _e: self._toggle_token_visibility())
        self.tg_token_toggle.bind("<Enter>", lambda _e: self.tg_token_toggle.configure(fg=TEXT, bg="#24242e"))
        self.tg_token_toggle.bind("<Leave>", lambda _e: self.tg_token_toggle.configure(fg=MUTED, bg="#1a1a22"))

    def _toggle_token_visibility(self) -> None:
        self._token_visible = not self._token_visible
        if self._token_visible:
            self.tg_token_entry.configure(show="")
            self.tg_token_toggle.configure(text="Скрыть")
        else:
            self.tg_token_entry.configure(show="•")
            self.tg_token_toggle.configure(text="Показать")

    def _default_settings(self) -> dict:
        return {
            "auto_accept": True,
            "tg_enabled": False,
            "tg_screenshot": True,
            "tg_token": "",
            "tg_chat_id": "",
        }

    def _wire_settings_autosave(self) -> None:
        """Persist every user-facing setting as soon as it changes."""
        for var in (
            self.auto_accept_var,
            self.tg_enabled_var,
            self.tg_screenshot_var,
        ):
            var.trace_add("write", lambda *_args: self._schedule_settings_save())
        for var in (self.tg_token_var, self.tg_chat_var):
            var.trace_add("write", lambda *_args: self._schedule_settings_save())
        self._settings_ready = True
        # Normalize file to full schema on first open
        self._save_settings(silent=True)

    def _schedule_settings_save(self) -> None:
        if not self._settings_ready:
            return
        if self._settings_save_job is not None:
            try:
                self.after_cancel(self._settings_save_job)
            except Exception:
                pass
        self._settings_save_job = self.after(250, lambda: self._save_settings(silent=True))

    def _load_settings(self) -> dict:
        defaults = self._default_settings()
        path = settings_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    defaults.update(data)
            except (OSError, json.JSONDecodeError):
                pass
        return defaults

    def _collect_settings(self) -> dict:
        return {
            "auto_accept": bool(self.auto_accept_var.get()),
            "tg_enabled": bool(self.tg_enabled_var.get()),
            "tg_screenshot": bool(self.tg_screenshot_var.get()),
            "tg_token": self.tg_token_var.get().strip(),
            "tg_chat_id": self.tg_chat_var.get().strip(),
        }

    def _save_settings(self, silent: bool = False) -> None:
        if not hasattr(self, "auto_accept_var"):
            return
        self.settings = self._collect_settings()
        path = settings_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self.settings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            if not silent:
                token = self.settings["tg_token"]
                profile_ok = False
                if token:
                    try:
                        profile_ok = bool(apply_bot_profile(token))
                    except Exception:
                        profile_ok = False
                if token and profile_ok:
                    self.tg_status.configure(text="Сохранено · описание TG обновлено", fg=GREEN)
                else:
                    self.tg_status.configure(text="Сохранено", fg=GREEN)
                self.after(2500, lambda: self.tg_status.configure(text=""))
        except OSError:
            if not silent:
                self.tg_status.configure(text="Ошибка сохранения", fg=RED)
                self.after(2500, lambda: self.tg_status.configure(text=""))

    def _show_tab(self, name: str) -> None:
        self.current_tab = name
        self.tab_main.set_active(name == "main")
        self.tab_settings.set_active(name == "settings")
        self.main_panel.pack_forget()
        self.settings_panel.pack_forget()
        if name == "main":
            self.main_panel.pack(fill="both", expand=True)
            self._set_scrollbar_visible(False)
        else:
            self.settings_panel.pack(fill="both", expand=True)
            self._set_scrollbar_visible(True)
        self.scroll_canvas.yview_moveto(0)
        self.after_idle(self._sync_scrollregion)

    def _set_scrollbar_visible(self, visible: bool) -> None:
        if visible == self._scrollbar_visible and (
            self.scrollbar.winfo_ismapped() == visible
        ):
            return
        self._scrollbar_visible = visible
        self.scroll_canvas.pack_forget()
        self.scrollbar.pack_forget()
        if visible:
            self.scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.pack(side="left", fill="both", expand=True)

    def _on_scroll_content_configure(self, _event=None) -> None:
        self._sync_scrollregion()

    def _on_scroll_canvas_configure(self, event) -> None:
        self.scroll_canvas.itemconfigure(self._scroll_window, width=event.width)
        self._sync_scrollregion()

    def _sync_scrollregion(self) -> None:
        self.scroll_canvas.update_idletasks()
        bbox = self.scroll_canvas.bbox("all")
        if bbox:
            self.scroll_canvas.configure(scrollregion=bbox)

    def _on_canvas_scroll(self, first: str, last: str) -> None:
        if self._scrollbar_visible:
            self.scrollbar.set(first, last)

    def _on_scrollbar(self, *args) -> None:
        self.scroll_canvas.yview(*args)

    def _bind_mousewheel_tree(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_mousewheel_tree(child)

    def _pointer_over_stage(self) -> bool:
        try:
            x, y = self.winfo_pointerxy()
            rx, ry = self.stage.winfo_rootx(), self.stage.winfo_rooty()
            rw, rh = self.stage.winfo_width(), self.stage.winfo_height()
            return rx <= x < rx + rw and ry <= y < ry + rh
        except tk.TclError:
            return False

    def _on_mousewheel(self, event) -> None:
        if self.current_tab != "settings":
            return
        if not self._pointer_over_stage():
            return
        bbox = self.scroll_canvas.bbox("all")
        if not bbox:
            return
        content_h = bbox[3] - bbox[1]
        if content_h <= self.scroll_canvas.winfo_height():
            return
        steps = int(-event.delta / 120)
        if steps == 0:
            steps = -1 if event.delta > 0 else 1
        self.scroll_canvas.yview_scroll(steps, "units")
        return "break"

    def _draw_dot(self, color: str) -> None:
        self.status_dot.delete("all")
        self.status_dot.create_oval(2, 2, 10, 10, fill=color, outline="")

    def _format_elapsed(self, seconds: float) -> str:
        total = max(0, int(seconds))
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h:d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _tick_timer(self) -> None:
        self._timer_job = None
        if self.running and self._run_started is not None:
            elapsed = time.monotonic() - self._run_started
            self.timer_label.configure(text=self._format_elapsed(elapsed), fg=GREEN)
            self._timer_job = self.after(250, self._tick_timer)

    def _stop_timer(self) -> None:
        if self._timer_job is not None:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None
        self._run_started = None
        self.timer_label.configure(text="00:00", fg=MUTED)

    def _on_toggle_hover(self, hovering: bool) -> None:
        if self.running:
            color = RED_HOVER if hovering else RED
        else:
            color = GREEN_HOVER if hovering else GREEN
        self.toggle_wrap.configure(bg=color)
        self.toggle_btn.configure(bg=color)

    def _toggle_running(self) -> None:
        if self.running:
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self) -> None:
        template = resource_path("bot", "vision", "buttons", "accept.png")
        if not template.exists():
            self.status_label.configure(text="Нет шаблона accept.png")
            return
        # Pull latest values from UI vars before running
        self._save_settings(silent=True)
        try:
            self.engine.start()
        except Exception as exc:
            self.status_label.configure(text=f"Не удалось запустить: {exc}")
            return

        self.running = True
        self._draw_dot(GREEN)
        self.status_label.configure(text="Автопринятие активно")
        self.toggle_wrap.configure(bg=RED)
        self.toggle_btn.configure(text="■  Stop", bg=RED, fg="#ffffff")
        self._run_started = time.monotonic()
        self.timer_label.configure(text="00:00", fg=GREEN)
        self._tick_timer()

    def _stop_bot(self) -> None:
        self.engine.stop()
        self.running = False
        self._draw_dot(IDLE_DOT)
        self.status_label.configure(text="Остановлен")
        self.toggle_wrap.configure(bg=GREEN)
        self.toggle_btn.configure(text="▶  Start", bg=GREEN, fg="#ffffff")
        self._stop_timer()

    def _on_engine_status(self, text: str) -> None:
        # Called from worker thread — hop back to UI thread
        self.after(0, lambda t=text: self._apply_engine_status(t))

    def _apply_engine_status(self, text: str) -> None:
        if not self.running:
            return
        # Keep timer visible; flash short status for events, then restore
        self.status_label.configure(text=text)
        self.after(2500, self._restore_running_status)

    def _restore_running_status(self) -> None:
        if self.running:
            self.status_label.configure(text="Автопринятие активно")

    def _on_close(self) -> None:
        try:
            self._save_settings(silent=True)
        except Exception:
            pass
        try:
            self.tg_poller.stop()
        except Exception:
            pass
        try:
            self.engine.stop()
        except Exception:
            pass
        self.destroy()


def main() -> None:
    if not ensure_single_instance():
        return
    app = AutoAcceptApp()
    app.mainloop()


if __name__ == "__main__":
    main()
