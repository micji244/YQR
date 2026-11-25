# -*- coding: utf-8 -*-
"""YQR - QR Code Generator  v2.1.0

Major update:
  * Content presets: URL / Wi-Fi / vCard / Email / SMS / Plain text
  * Design templates: pick a ready-made look (colored finder "eyes",
    module shapes, CTA caption) and tweak colors live
  * Module shapes: square / rounded / circle / vertical bars / horizontal bars
  * Blue-ish theme matching the app logo
  * Teal scanner tab (scan / decode from image or clipboard)
"""
import os
import sys
import io
import webbrowser
import tkinter as tk
import customtkinter as ctk
import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageColor
from tkinter import filedialog, messagebox, colorchooser

from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import (
    SquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
    VerticalBarsDrawer,
    HorizontalBarsDrawer,
)
from qrcode.image.styles.colormasks import QRColorMask


# ---------------------------------------------------------------------------
# Paths / assets
# ---------------------------------------------------------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


FONTS_DIR = "fonts"
TAHOMA = os.path.join(FONTS_DIR, "tahoma.ttf")  # bundled for Thai text rendering


def load_font(size, bold=False):
    """Load a Thai-capable font: bundled Tahoma, else the Windows copy."""
    windir = os.environ.get("WINDIR", r"C:\Windows")
    for path in (resource_path(TAHOMA),
                 os.path.join(windir, "Fonts", "tahoma.ttf")):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Module drawing
# ---------------------------------------------------------------------------
DRAWERS = {
    "square": SquareModuleDrawer(),
    "rounded": RoundedModuleDrawer(radius_ratio=1.0),
    "circle": CircleModuleDrawer(),
    "vertical": VerticalBarsDrawer(),
    "horizontal": HorizontalBarsDrawer(),
}


def finder_boxes(n):
    return [(4, 4, 10, 10), (4, n - 11, 10, n - 5), (n - 11, 4, n - 5, 10)]


class EyeColorMask(QRColorMask):
    """Recolor the three finder-pattern 'eyes' with eye_color, rest fg_color."""
    back_color = (0, 0, 0, 0)
    has_transparency = True
    paint_color = (0, 0, 0, 255)

    def apply_mask(self, image, use_cache=False):
        # Vectorised with numpy: the old per-pixel Python loop took seconds
        # on large QR codes.
        import numpy as np
        arr = np.array(image.convert("RGBA"))
        h, w = arr.shape[:2]
        eye = np.zeros((h, w), dtype=bool)
        bs = self.box_size
        for (x0, y0, x1, y1) in finder_boxes(self.n):
            eye[y0 * bs:(y1 + 1) * bs, x0 * bs:(x1 + 1) * bs] = True
        arr[..., :3] = np.where(eye[..., None],
                                np.array(self.eye_color[:3], dtype=np.uint8),
                                np.array(self.fg_color[:3], dtype=np.uint8))
        image.paste(Image.fromarray(arr, "RGBA"))


# ---------------------------------------------------------------------------
# Design templates  (name -> dict of defaults)
# ---------------------------------------------------------------------------
TEMPLATES = {
    "คลาสสิก (ขาว-ดำ)": dict(fg="#000000", eye="#000000", bg="",
                              shape="square", cta="SCAN ME", cta_color="#000000"),
    "Minimal Blue (โลโก้)": dict(fg="#1f4e99", eye="#1f8a96", bg="",
                              shape="rounded", cta="SCAN ME", cta_color="#1f4e99"),
    "Ocean Teal": dict(fg="#0a4f8c", eye="#1f8a96", bg="",
                       shape="circle", cta="SCAN ME", cta_color="#0a4f8c"),
    "Sunset": dict(fg="#b5341f", eye="#c9701c", bg="",
                   shape="rounded", cta="SCAN ME", cta_color="#b5341f"),
    "Forest": dict(fg="#1b5e20", eye="#4f8a2e", bg="",
                   shape="circle", cta="SCAN ME", cta_color="#1b5e20"),
    "Grape": dict(fg="#4a148c", eye="#a83cc0", bg="",
                  shape="rounded", cta="SCAN ME", cta_color="#4a148c"),
    "Graphite": dict(fg="#212121", eye="#2f8f9d", bg="",
                     shape="square", cta="SCAN ME", cta_color="#212121"),
    "Royal Card": dict(fg="#102a43", eye="#a8741a", bg="#dbe9ff",
                       shape="rounded", cta="SCAN ME", cta_color="#102a43"),
    "Order Here": dict(fg="#b71c1c", eye="#d9600f", bg="",
                       shape="circle", cta="ORDER HERE", cta_color="#b71c1c"),
    "Promo Code": dict(fg="#6a1b9a", eye="#b87a10", bg="",
                       shape="rounded", cta="PROMO CODE", cta_color="#6a1b9a"),
    "Play Audio": dict(fg="#006064", eye="#1f8a96", bg="",
                       shape="circle", cta="PLAY AUDIO", cta_color="#006064"),
}


# Error-correction levels (density / robustness) and module sizes
EC_LEVELS = {
    "L (ทนทาน 7%)": qrcode.constants.ERROR_CORRECT_L,
    "M (ทนทาน 15%)": qrcode.constants.ERROR_CORRECT_M,
    "Q (ทนทาน 25%)": qrcode.constants.ERROR_CORRECT_Q,
    "H (หนาแน่น 30%)": qrcode.constants.ERROR_CORRECT_H,
}
SIZE_MAP = {"เล็ก (8)": 8, "กลาง (10)": 10, "ใหญ่ (12)": 12}


