# -*- coding: utf-8 -*-
"""
glass.py - Verified acrylic-frost engine for ComfyUI Uncensored.

PROBLEM (verified on this machine, 2026-07-31):
  - Windows 11 native Mica/Acrylic (SetWindowCompositionAttribute) -> blocked (HVCI / Insider)
  - Documented DwmSetWindowAttribute attr 38/33/20 -> E_NOTIMPL
  - win32mica.ApplyMica (undocumented 1029) -> fails
  So the OS will not paint glass. This module EMULATES real frosted acrylic
  in-app (the same technique Chrome/Firefox/Electron use): capture the desktop
  region behind the window, blur + periwinkle-tint it, display as the root's
  background label. Verified working on this build.
"""
import random
import ctypes
import time
import tkinter as tk
from PIL import Image, ImageFilter, ImageTk, ImageDraw, ImageFont

user32 = getattr(ctypes, "windll", None).user32 if hasattr(ctypes, "windll") else None
GDI32 = getattr(ctypes, "windll", None).gdi32 if hasattr(ctypes, "windll") else None
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
BI_RGB = 0
DIB_RGB_COLORS = 0
BLUR_RADIUS = 18
TINT = (0, 20, 8, 80)  # Matrix deep cyber emerald tint
_CAPTURE_SCALE = 1.0

# Matrix digital glyphs cache
_MATRIX_GLYPHS = "0123456789ABCDEFｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ=-+*~|<>/\\"

