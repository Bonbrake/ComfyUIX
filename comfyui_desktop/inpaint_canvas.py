"""
inpaint_canvas.py - Interactive Inpainting Canvas & Mask Drawing Studio
Provides brush painting, erasing, mask inversion, and mask export for ComfyUI.
"""
import os
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageOps
from comfyui_desktop.widgets import ToolTip

class InpaintCanvas(ctk.CTkFrame):
    """Interactive Inpaint Canvas with live brush mask rendering."""
    def __init__(self, master, width=420, height=420, **kwargs):
        super().__init__(master, **kwargs)
        self.canvas_w = width
        self.canvas_h = height
        
        self.source_pil = None
        self.mask_pil = None
        self.mask_draw = None
        self.brush_size = 28
        self.erase_mode = False
        self._last_pt = None
        self._tk_display = None
        
        # Toolbar
        tb = ctk.CTkFrame(self, fg_color="#08140C", corner_radius=6)
        tb.pack(fill="x", padx=4, pady=(4, 6))
        
        ctk.CTkLabel(tb, text="Brush:", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color="#39FF8C").pack(side="left", padx=6)
        self.slider = ctk.CTkSlider(tb, from_=4, to=100, number_of_steps=48, command=self._on_brush_change, width=110)
        self.slider.set(self.brush_size)
        self.slider.pack(side="left", padx=4)
        
        self.erase_btn = ctk.CTkButton(tb, text="🖌️ Paint", width=70, height=24, font=ctk.CTkFont(family="Consolas", size=10),
                                      fg_color="#1C3D2E", hover_color="#2B5C45", text_color="#FFFFFF", command=self._toggle_erase)
        self.erase_btn.pack(side="left", padx=4)
        
        self.invert_btn = ctk.CTkButton(tb, text="🔄 Invert", width=65, height=24, font=ctk.CTkFont(family="Consolas", size=10),
                                       fg_color="#1C3D2E", hover_color="#2B5C45", text_color="#FFFFFF", command=self.invert_mask)
        self.invert_btn.pack(side="left", padx=4)
                       
        self.clear_btn = ctk.CTkButton(tb, text="🧹 Clear", width=60, height=24, font=ctk.CTkFont(family="Consolas", size=10),
                                      fg_color="#3D1C1C", hover_color="#5C2B2B", text_color="#FFFFFF", command=self.clear_mask)
        self.clear_btn.pack(side="left", padx=4)

        # Attach tooltips to toolbar controls for accessibility & micro-UX
        ToolTip(self.slider, title="Brush Size", description="Adjust inpaint mask brush diameter (4px to 100px).")
        ToolTip(self.erase_btn, title="Brush Mode", description="Toggle between painting mask coverage and erasing mask areas.")
        ToolTip(self.invert_btn, title="Invert Mask", description="Invert active inpaint mask areas across the canvas.")
        ToolTip(self.clear_btn, title="Clear Mask", description="Reset inpaint mask and erase all painted regions.")

        # Drawing Canvas
        self.canvas = tk.Canvas(self, width=self.canvas_w, height=self.canvas_h, bg="#040A06", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

    def _on_brush_change(self, val):
        self.brush_size = int(val)

    def _toggle_erase(self):
        self.erase_mode = not self.erase_mode
        self.erase_btn.configure(text="🧹 Erase" if self.erase_mode else "🖌️ Paint",
                                fg_color="#3D2A1C" if self.erase_mode else "#1C3D2E")

    def load_image(self, img_or_path):
        if isinstance(img_or_path, str):
            if not os.path.isfile(img_or_path): return
            self.source_pil = Image.open(img_or_path).convert("RGB")
        elif isinstance(img_or_path, Image.Image):
            self.source_pil = img_or_path.convert("RGB")
        else:
            return
            
        self.mask_pil = Image.new("L", self.source_pil.size, 0)
        self.mask_draw = ImageDraw.Draw(self.mask_pil)
        self._redraw()

    def clear_mask(self):
        if self.source_pil:
            self.mask_pil = Image.new("L", self.source_pil.size, 0)
            self.mask_draw = ImageDraw.Draw(self.mask_pil)
            self._redraw()

    def invert_mask(self):
        if self.mask_pil:
            self.mask_pil = ImageOps.invert(self.mask_pil)
            self.mask_draw = ImageDraw.Draw(self.mask_pil)
            self._redraw()

    def _get_scale_and_offset(self):
        if not self.source_pil:
            return 1.0, 0, 0
        w, h = self.source_pil.size
        cw = self.canvas.winfo_width() or self.canvas_w
        ch = self.canvas.winfo_height() or self.canvas_h
        scale = min(cw / w, ch / h)
        dw, dh = int(w * scale), int(h * scale)
        ox, oy = (cw - dw) // 2, (ch - dh) // 2
        return scale, ox, oy

    def _canvas_to_image_coords(self, cx, cy):
        scale, ox, oy = self._get_scale_and_offset()
        ix = (cx - ox) / scale
        iy = (cy - oy) / scale
        return ix, iy

    def _draw_stroke(self, pt1, pt2):
        if not self.mask_draw or not self.source_pil:
            return
        val = 0 if self.erase_mode else 255
        r = self.brush_size
        if pt1 == pt2:
            self.mask_draw.ellipse([pt1[0] - r, pt1[1] - r, pt1[0] + r, pt1[1] + r], fill=val)
        else:
            self.mask_draw.line([pt1, pt2], fill=val, width=r * 2)
            self.mask_draw.ellipse([pt2[0] - r, pt2[1] - r, pt2[0] + r, pt2[1] + r], fill=val)

    def _on_press(self, event):
        ix, iy = self._canvas_to_image_coords(event.x, event.y)
        self._last_pt = (ix, iy)
        self._draw_stroke(self._last_pt, self._last_pt)
        self._redraw()

    def _on_motion(self, event):
        ix, iy = self._canvas_to_image_coords(event.x, event.y)
        cur_pt = (ix, iy)
        if self._last_pt:
            self._draw_stroke(self._last_pt, cur_pt)
        self._last_pt = cur_pt
        self._redraw()

    def _on_release(self, event):
        self._last_pt = None
        self._redraw()

    def _redraw(self):
        if not self.source_pil:
            self.canvas.delete("all")
            return
            
        scale, ox, oy = self._get_scale_and_offset()
        w, h = self.source_pil.size
        dw, dh = max(1, int(w * scale)), max(1, int(h * scale))

        # Composite visual overlay: source RGB + semi-transparent green mask
        disp_rgb = self.source_pil.resize((dw, dh), Image.Resampling.BILINEAR)
        disp_mask = self.mask_pil.resize((dw, dh), Image.Resampling.NEAREST)
        
        overlay = disp_rgb.convert("RGBA")
        green_tint = Image.new("RGBA", (dw, dh), (57, 255, 140, 140))
        overlay.paste(green_tint, (0, 0), disp_mask)

        self._tk_display = ImageTk.PhotoImage(overlay)
        self.canvas.delete("all")
        self.canvas.create_image(ox, oy, anchor="nw", image=self._tk_display)

    def save_staged_inpaint(self, input_dir):
        """Save source image and inpaint mask to input_dir and return file paths."""
        if not self.source_pil or not self.mask_pil:
            return None, None
        os.makedirs(input_dir, exist_ok=True)
        img_p = os.path.join(input_dir, "inpaint_in.png")
        mask_p = os.path.join(input_dir, "inpaint_mask.png")
        self.source_pil.save(img_p)
        self.mask_pil.save(mask_p)
        return img_p, mask_p