# ---------------------------------------------------------------------------
# Pure logic helpers (testable headlessly)
# ---------------------------------------------------------------------------
def build_payload(kind, fields):
    """Return the QR payload string for a content preset."""
    if kind == "url":
        v = (fields.get("url") or "").strip()
        if v and not v.lower().startswith(("http://", "https://")):
            v = "https://" + v
        return v
    if kind == "text":
        return fields.get("text") or ""
    if kind == "wifi":
        ssid = (fields.get("ssid") or "").strip()
        pw = (fields.get("password") or "").strip()
        sec = fields.get("security") or "WPA"
        hidden = fields.get("hidden")
        if not ssid:
            return ""
        if isinstance(hidden, str):
            hidden = hidden.strip().lower() in ("yes", "true", "1")
        esc = lambda s: "".join("\\" + ch if ch in '\\;,:"' else ch for ch in s)
        if sec == "nopass":
            return f"WIFI:T:nopass;S:{esc(ssid)};{'H:true;' if hidden else ''};"
        return (f"WIFI:T:{sec};S:{esc(ssid)};P:{esc(pw)};"
                f"{'H:true;' if hidden else ''};")
    if kind == "email":
        to = (fields.get("to") or "").strip()
        subject = (fields.get("subject") or "").strip()
        body = (fields.get("body") or "").strip()
        if not to:
            return ""
        from urllib.parse import quote
        q = []
        if subject:
            q.append("subject=" + quote(subject))
        if body:
            q.append("body=" + quote(body))
        return f"mailto:{to}" + ("?" + "&".join(q) if q else "")
    if kind == "sms":
        num = (fields.get("number") or "").strip()
        msg = (fields.get("message") or "").strip()
        if not num:
            return ""
        return f"SMSTO:{num}:{msg}" if msg else f"SMSTO:{num}"
    if kind == "vcard":
        name = (fields.get("name") or "").strip()
        org = (fields.get("org") or "").strip()
        phone = (fields.get("phone") or "").strip()
        email = (fields.get("email") or "").strip()
        url = (fields.get("url") or "").strip()
        if not name:
            return ""
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{name}", f"FN:{name}"]
        if org:
            lines.append(f"ORG:{org}")
        if phone:
            lines.append(f"TEL;TYPE=CELL:{phone}")
        if email:
            lines.append(f"EMAIL:{email}")
        if url:
            lines.append(f"URL:{url}")
        lines.append("END:VCARD")
        return "\n".join(lines)
    return ""


def contrast_ok(fg, bg):
    """Return True if fg has enough contrast over bg for scannability.

    For a transparent background we assume a white surface.
    """
    def lum(hex_or_tuple):
        if isinstance(hex_or_tuple, str):
            c = ImageColor.getrgb(hex_or_tuple)
        else:
            c = hex_or_tuple
        r, g, b = [x / 255.0 for x in c[:3]]
        f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

    fg_l = lum(fg)
    bg_l = lum(bg) if bg else 1.0  # transparent -> white surface
    lighter, darker = max(fg_l, bg_l), min(fg_l, bg_l)
    ratio = (lighter + 0.05) / (darker + 0.05)
    return ratio >= 2.5  # QR tolerance is ~ lower than text; be lenient-ish


def make_rounded_corners(im, rad):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0) + im.size, radius=rad, fill=255)
    result = im.copy()
    result.putalpha(mask)
    return result