def _get_matrix_font(size=14):
    for fpath in (
        r"C:\Windows\Fonts\msgothic.ttc",
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\CascadiaCode.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        try:
            return ImageFont.truetype(fpath, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _capture_desktop_region(rx, ry, w, h):
    """Legacy desktop capture — retained for API compatibility, not actively used."""
    try:
        hwnd_desk = user32.GetDesktopWindow()
        hdc_screen = user32.GetDC(hwnd_desk)
        hbmp = GDI32.CreateCompatibleBitmap(hdc_screen, w, h)
        hdc_mem = GDI32.CreateCompatibleDC(hdc_screen)
        GDI32.SelectObject(hdc_mem, hbmp)
        user32.PrintWindow(hwnd_desk, hdc_mem, CAPTUREBLT)
        GDI32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY)
        import struct, io
        bmi = ctypes.create_string_buffer(40)
        ctypes.memset(bmi, 0, 40)
        struct.pack_into("i i i i I i i i i i i", bmi, 0, 40, w, -h, 1, 32, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        GDI32.GetDIBits(hdc_mem, hbmp, 0, h, buf, bmi)
        GDI32.DeleteObject(hbmp)
        GDI32.DeleteDC(hdc_mem)
        raw = bytes(buf)
        img = Image.frombuffer("RGBA", (w, h), raw, "raw", "BGRA")
        user32.ReleaseDC(hwnd_desk, hdc_screen)
        return img
    except Exception:
        return Image.new("RGBA", (max(1, w), max(1, h)), (4, 10, 6, 255))


def make_acrylic(w, h, root=None, mode=None):
    """Frosted Matrix Cyber Glass rendered in PIL/NumPy with digital rain."""
    if mode is None:
        try:
            import customtkinter as ctk
            mode = ctk.get_appearance_mode()
        except Exception:
            mode = "dark"

    w, h = max(1, w), max(1, h)
    if str(mode).lower() == "light":
        base = Image.new("RGBA", (w, h), (240, 253, 244, 255))
        try:
            frost = make_gradient(w, h, (230, 248, 235), (210, 240, 220), angle=45)
        except Exception:
            frost = base
        tint = Image.new("RGBA", (w, h), (200, 250, 215, 60))
    else:
        # Deep Matrix Obsidian Green
        base = Image.new("RGBA", (w, h), (4, 10, 6, 255))
        try:
            frost = make_gradient(w, h, (3, 8, 5), (10, 24, 15), angle=135)
        except Exception:
            frost = base
        tint = Image.new("RGBA", (w, h), TINT)

    out = Image.alpha_composite(base, frost)
    out = Image.alpha_composite(out, tint)

    # Add procedural subtle Matrix digital rain streams
    try:
        rain_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(rain_layer)
        font = _get_matrix_font(13)
        
        # Deterministic seed per size for smooth resizing
        rng = random.Random(42)
        step_x = 28
        for x in range(12, w, step_x):
            stream_len = rng.randint(10, 30)
            start_y = rng.randint(-300, max(0, h - 100))
            for i in range(stream_len):
                y = start_y + i * 18
                if 0 <= y <= h:
                    ch = rng.choice(_MATRIX_GLYPHS)
                    progress = i / stream_len
                    if i == stream_len - 1:
                        col = (200, 255, 220, 110)
                    elif i > stream_len - 3:
                        col = (0, 255, 102, 90)
                    else:
                        alpha = int(8 + progress * 45)
                        col = (0, int(100 + progress * 100), int(35 + progress * 35), alpha)
                    d.text((x, y), ch, fill=col, font=font)
        out = Image.alpha_composite(out, rain_layer)
    except Exception:
        pass

    return out


def make_gradient(w, h, c0, c1, angle=45):
    """Diagonal gradient (NumPy vectorized — fast)."""
    import math
    import numpy as np
    img = np.zeros((h, w, 4), dtype=np.uint8)
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    x_grid = np.arange(w, dtype=np.float32).reshape(1, w, 1)
    y_grid = np.arange(h, dtype=np.float32).reshape(h, 1, 1)
    t = (x_grid * dx + y_grid * dy) / (w * abs(dx) + h * abs(dy) + 1)
    t = np.clip(t, 0, 1)
    rgb = np.array([c0[0], c0[1], c0[2]], dtype=np.float32)
    rgb_diff = np.array([c1[0] - c0[0], c1[1] - c0[1], c1[2] - c0[2]], dtype=np.float32)
    img[:, :, :3] = (rgb + rgb_diff * t).astype(np.uint8)
    img[:, :, 3] = 255
    return Image.fromarray(img, "RGBA")


def make_button_gradient(w, h):
    """Neon Matrix green gradient for cyber buttons."""
    return make_gradient(w, h, (0, 255, 102), (0, 204, 85), angle=90)


def make_sidebar_gradient(w, h):
    """Subtle matrix dark gradient behind the sidebar logo area."""
    return make_gradient(w, h, (10, 26, 16), (4, 12, 7), angle=90)


def _hue_shift_color(rgb, deg):
    """Rotate hue of an RGB tuple by deg degrees for subtle matrix glow animation."""
    import colorsys
    r, g, b = rgb[0] / 255, rgb[1] / 255, rgb[2] / 255
    hh, ss, vv = colorsys.rgb_to_hsv(r, g, b)
    hh = (hh + deg / 360.0) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hh, ss, vv)
    return (int(r * 255), int(g * 255), int(b * 255))


class MatrixRainCanvas(tk.Canvas):
    """High-Performance Live Matrix Digital Rain Background Canvas.

    Renders real falling Katakana/digit green rain streams using canvas item
    pooling (coords/itemconfigure) — zero object allocation per frame.
    Target ~20 FPS with near-zero CPU idle overhead.
    """
    CHARS = list("ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ9876543210ABCDEF+-*/<>$#@%&")

    # Pre-computed green shades (head=bright, tail=dim) to avoid per-frame hex conversion
    _SHADES = [
        "#001A08", "#002A0E", "#003A14", "#004A1A", "#005A20",
        "#006A26", "#007A2C", "#008A32", "#009A38", "#00AA3E",
        "#00BB44", "#00CC4A", "#00DD50", "#00EE56", "#00FF66",
        "#44FF88", "#88FFAA", "#BBFFCC", "#DDFFE8", "#EEFFEE",
    ]

    def __init__(self, master, font_size=13, fps=20, **kwargs):
        kwargs.setdefault("bg", "#040A06")
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self.font_size = font_size
        self._target_ms = max(16, 1000 // fps)  # frame interval
        self.running = False
        self._resize_job = None
        self._tick_job = None
        self._last_time = 0.0
        self._cols = 0
        self._rows = 0
        self._streams = []  # list of stream dicts
        self._items = []    # pre-allocated canvas text item IDs
        self._rng = random.Random(42)

        # Resolve font family for canvas text (prefer MS Gothic for Katakana)
        self._font_family = "Consolas"
        for fam in ("MS Gothic", "MS PGothic", "Yu Gothic", "Consolas"):
            try:
                import tkinter.font as tkfont
                if fam in tkfont.families():
                    self._font_family = fam
                    break
            except Exception:
                break

        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event=None):
        """Debounced resize — reallocate columns after 200ms of inactivity."""
        if not self.winfo_exists():
            return
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(200, self._rebuild_pool)

    def _rebuild_pool(self):
        """Reallocate the canvas item pool to match current window dimensions."""
        self._resize_job = None
        try:
            if not self.winfo_exists():
                return
            w = max(10, self.winfo_width())
            h = max(10, self.winfo_height())

            col_w = max(14, self.font_size + 2)
            row_h = max(16, self.font_size + 4)
            self._cols = max(1, w // col_w)
            self._rows = max(1, h // row_h)
            self._col_w = col_w
            self._row_h = row_h

            # Delete old items and rebuild
            self.delete("all")

            # Subtle cyber grid lines (behind rain)
            grid_step = max(32, self.font_size * 3)
            for x in range(0, w, grid_step):
                self.create_line(x, 0, x, h, fill="#08140C", width=1, tags="grid")
            for y in range(0, h, grid_step):
                self.create_line(0, y, w, y, fill="#08140C", width=1, tags="grid")

            # Pre-allocate text items (one per visible cell)
            self._items = []
            canvas_font = (self._font_family, self.font_size)
            for col in range(self._cols):
                col_items = []
                x = col * col_w + col_w // 2
                for row in range(self._rows + 2):  # +2 for overflow
                    y = row * row_h
                    item_id = self.create_text(
                        x, y, text="", fill="#040A06", font=canvas_font,
                        anchor="center", tags="rain"
                    )
                    col_items.append(item_id)
                self._items.append(col_items)

            # Initialize stream state for each column
            self._streams = []
            for col in range(self._cols):
                self._streams.append(self._new_stream(col))

        except Exception:
            pass

    def _new_stream(self, col):
        """Create a new random rain stream for a column."""
        rng = self._rng
        stream_len = rng.randint(6, min(self._rows, 22))
        return {
            "y": rng.uniform(-stream_len * 2, -1),  # start above screen
            "speed": rng.uniform(0.3, 1.2),          # cells per frame
            "length": stream_len,
            "chars": [rng.choice(self.CHARS) for _ in range(stream_len)],
            "change_timer": rng.randint(3, 8),       # frames until char randomization
        }

    def _tick(self):
        """Main animation frame — update stream positions and canvas items."""
        if not self.running:
            return
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        now = time.perf_counter()
        dt = min(now - self._last_time, 0.1) if self._last_time > 0 else 0.05
        self._last_time = now
        speed_mult = dt * 20  # normalize to ~20 FPS baseline

        rng = self._rng
        num_shades = len(self._SHADES)
        max_row = self._rows + 1

        for col_idx, stream in enumerate(self._streams):
            if col_idx >= len(self._items):
                break
            col_items = self._items[col_idx]

            # Advance position
            stream["y"] += stream["speed"] * speed_mult

            # Randomize characters periodically
            stream["change_timer"] -= 1
            if stream["change_timer"] <= 0:
                stream["change_timer"] = rng.randint(3, 8)
                idx = rng.randint(0, len(stream["chars"]) - 1)
                stream["chars"][idx] = rng.choice(self.CHARS)

            head_y = stream["y"]
            slen = stream["length"]

            # Update each visible cell in this column
            for row_idx, item_id in enumerate(col_items):
                dist_from_head = head_y - row_idx
                if 0 <= dist_from_head < slen:
                    # This cell is part of the active stream
                    char_idx = int(dist_from_head) % len(stream["chars"])
                    char = stream["chars"][char_idx]

                    # Brightness: head = bright white-green, tail = dim
                    brightness = 1.0 - (dist_from_head / slen)
                    shade_idx = min(num_shades - 1, int(brightness * (num_shades - 1)))
                    color = self._SHADES[shade_idx]

                    try:
                        self.itemconfigure(item_id, text=char, fill=color)
                    except tk.TclError:
                        return
                else:
                    # Clear cell (transparent = match background)
                    try:
                        cur = self.itemcget(item_id, "text")
                        if cur:
                            self.itemconfigure(item_id, text="", fill="#040A06")
                    except tk.TclError:
                        return

            # Reset stream when it falls fully off screen
            if head_y - slen > max_row:
                self._streams[col_idx] = self._new_stream(col_idx)

        # Schedule next frame
        try:
            if self.winfo_exists():
                self._tick_job = self.after(self._target_ms, self._tick)
        except Exception:
            pass

    def start(self):
        """Start the rain animation."""
        self.running = True
        self._last_time = time.perf_counter()
        # Signal to AcrylicBackground to skip heavy PIL compositing
        try:
            self.master._matrix_rain_active = True
        except Exception:
            pass
        self._rebuild_pool()
        self._tick()

    def stop(self):
        """Stop the rain animation and cancel pending timers."""
        self.running = False
        try:
            self.master._matrix_rain_active = False
        except Exception:
            pass
        if self._tick_job is not None:
            try:
                self.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
            self._resize_job = None


class AcrylicBackground:
    def __init__(self, root, behind=None):
        self.root = root
        self.behind = behind
        self._last_w = 0
        self._last_h = 0
        bg_color = "#040A06"
        try:
            import customtkinter as ctk
            mode = ctk.get_appearance_mode().lower()
            bg_color = "#F0FDF4" if mode == "light" else "#040A06"
        except Exception:
            pass
        self.label = tk.Label(root, bg=bg_color)
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self._job = None
        self._refresh(immediate=True)
        root.bind("<Configure>", self._on_configure)

    def _on_configure(self, _e=None):
        # Skip heavy PIL compositing entirely when MatrixRainCanvas handles the background
        if getattr(self.root, '_matrix_rain_active', False):
            return
        # Size-delta threshold: ignore sub-5px changes to prevent redundant re-renders
        try:
            if not self.root.winfo_exists():
                return
            new_w = self.root.winfo_width()
            new_h = self.root.winfo_height()
            if self._last_w > 0 and abs(new_w - self._last_w) < 5 and abs(new_h - self._last_h) < 5:
                return
        except Exception:
            pass
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except (tk.TclError, RuntimeError):
                pass
        self._job = self.root.after(600, self._refresh)

    def _refresh(self, immediate=False):
        try:
            if not self.root.winfo_exists():
                return
            # Skip when MatrixRainCanvas is running (it handles the background)
            if getattr(self.root, '_matrix_rain_active', False):
                return
            try:
                import customtkinter as ctk
                mode = ctk.get_appearance_mode().lower()
                bg_color = "#F0FDF4" if mode == "light" else "#040A06"
                self.label.configure(bg=bg_color)
            except Exception:
                pass
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            if w < 2 or h < 2:
                return
            if not self.root.winfo_ismapped():
                return
            # Cache dimensions to avoid re-rendering same size
            if w == self._last_w and h == self._last_h and not immediate:
                return
            self._last_w = w
            self._last_h = h
            img = make_acrylic(w, h, self.behind or self.root)
            self._tkimg = ImageTk.PhotoImage(img)
            self.label.configure(image=self._tkimg)
            self.label.image = self._tkimg
        except Exception:
            pass

    def refresh(self):
        self._refresh(immediate=True)