def render_qr(data, template_name, fg=None, eye=None, bg=None, shape=None,
              cta_text=None, cta_color=None, box_size=10, border=4,
              logo_path=None, logo_scale=0.25, use_template_shape=True,
              ec="H (หนาแน่น 30%)"):
    """Render a styled QR. Colors/shape/cta fall back to the template defaults."""
    tpl = TEMPLATES[template_name]
    fg = fg or tpl["fg"]
    eye = eye or tpl["eye"]
    bg = bg if bg is not None else tpl["bg"]
    shape = shape or tpl["shape"]
    cta_text = cta_text if cta_text is not None else tpl["cta"]
    cta_color = cta_color or tpl["cta_color"]

    level = EC_LEVELS.get(ec, qrcode.constants.ERROR_CORRECT_H)
    if logo_path and level in (qrcode.constants.ERROR_CORRECT_L,
                               qrcode.constants.ERROR_CORRECT_M):
        level = qrcode.constants.ERROR_CORRECT_Q  # logo hides modules
    qr = qrcode.QRCode(
        version=None,
        error_correction=level,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except ValueError:
        raise RuntimeError("ข้อมูลยาวเกินกว่าที่ QR Code จะรองรับได้ "
                           "ลองลดข้อความ หรือเลือกระดับความหนาแน่น L")
    n = len(qr.get_matrix())

    mask = EyeColorMask()
    mask.fg_color = ImageColor.getrgb(fg)
    mask.eye_color = ImageColor.getrgb(eye)
    mask.n = n
    mask.box_size = box_size

    drawer = DRAWERS.get(shape, SquareModuleDrawer())
    img = qr.make_image(image_factory=StyledPilImage,
                        module_drawer=drawer, color_mask=mask).convert("RGBA")

    # composite onto a colored background if requested
    if bg:
        base = Image.new("RGBA", img.size, ImageColor.getrgb(bg))
        base.alpha_composite(img)
        img = base

    # logo in the center
    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            basewidth = int(img.size[0] * float(logo_scale))
            wpercent = basewidth / float(logo.size[0])
            hsize = int(float(logo.size[1]) * wpercent)
            logo = logo.resize((basewidth, hsize), Image.Resampling.LANCZOS)
            radius = int(basewidth * 0.2)
            logo = make_rounded_corners(logo, radius)
            bg_pad = 10
            bg_radius = int(radius * 1.1)
            logo_bg = Image.new("RGBA", (basewidth + bg_pad, hsize + bg_pad),
                                (255, 255, 255, 255))
            logo_bg = make_rounded_corners(logo_bg, bg_radius)
            bg_pos = ((img.size[0] - logo_bg.size[0]) // 2,
                      (img.size[1] - logo_bg.size[1]) // 2)
            img.paste(logo_bg, bg_pos, mask=logo_bg)
            logo_pos = ((img.size[0] - logo.size[0]) // 2,
                        (img.size[1] - logo.size[1]) // 2)
            img.paste(logo, logo_pos, mask=logo)
        except Exception as e:
            raise RuntimeError(f"ไม่สามารถใส่โลโก้ได้: {e}")

    # CTA caption strip
    if cta_text:
        pad = max(40, int(box_size * 4))
        if bg:
            strip_color = ImageColor.getrgb(bg)
        else:
            px = img.getpixel((0, 0))
            if isinstance(px, int):  # grayscale
                strip_color = (px, px, px, 255)
            elif len(px) == 3:
                strip_color = (px[0], px[1], px[2], 255)
            else:
                strip_color = px if px[3] != 0 else (255, 255, 255, 255)
        new = Image.new("RGBA", (img.size[0], img.size[1] + pad), strip_color)
        new.paste(img, (0, 0))
        d = ImageDraw.Draw(new)
        font = load_font(max(22, int(box_size * 3)))
        tb = d.textbbox((0, 0), cta_text, font=font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
        cx = new.size[0] // 2 - tw // 2
        cy = img.size[1] + pad // 2 - th // 2 - 2
        d.text((cx + 1, cy + 1), cta_text, font=font, fill=(0, 0, 0, 130))
        d.text((cx, cy), cta_text, font=font, fill=ImageColor.getrgb(cta_color))
        img = new

    return img


def qr_matrix_to_svg(matrix, box_size, fg, bg, has_bg):
    n = len(matrix)
    size = n * box_size
    fg_hex = _hex(fg)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
             f'height="{size}" viewBox="0 0 {size} {size}" '
             f'shape-rendering="crispEdges">']
    if has_bg:
        parts.append(f'<rect width="100%" height="100%" fill="{_hex(bg)}"/>')
    for r in range(n):
        for c in range(n):
            if matrix[r][c]:
                parts.append(f'<rect x="{c*box_size}" y="{r*box_size}" '
                             f'width="{box_size}" height="{box_size}" '
                             f'fill="{fg_hex}"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def _hex(c):
    if isinstance(c, str):
        c = ImageColor.getrgb(c)
    return "#{:02x}{:02x}{:02x}".format(c[0], c[1], c[2])


def decode_qr_from_image(pil_img):
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise RuntimeError(f"ไม่พบไลบรารีสแกน (opencv): {e}")
    # Transparent PNGs (YQR's own default output) turn black-on-black when
    # converted straight to RGB, so flatten onto white first.
    rgba = pil_img.convert("RGBA")
    flat = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    flat.alpha_composite(rgba)
    gray = np.array(flat.convert("L"))
    detector = cv2.QRCodeDetector()
    candidates = [gray, 255 - gray]  # normal + inverted (light-on-dark)
    if max(gray.shape) < 400:  # tiny screenshots decode better upscaled
        big = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        candidates += [big, 255 - big]
    for g in candidates:
        try:
            data, _bbox, _ = detector.detectAndDecode(g)
        except cv2.error:
            data = ""
        if data:
            return data.strip()
    return ""


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
# Calm, low-contrast palette (light, dark). Soft steel-blue accent that
# echoes the logo without being loud.
C = {
    "bg":       ("#F2F4F7", "#1B1F24"),
    "card":     ("#FFFFFF", "#242A31"),
    "border":   ("#E2E6EB", "#323A43"),
    "field":    ("#F7F9FB", "#1F242A"),
    "text":     ("#2B3440", "#DCE1E6"),
    "muted":    ("#7A8591", "#8B96A1"),
    "accent":   ("#5B8DB8", "#6F9CC4"),
    "accent_h": ("#4A7AA3", "#5D8AB2"),
    "soft":     ("#E8EEF5", "#2C343D"),
    "soft_h":   ("#DCE5EF", "#353F49"),
    "ok":       ("#4F9373", "#7BB89A"),
    "warn":     ("#B57F38", "#D7A35E"),
    "danger":   ("#BD6262", "#D98A8A"),
}
R = 8  # corner radius: slightly rounded

SHAPE_LABELS = {"square": "สี่เหลี่ยม", "rounded": "มุมมน", "circle": "วงกลม",
                "vertical": "แท่งแนวตั้ง", "horizontal": "แท่งแนวนอน"}

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


def F(size=13, bold=False):
    return ctk.CTkFont(family="Tahoma", size=size,
                       weight="bold" if bold else "normal")


class App(ctk.CTk):
    VERSION = "2.1.0"

    def __init__(self):
        super().__init__(fg_color=C["bg"])
        self.title(f"YQR - QR Code Generator v{self.VERSION}")
        self.geometry("940x680")
        self.minsize(860, 600)
        try:
            self.iconbitmap(resource_path("logo101.ico"))
        except Exception:
            pass

        # ----- state -----
        self.qr_image = None
        self.scan_img = None
        self.logo_path = None
        self.last_data = ""
        self.template_name = "Minimal Blue (โลโก้)"
        tpl = TEMPLATES[self.template_name]
        self.fg, self.eye, self.bg = tpl["fg"], tpl["eye"], tpl["bg"]
        self.shape, self.cta_text = tpl["shape"], tpl["cta"]
        self.cta_color = tpl["cta_color"]
        self.logo_scale = 0.25
        self.content_kind = "url"
        self.fields = {}
        self.field_vars = {}
        self.ec_key = "H (หนาแน่น 30%)"
        self.size_key = "กลาง (10)"

        self._build_ui()

    # ============================ widget helpers ============================
    def card(self, parent, **kw):
        return ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=R + 2,
                            border_width=1, border_color=C["border"], **kw)

    def title_lbl(self, parent, text):
        return ctk.CTkLabel(parent, text=text, font=F(13, True),
                            text_color=C["text"], anchor="w")

    def lbl(self, parent, text, muted=False):
        return ctk.CTkLabel(parent, text=text, font=F(12), anchor="w",
                            text_color=C["muted"] if muted else C["text"])

    def btn(self, parent, text, command, primary=False, **kw):
        kw.setdefault("height", 32)
        if primary:
            colors = dict(fg_color=C["accent"], hover_color=C["accent_h"],
                          text_color="#FFFFFF")
        else:
            colors = dict(fg_color=C["soft"], hover_color=C["soft_h"],
                          text_color=C["text"])
        return ctk.CTkButton(parent, text=text, command=command,
                             corner_radius=R, font=F(12, primary),
                             **colors, **kw)

    def menu(self, parent, values, command=None, width=180, **kw):
        return ctk.CTkOptionMenu(
            parent, values=values, command=command, width=width, height=30,
            corner_radius=R, font=F(12), dropdown_font=F(12),
            fg_color=C["field"], button_color=C["soft"],
            button_hover_color=C["soft_h"], text_color=C["text"],
            dropdown_fg_color=C["card"], dropdown_text_color=C["text"],
            dropdown_hover_color=C["soft"], **kw)

    def entry(self, parent, width=260, **kw):
        return ctk.CTkEntry(parent, width=width, height=30, corner_radius=R,
                            font=F(12), fg_color=C["field"],
                            border_color=C["border"], border_width=1,
                            text_color=C["text"], **kw)

    def swatch(self, parent, color, command, width=34):
        return ctk.CTkButton(parent, text="", width=width, height=26,
                             corner_radius=R - 2, fg_color=color,
                             hover_color=color, border_width=1,
                             border_color=C["border"], command=command)

    def segmented(self, parent, values, command, **kw):
        return ctk.CTkSegmentedButton(
            parent, values=values, command=command, corner_radius=R,
            font=F(11), height=30, fg_color=C["soft"],
            selected_color=C["accent"], selected_hover_color=C["accent_h"],
            unselected_color=C["soft"], unselected_hover_color=C["soft_h"],
            text_color=(("#2B3440", "#DCE1E6")), **kw)

    # ============================ UI ============================
    def _build_ui(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(14, 6))
        try:
            logo = Image.open(resource_path("logo101.png"))
            self._head_logo = ctk.CTkImage(logo, logo, size=(30, 30))
            ctk.CTkLabel(head, text="", image=self._head_logo).pack(
                side="left", padx=(0, 10))
        except Exception:
            pass
        ctk.CTkLabel(head, text="YQR", font=F(20, True),
                     text_color=C["text"]).pack(side="left")
        ctk.CTkLabel(head, text=f"  QR Code Generator  ·  v{self.VERSION}",
                     font=F(12), text_color=C["muted"]).pack(side="left",
                                                             pady=(4, 0))
        self.theme_seg = self.segmented(
            head, ["System", "Light", "Dark"],
            lambda v: ctk.set_appearance_mode(v))
        self.theme_seg.set("System")
        self.theme_seg.pack(side="right")

        self.tab = ctk.CTkTabview(
            self, corner_radius=R + 4, fg_color=C["bg"],
            segmented_button_fg_color=C["soft"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent_h"],
            segmented_button_unselected_color=C["soft"],
            segmented_button_unselected_hover_color=C["soft_h"],
            text_color=C["text"], anchor="w")
        self.tab.pack(padx=14, pady=(0, 14), fill="both", expand=True)
        self.tab.add("สร้าง QR")
        self.tab.add("สแกน QR")
        self.tab._segmented_button.configure(font=F(12, True))
        self._build_create(self.tab.tab("สร้าง QR"))
        self._build_scan(self.tab.tab("สแกน QR"))

    # -------- create tab --------
    def _build_create(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=0)
        tab.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(
            tab, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=C["soft"],
            scrollbar_button_hover_color=C["soft_h"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        right = ctk.CTkFrame(tab, fg_color="transparent")
        right.grid(row=0, column=1, sticky="ns")

        # 1) content
        c1 = self.card(left)
        c1.pack(fill="x", pady=(0, 10))
        self.title_lbl(c1, "1  เนื้อหา").pack(anchor="w", padx=14, pady=(12, 6))
        self.kind_labels = {"url": "URL / ลิงก์", "wifi": "Wi-Fi",
                            "vcard": "นามบัตร", "email": "อีเมล",
                            "sms": "SMS", "text": "ข้อความ"}
        self.kind_seg = self.segmented(c1, list(self.kind_labels.values()),
                                       self._on_kind)
        self.kind_seg.set(self.kind_labels[self.content_kind])
        self.kind_seg.pack(anchor="w", padx=14, pady=(0, 8))
        self.field_frame = ctk.CTkFrame(c1, fg_color="transparent")
        self.field_frame.pack(fill="x", padx=8, pady=(0, 10))
        self._build_fields()

        # 2) design
        c2 = self.card(left)
        c2.pack(fill="x", pady=(0, 10))
        self.title_lbl(c2, "2  ดีไซน์").pack(anchor="w", padx=14, pady=(12, 6))
        g = ctk.CTkFrame(c2, fg_color="transparent")
        g.pack(fill="x", padx=8, pady=(0, 12))
        g.grid_columnconfigure(1, weight=1)

        def row(r, text):
            self.lbl(g, text, muted=True).grid(row=r, column=0, sticky="w",
                                               padx=6, pady=5)

        row(0, "แม่แบบ")
        self.tpl_menu = self.menu(g, list(TEMPLATES.keys()),
                                  command=self._on_template, width=240)
        self.tpl_menu.set(self.template_name)
        self.tpl_menu.grid(row=0, column=1, sticky="w", padx=6, pady=5)

        row(1, "สี")
        sw = ctk.CTkFrame(g, fg_color="transparent")
        sw.grid(row=1, column=1, sticky="w", padx=6, pady=5)
        self.fg_btn = self.swatch(sw, self.fg, lambda: self._pick("fg"))
        self.eye_btn = self.swatch(sw, self.eye, lambda: self._pick("eye"))
        self.cta_btn = self.swatch(sw, self.cta_color,
                                   lambda: self._pick("cta_color"))
        self.bg_btn = self.swatch(sw, self.bg or "#FFFFFF",
                                  lambda: self._pick("bg"))
        for b, t in ((self.fg_btn, "โมดูล"), (self.eye_btn, "ตา"),
                     (self.cta_btn, "ข้อความ"), (self.bg_btn, "พื้นหลัง")):
            b.pack(side="left")
            self.lbl(sw, t, muted=True).pack(side="left", padx=(5, 12))
        self.btn(sw, "โปร่งใส", self._clear_bg, width=60,
                 height=26).pack(side="left")

        row(2, "รูปทรง")
        self.shape_menu = self.menu(g, list(SHAPE_LABELS.values()),
                                    command=self._on_shape, width=160)
        self.shape_menu.set(SHAPE_LABELS[self.shape])
        self.shape_menu.grid(row=2, column=1, sticky="w", padx=6, pady=5)

        row(3, "ข้อความใต้ QR")
        self.cta_entry = self.entry(g, width=240,
                                    placeholder_text="เว้นว่างได้")
        self.cta_entry.insert(0, self.cta_text)
        self.cta_entry.grid(row=3, column=1, sticky="w", padx=6, pady=5)

        row(4, "ความทนทาน")
        self.ec_menu = self.menu(g, list(EC_LEVELS.keys()),
                                 command=lambda v: setattr(self, "ec_key", v),
                                 width=160)
        self.ec_menu.set(self.ec_key)
        self.ec_menu.grid(row=4, column=1, sticky="w", padx=6, pady=5)

        row(5, "ขนาดโมดูล")
        self.size_menu = self.menu(
            g, list(SIZE_MAP.keys()),
            command=lambda v: setattr(self, "size_key", v), width=160)
        self.size_menu.set(self.size_key)
        self.size_menu.grid(row=5, column=1, sticky="w", padx=6, pady=5)

        # 3) logo
        c3 = self.card(left)
        c3.pack(fill="x", pady=(0, 4))
        self.title_lbl(c3, "3  โลโก้ (ไม่บังคับ)").pack(anchor="w", padx=14,
                                                      pady=(12, 6))
        lr = ctk.CTkFrame(c3, fg_color="transparent")
        lr.pack(fill="x", padx=14, pady=(0, 6))
        self.btn(lr, "เลือกรูป", self.select_logo, width=90).pack(side="left")
        self.btn(lr, "ลบ", self.clear_logo, width=50).pack(side="left",
                                                          padx=(6, 10))
        self.logo_label = self.lbl(lr, "ไม่มีโลโก้", muted=True)
        self.logo_label.pack(side="left")
        sr = ctk.CTkFrame(c3, fg_color="transparent")
        sr.pack(fill="x", padx=14, pady=(0, 12))
        self.lbl(sr, "ขนาด", muted=True).pack(side="left", padx=(0, 10))
        self.scale = ctk.CTkSlider(
            sr, from_=0.10, to=0.40, number_of_steps=30, width=200,
            command=self._on_scale, button_color=C["accent"],
            button_hover_color=C["accent_h"], progress_color=C["accent"],
            fg_color=C["soft"])
        self.scale.set(self.logo_scale)
        self.scale.pack(side="left")
        self.scale_lbl = self.lbl(sr, f"{int(self.logo_scale*100)}%")
        self.scale_lbl.pack(side="left", padx=(8, 0))

        # right: preview card (always visible)
        pc = self.card(right)
        pc.pack(fill="both", expand=True)
        self.title_lbl(pc, "ตัวอย่าง").pack(anchor="w", padx=14, pady=(12, 6))
        self.qr_display = ctk.CTkLabel(
            pc, text="กด “สร้าง QR Code”\nเพื่อดูตัวอย่าง", width=300,
            height=330, fg_color=C["field"], corner_radius=R,
            text_color=C["muted"], font=F(12))
        self.qr_display.pack(padx=14)
        self.error_label = ctk.CTkLabel(pc, text="", font=F(11),
                                        text_color=C["warn"], wraplength=300,
                                        justify="left")
        self.error_label.pack(padx=14, pady=(6, 0), anchor="w")
        self.btn(pc, "สร้าง QR Code", self.generate_qr, primary=True,
                 height=40, width=300).pack(padx=14, pady=(8, 8))
        act = ctk.CTkFrame(pc, fg_color="transparent")
        act.pack(padx=14, pady=(0, 14))
        self.save_btn = self.btn(act, "บันทึก", self.save_qr, width=146,
                                 state="disabled")
        self.save_btn.pack(side="left", padx=(0, 8))
        self.copy_btn = self.btn(act, "คัดลอกรูป", self.copy_qr, width=146,
                                 state="disabled")
        self.copy_btn.pack(side="left")
        self.bind("<Return>", lambda e: self.generate_qr())

    # -------- scan tab --------
    def _build_scan(self, tab):
        tab.grid_columnconfigure(0, weight=0)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        lc = self.card(tab)
        lc.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.title_lbl(lc, "รูปภาพ").pack(anchor="w", padx=14, pady=(12, 6))
        self.scan_display = ctk.CTkLabel(
            lc, text="ยังไม่มีรูป", width=280, height=280,
            fg_color=C["field"], corner_radius=R, text_color=C["muted"],
            font=F(12))
        self.scan_display.pack(padx=14)
        self.btn(lc, "เลือกรูปภาพ QR", self.scan_from_file, primary=True,
                 width=280, height=36).pack(padx=14, pady=(12, 6))
        self.btn(lc, "วางจากคลิปบอร์ด", self.scan_from_clipboard,
                 width=280, height=36).pack(padx=14, pady=(0, 14))

        rc = self.card(tab)
        rc.grid(row=0, column=1, sticky="nsew")
        self.title_lbl(rc, "ผลลัพธ์").pack(anchor="w", padx=14, pady=(12, 2))
        self.scan_status = self.lbl(rc, "เลือกรูป หรือวางรูปจากคลิปบอร์ด",
                                    muted=True)
        self.scan_status.pack(anchor="w", padx=14, pady=(0, 6))
        self.result_box = ctk.CTkTextbox(
            rc, font=F(13), wrap="word", corner_radius=R, fg_color=C["field"],
            border_width=1, border_color=C["border"], text_color=C["text"])
        self.result_box.pack(fill="both", expand=True, padx=14)
        self._set_result("")
        act = ctk.CTkFrame(rc, fg_color="transparent")
        act.pack(anchor="w", padx=14, pady=12)
        self.btn(act, "คัดลอกผลลัพธ์", self.copy_result, width=150).pack(
            side="left", padx=(0, 8))
        self.open_btn = self.btn(act, "เปิดในเบราว์เซอร์", self.open_result,
                                 width=150, state="disabled")
        self.open_btn.pack(side="left")

    def _set_result(self, text):
        self.result_box.configure(state="normal")
        self.result_box.delete("0.0", "end")
        self.result_box.insert("0.0", text)
        self.result_box.configure(state="disabled")

    # ============================ fields ============================
    def _build_fields(self):
        # keep what the user typed when switching content type
        for k, var in self.field_vars.items():
            self.fields[k] = var.get()
        for w in list(self.field_frame.winfo_children()):
            w.destroy()
        rows = {
            "url": [("url", "ลิงก์", "https://example.com")],
            "text": [("text", "ข้อความ", "พิมพ์ข้อความที่นี่...")],
            "wifi": [("ssid", "ชื่อ Wi-Fi", "MyWiFi"),
                     ("password", "รหัสผ่าน", "password123"),
                     ("security", "ความปลอดภัย", "WPA"),
                     ("hidden", "ซ่อนเครือข่าย", "no")],
            "email": [("to", "ถึง", "someone@example.com"),
                      ("subject", "หัวข้อ", "สวัสดี"),
                      ("body", "ข้อความ", "")],
            "sms": [("number", "เบอร์โทร", "0812345678"),
                    ("message", "ข้อความ", "")],
            "vcard": [("name", "ชื่อ-นามสกุล", "สมชาย ใจดี"),
                      ("org", "องค์กร", "บริษัท ABC"),
                      ("phone", "โทรศัพท์", "0812345678"),
                      ("email", "อีเมล", "name@example.com"),
                      ("url", "เว็บไซต์", "https://example.com")],
        }[self.content_kind]
        self.field_vars = {}
        self.field_frame.grid_columnconfigure(1, weight=1)
        for i, (key, label, ph) in enumerate(rows):
            self.lbl(self.field_frame, label, muted=True).grid(
                row=i, column=0, sticky="w", padx=6, pady=4)
            if key in ("hidden", "security"):
                opts = (["WPA", "WEP", "nopass"] if key == "security"
                        else ["no", "yes"])
                val = self.fields.get(key, ph)
                var = tk.StringVar(value=val if val in opts else ph)
                self.menu(self.field_frame, opts, width=140,
                          variable=var).grid(row=i, column=1, padx=6, pady=4,
                                             sticky="w")
            else:
                var = tk.StringVar(value=self.fields.get(key, ""))
                self.entry(self.field_frame, width=340, textvariable=var,
                           placeholder_text=ph).grid(
                    row=i, column=1, padx=6, pady=4, sticky="ew")
            self.field_vars[key] = var

    def _on_kind(self, label):
        self.content_kind = next(k for k, v in self.kind_labels.items()
                                 if v == label)
        self._build_fields()

    def _current_fields(self):
        return {k: var.get() for k, var in self.field_vars.items()}

    # ============================ template / pick ============================
    def _on_template(self, name):
        self.template_name = name
        self.tpl_menu.set(name)
        tpl = TEMPLATES[name]
        self.fg, self.eye, self.bg = tpl["fg"], tpl["eye"], tpl["bg"]
        self.shape, self.cta_text = tpl["shape"], tpl["cta"]
        self.cta_color = tpl["cta_color"]
        self.fg_btn.configure(fg_color=self.fg, hover_color=self.fg)
        self.eye_btn.configure(fg_color=self.eye, hover_color=self.eye)
        self.cta_btn.configure(fg_color=self.cta_color,
                               hover_color=self.cta_color)
        self._refresh_bg_btn()
        self.shape_menu.set(SHAPE_LABELS[self.shape])
        self.cta_entry.delete(0, "end")
        self.cta_entry.insert(0, self.cta_text)

    def _on_shape(self, label):
        self.shape = next(k for k, v in SHAPE_LABELS.items() if v == label)

    def _refresh_bg_btn(self):
        c = self.bg or "#FFFFFF"
        self.bg_btn.configure(fg_color=c, hover_color=c)

    def _clear_bg(self):
        self.bg = ""
        self._refresh_bg_btn()

    def _pick(self, attr):
        init = getattr(self, attr) or "#ffffff"
        color = colorchooser.askcolor(title="เลือกสี", initialcolor=init)
        if not (color and color[1]):
            return
        value = color[1]
        setattr(self, attr, value)
        if attr == "bg":
            self._refresh_bg_btn()
        else:
            b = {"fg": self.fg_btn, "eye": self.eye_btn,
                 "cta_color": self.cta_btn}[attr]
            b.configure(fg_color=value, hover_color=value)

    def _on_scale(self, value):
        self.logo_scale = float(value)
        self.scale_lbl.configure(text=f"{int(self.logo_scale*100)}%")

    def select_logo(self):
        fp = filedialog.askopenfilename(
            title="เลือกไฟล์โลโก้",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("All files", "*.*")])
        if fp:
            self.logo_path = fp
            name = os.path.basename(fp)
            shown = name if len(name) <= 22 else name[:19] + "..."
            self.logo_label.configure(text=shown, text_color=C["text"])

    def clear_logo(self):
        self.logo_path = None
        self.logo_label.configure(text="ไม่มีโลโก้", text_color=C["muted"])

    # ============================ generate ============================
    def generate_qr(self):
        self.error_label.configure(text="")
        data = build_payload(self.content_kind, self._current_fields())
        if not data.strip():
            self.error_label.configure(
                text="กรุณากรอกข้อมูลก่อนสร้าง QR Code", text_color=C["danger"])
            return
        self.cta_text = self.cta_entry.get()

        warnings = []
        if not (contrast_ok(self.fg, self.bg) and
                contrast_ok(self.eye, self.bg)):
            warnings.append("สีโมดูล/สีตา กับพื้นหลังตัดกันน้อย อาจสแกนไม่ได้")
        if self.logo_path and EC_LEVELS[self.ec_key] in (
                qrcode.constants.ERROR_CORRECT_L,
                qrcode.constants.ERROR_CORRECT_M):
            warnings.append("มีโลโก้ ระบบปรับความทนทานเป็น Q ให้อัตโนมัติ")

        try:
            img = render_qr(
                data, self.template_name, fg=self.fg, eye=self.eye,
                bg=self.bg, shape=self.shape, cta_text=self.cta_text,
                cta_color=self.cta_color, logo_path=self.logo_path,
                logo_scale=self.logo_scale, ec=self.ec_key,
                box_size=SIZE_MAP[self.size_key])
        except Exception as e:
            self.error_label.configure(text=str(e), text_color=C["danger"])
            return

        self.last_data = data
        self.qr_image = img
        # self-check: make sure the result actually scans
        try:
            if decode_qr_from_image(img) != data.strip():
                warnings.append("ตรวจแล้วสแกนไม่ผ่าน ลองลดขนาดโลโก้ "
                                "หรือเพิ่มความต่างของสี")
        except Exception:
            pass

        disp = self._flatten(img)  # show on white, as it will be printed
        disp.thumbnail((272, 300), Image.Resampling.LANCZOS)
        self._preview = ctk.CTkImage(disp, disp, size=disp.size)
        self.qr_display.configure(image=self._preview, text="")
        self.save_btn.configure(state="normal")
        self.copy_btn.configure(state="normal")
        if warnings:
            self.error_label.configure(text="⚠ " + "\n⚠ ".join(warnings),
                                       text_color=C["warn"])
        else:
            self.error_label.configure(text="✓ สร้างแล้ว และทดสอบสแกนผ่าน",
                                       text_color=C["ok"])

    # ============================ save / copy ============================
    def save_qr(self):
        if self.qr_image is None:
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"),
                       ("SVG", "*.svg"), ("PDF", "*.pdf"),
                       ("All files", "*.*")],
            title="บันทึก QR Code", initialfile="qrcode")
        if not fp:
            return
        ext = os.path.splitext(fp)[1].lower()
        try:
            if ext in (".jpg", ".jpeg"):
                self._flatten(self.qr_image).save(fp, "JPEG", quality=95)
            elif ext == ".svg":
                # SVG is a plain vector version (single colour, square modules)
                qr = qrcode.QRCode(
                    version=None, box_size=10, border=4,
                    error_correction=EC_LEVELS.get(
                        self.ec_key, qrcode.constants.ERROR_CORRECT_H))
                qr.add_data(self.last_data)
                qr.make(fit=True)
                svg = qr_matrix_to_svg(qr.get_matrix(), 10, self.fg,
                                       self.bg, bool(self.bg))
                with open(fp, "w", encoding="utf-8") as fh:
                    fh.write(svg)
            elif ext == ".pdf":
                self._flatten(self.qr_image).save(fp, "PDF", resolution=100.0)
            else:
                self.qr_image.save(fp, "PNG")
            messagebox.showinfo("สำเร็จ", "บันทึก QR Code เรียบร้อยแล้ว")
        except Exception as e:
            messagebox.showerror("Error", f"ไม่สามารถบันทึกไฟล์ได้:\n{e}")

    @staticmethod
    def _flatten(img):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        return bg.convert("RGB")

    def copy_qr(self):
        if self.qr_image is None:
            return
        try:
            self._copy_image(self._flatten(self.qr_image))
            self.error_label.configure(text="✓ คัดลอกรูปไปคลิปบอร์ดแล้ว",
                                       text_color=C["ok"])
        except Exception:
            messagebox.showwarning("แจ้งเตือน",
                                   "ไม่สามารถคัดลอกรูปไปคลิปบอร์ดได้\n"
                                   "ลองใช้ปุ่ม 'บันทึก' แทน")

    # ============================ scan ============================
    def scan_from_file(self):
        fp = filedialog.askopenfilename(
            title="เลือกรูปภาพ QR Code",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("All files", "*.*")])
        if not fp:
            return
        try:
            img = Image.open(fp)
            img.load()
        except Exception as e:
            messagebox.showerror("Error", f"เปิดรูปไม่ได้: {e}")
            return
        self._decode_and_show(img, os.path.basename(fp))

    def scan_from_clipboard(self):
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
        except Exception:
            img = None
        if isinstance(img, list):  # file(s) copied in Explorer
            try:
                img = Image.open(img[0])
                img.load()
            except Exception:
                img = None
        if not isinstance(img, Image.Image):
            self.scan_status.configure(text="ไม่พบรูปภาพในคลิปบอร์ด",
                                       text_color=C["warn"])
            return
        self._decode_and_show(img, "คลิปบอร์ด")

    def _decode_and_show(self, img, source):
        self.scan_img = img
        flat = Image.new("RGBA", img.size, (255, 255, 255, 255))
        flat.alpha_composite(img.convert("RGBA"))
        flat.thumbnail((280, 280), Image.Resampling.LANCZOS)
        self._scan_preview = ctk.CTkImage(flat, flat, size=flat.size)
        self.scan_display.configure(image=self._scan_preview, text="")
        try:
            data = decode_qr_from_image(img)
        except Exception as e:
            self.scan_status.configure(text=f"เกิดข้อผิดพลาด: {e}",
                                       text_color=C["danger"])
            return
        if data:
            self._set_result(data)
            self.scan_status.configure(text=f"✓ ถอดรหัสสำเร็จ ({source})",
                                       text_color=C["ok"])
            is_url = data.lower().startswith(("http://", "https://"))
            self.open_btn.configure(state="normal" if is_url else "disabled")
        else:
            self._set_result("")
            self.scan_status.configure(text=f"ไม่พบ QR Code ({source})",
                                       text_color=C["warn"])
            self.open_btn.configure(state="disabled")

    def copy_result(self):
        text = self.result_box.get("0.0", "end").strip()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.scan_status.configure(text="✓ คัดลอกผลลัพธ์แล้ว",
                                   text_color=C["ok"])

    def open_result(self):
        text = self.result_box.get("0.0", "end").strip()
        if text.lower().startswith(("http://", "https://")):
            webbrowser.open(text)

    # ============================ clipboard (Windows DIB) ============
    @staticmethod
    def _copy_image(rgb_img):
        import ctypes
        from ctypes import wintypes
        bmp = io.BytesIO()
        rgb_img.save(bmp, "BMP")
        data = bmp.getvalue()[14:]
        CF_DIB, GMEM_MOVEABLE = 8, 0x0002
        k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
        # 64-bit safe signatures (the default int return truncates pointers)
        k32.GlobalAlloc.restype = wintypes.HGLOBAL
        k32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        u32.SetClipboardData.restype = wintypes.HANDLE
        u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        if not u32.OpenClipboard(0):
            raise RuntimeError("clipboard busy")
        try:
            u32.EmptyClipboard()
            h = k32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            p = k32.GlobalLock(h)
            ctypes.memmove(p, data, len(data))
            k32.GlobalUnlock(h)
            if not u32.SetClipboardData(CF_DIB, h):
                raise RuntimeError("SetClipboardData failed")
        finally:
            u32.CloseClipboard()


if __name__ == "__main__":
    app = App()
    app.mainloop()
