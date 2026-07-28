from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
import traceback
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFont,
    ImageOps,
    ImageTk,
)

try:
    import rawpy
except Exception:
    rawpy = None


APP_NAME = "ZCS Polaroid Maker"
APP_VERSION = "2.6"
PROJECT_EXTENSION = ".zcsp"

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".dng"
}

FRAME_PRESETS: dict[str, dict[str, Any]] = {
    "クラシックホワイト": {
        "paper": (247, 245, 239), "text": (45, 45, 45),
        "texture": 0.035, "border": (214, 211, 204), "rounded": 0.0,
    },
    "純白": {
        "paper": (255, 255, 255), "text": (35, 35, 35),
        "texture": 0.0, "border": (220, 220, 220), "rounded": 0.0,
    },
    "クリーム": {
        "paper": (240, 229, 202), "text": (66, 53, 39),
        "texture": 0.045, "border": (204, 188, 154), "rounded": 0.0,
    },
    "厚紙": {
        "paper": (230, 224, 210), "text": (55, 50, 44),
        "texture": 0.075, "border": (185, 176, 158), "rounded": 0.0,
    },
    "古紙": {
        "paper": (216, 199, 163), "text": (73, 54, 36),
        "texture": 0.11, "border": (165, 142, 105), "rounded": 0.0,
    },
    "ブラック": {
        "paper": (28, 28, 30), "text": (235, 235, 235),
        "texture": 0.02, "border": (80, 80, 84), "rounded": 0.0,
    },
    "青みフィルム": {
        "paper": (218, 230, 232), "text": (37, 54, 59),
        "texture": 0.04, "border": (166, 190, 195), "rounded": 0.0,
    },
    "ノート風": {
        "paper": (248, 246, 231), "text": (49, 58, 75),
        "texture": 0.025, "border": (194, 199, 203), "rounded": 0.0,
        "notebook": True,
    },
    "角丸ホワイト": {
        "paper": (250, 250, 248), "text": (42, 42, 42),
        "texture": 0.02, "border": (208, 208, 204), "rounded": 0.035,
    },
}

FILTER_PRESETS: dict[str, dict[str, Any]] = {
    "なし": {
        "brightness": 1.0, "contrast": 1.0, "saturation": 1.0,
        "warmth": 0, "grain": 0, "vignette": 0, "vignette_extent": 45, "vignette_softness": 65, "fade": 0,
        "monochrome": False,
    },
    "ONE35風": {
        "brightness": 1.01, "contrast": 0.96, "saturation": 0.91,
        "warmth": 7, "grain": 18, "vignette": 12, "vignette_extent": 48, "vignette_softness": 72, "fade": 7,
        "monochrome": False,
    },
    "使い捨てカメラ風": {
        "brightness": 1.05, "contrast": 1.08, "saturation": 1.04,
        "warmth": 10, "grain": 30, "vignette": 22, "vignette_extent": 62, "vignette_softness": 48, "fade": 4,
        "monochrome": False,
    },
    "暖色フィルム": {
        "brightness": 1.02, "contrast": 0.98, "saturation": 0.94,
        "warmth": 18, "grain": 12, "vignette": 8, "vignette_extent": 42, "vignette_softness": 76, "fade": 5,
        "monochrome": False,
    },
    "白黒フィルム": {
        "brightness": 1.0, "contrast": 1.08, "saturation": 0.0,
        "warmth": 0, "grain": 22, "vignette": 15, "vignette_extent": 55, "vignette_softness": 60, "fade": 2,
        "monochrome": True,
    },
    "色あせ": {
        "brightness": 1.05, "contrast": 0.84, "saturation": 0.76,
        "warmth": 5, "grain": 10, "vignette": 6, "vignette_extent": 38, "vignette_softness": 82, "fade": 18,
        "monochrome": False,
    },
}

OUTPUT_WIDTHS = {
    "元画像に合わせる": None,
    "SNS向け 1080px": 1080,
    "高画質 2048px": 2048,
    "印刷向け 3000px": 3000,
}

PAPER_PRESETS: dict[str, Optional[tuple[float, float]]] = {
    "写真のみ（用紙なし）": None,
    "A4 縦（210×297mm）": (210.0, 297.0),
    "A4 横（297×210mm）": (297.0, 210.0),
    "A5 縦（148×210mm）": (148.0, 210.0),
    "A5 横（210×148mm）": (210.0, 148.0),
    "はがき 縦（100×148mm）": (100.0, 148.0),
    "はがき 横（148×100mm）": (148.0, 100.0),
    "L判 縦（89×127mm）": (89.0, 127.0),
    "L判 横（127×89mm）": (127.0, 89.0),
    "2L判 縦（127×178mm）": (127.0, 178.0),
    "2L判 横（178×127mm）": (178.0, 127.0),
}

DPI_PRESETS = {
    "150 dpi（確認用）": 150,
    "300 dpi（印刷推奨）": 300,
    "600 dpi（高精細）": 600,
}

DATE_INSET_PRESETS = {
    "標準 10mm": 10.0,
    "安全 12mm（推奨）": 12.0,
    "広め 15mm": 15.0,
}

# 複数画像を用紙端へ並べた場合の、フチなし印刷拡大・搬送誤差対策。
# 値は（上下の保護余白mm, 左右の保護余白mm）。
MULTI_IMAGE_GUARD_PRESETS = {
    "なし（用紙端まで使用）": (0.0, 0.0),
    "控えめ 上下2mm・左右1mm": (2.0, 1.0),
    "標準 上下4mm・左右2mm（推奨）": (4.0, 2.0),
    "安全 上下6mm・左右3mm": (6.0, 3.0),
    "広め 上下8mm・左右4mm": (8.0, 4.0),
}

CAPTION_LINE_PRESETS = {
    "1行": 1, "2行（標準）": 2, "3行": 3, "4行": 4,
    "5行": 5, "6行": 6, "7行": 7, "8行": 8,
}

LAYOUT_CAPACITY = {
    "1枚": 1,
    "2枚（上下）": 2,
    "2枚（左右）": 2,
    "4枚": 4,
    "大1＋小2": 3,
}

CROP_MODES = [
    "縦横比で自動最適化（見切れ防止）",
    "フレームに合わせてトリミング",
    "写真全体を収める",
    "手動調整",
]


@dataclass
class PrinterProfile:
    name: str = "標準プリンター"
    top_mm: float = 0.0
    right_mm: float = 0.0
    bottom_mm: float = 0.0
    left_mm: float = 0.0


@dataclass
class PhotoState:
    path: str
    caption: str = ""
    caption_lines: int = 2
    add_date: bool = True
    frame_name: str = "クラシックホワイト"
    crop_mode: str = "縦横比で自動最適化（見切れ防止）"
    filter_name: str = "なし"
    paper_texture: bool = True
    rotation: int = 0
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    warmth: int = 0
    grain: int = 0
    vignette: int = 0
    vignette_extent: int = 45
    vignette_softness: int = 65
    fade: int = 0
    monochrome: bool = False

    @property
    def file_path(self) -> Path:
        return Path(self.path)


@dataclass
class GlobalOptions:
    layout_name: str = "1枚"
    paper_name: str = "はがき 縦（100×148mm）"
    print_dpi: int = 300
    date_inset_mm: float = 12.0
    output_width: Optional[int] = 2048
    save_format: str = "JPEG"
    jpeg_quality: int = 94
    page_background: tuple[int, int, int] = (255, 255, 255)
    apply_printer_profile: bool = True
    multi_vertical_guard_mm: float = 4.0
    multi_horizontal_guard_mm: float = 2.0


@dataclass
class CardMeta:
    index: int
    card_rect: tuple[int, int, int, int]
    photo_rect: tuple[int, int, int, int]
    caption_rect: tuple[int, int, int, int]
    date_rect: tuple[int, int, int, int]


@dataclass
class PageRenderResult:
    image: Image.Image
    cards: list[CardMeta] = field(default_factory=list)
    safety_rect: Optional[tuple[int, int, int, int]] = None


@dataclass
class ConversionTask:
    """1枚の出力ページに必要な画像集合とレイアウト設定。"""

    start_index: int = 0
    explicit_indices: Optional[list[int]] = None
    layout_name: Optional[str] = None
    gutter_override: Optional[int] = None
    page_background: Optional[tuple[int, int, int]] = None
    selected_export: bool = False


def app_data_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_FILE = app_data_dir() / "settings.json"
ERROR_LOG = app_data_dir() / "zcs_polaroid_maker_error.log"


def mm_to_pixels(mm: float, dpi: int) -> int:
    # 0mmは厳密に0pxとし、補正なしの設定へ不要な1px余白を入れない。
    return max(0, round(mm / 25.4 * dpi))


def choose_font(size: int, handwritten: bool = False) -> ImageFont.ImageFont:
    candidates: list[str] = []
    if sys.platform.startswith("win"):
        if handwritten:
            candidates += [
                r"C:\Windows\Fonts\yumin.ttf",
                r"C:\Windows\Fonts\YuGothM.ttc",
                r"C:\Windows\Fonts\meiryo.ttc",
            ]
        else:
            candidates += [
                r"C:\Windows\Fonts\meiryo.ttc",
                r"C:\Windows\Fonts\YuGothM.ttc",
            ]
    elif sys.platform == "darwin":
        candidates += [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates += [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for candidate in candidates:
        try:
            if os.path.exists(candidate):
                return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def open_source_image(path: Path) -> Image.Image:
    if path.suffix.lower() == ".dng":
        if rawpy is None:
            raise RuntimeError(
                "DNGを開くにはrawpyが必要です。setup_windows.ps1を再実行するか、"
                "JPEGへ書き出してから追加してください。"
            )
        with rawpy.imread(str(path)) as raw:
            rgb = raw.postprocess(
                use_camera_wb=True,
                no_auto_bright=False,
                output_bps=8,
            )
        image = Image.fromarray(rgb)
    else:
        image = Image.open(path)
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGB")
    return image


def get_photo_date(path: Path, image: Image.Image) -> str:
    try:
        exif = image.getexif()
        for tag_id in (36867, 36868, 306):
            value = exif.get(tag_id)
            if not value:
                continue
            raw_value = str(value).replace("\x00", "").strip()
            match = re.match(r"^(\d{4})[:\-/](\d{2})[:\-/](\d{2})", raw_value)
            if match:
                year, month, day = match.groups()
                return f"{year}.{month}.{day}"
    except Exception:
        pass
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y.%m.%d")
    except Exception:
        return "日付不明"


def add_paper_texture(image: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return image
    noise = Image.effect_noise(image.size, 22).convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(0.65)
    alpha = max(5, min(48, int(255 * strength)))
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    overlay.putalpha(noise.point(lambda p: int((p / 255) * alpha)))
    return Image.alpha_composite(image.convert("RGBA"), overlay)


def build_vignette_mask(
    size: tuple[int, int],
    amount: int,
    extent: int,
    softness: int,
) -> Image.Image:
    """
    ケラレ用のマスクを生成する。

    amount:
        暗くする強さ。0～100。
    extent:
        ケラレが中央方向へ広がる範囲。0～100。
    softness:
        境界のぼかし。0は硬く、100は滑らか。
    """
    amount = max(0, min(100, int(amount)))
    extent = max(0, min(100, int(extent)))
    softness = max(0, min(100, int(softness)))

    if amount <= 0:
        return Image.new("L", size, 0)

    gradient = Image.radial_gradient("L").resize(
        size,
        Image.Resampling.BICUBIC,
    )

    # extentが大きいほど暗部の開始点を中央寄りへ移動する。
    start = 248 - round(extent * 1.55)
    # softnessが大きいほど広い距離でなだらかに変化させる。
    transition = max(6, 14 + round(softness * 1.45))
    maximum = round(255 * amount / 100.0)

    def convert(pixel: int) -> int:
        progress = (pixel - start) / transition
        progress = max(0.0, min(1.0, progress))
        # smoothstepで境界の不自然な段差を防ぐ。
        progress = progress * progress * (3.0 - 2.0 * progress)
        return round(maximum * progress)

    return gradient.point(convert)


def apply_photo_adjustments(image: Image.Image, state: PhotoState) -> Image.Image:
    result = image.convert("RGB")
    result = ImageEnhance.Brightness(result).enhance(max(0.2, state.brightness))
    result = ImageEnhance.Contrast(result).enhance(max(0.2, state.contrast))
    result = ImageEnhance.Color(result).enhance(max(0.0, state.saturation))

    if state.warmth:
        r, g, b = result.split()
        amount = max(-40, min(40, state.warmth)) / 100.0
        if amount >= 0:
            r = r.point(lambda p: min(255, int(p * (1.0 + amount * 0.32))))
            b = b.point(lambda p: max(0, int(p * (1.0 - amount * 0.28))))
        else:
            r = r.point(lambda p: max(0, int(p * (1.0 + amount * 0.28))))
            b = b.point(lambda p: min(255, int(p * (1.0 - amount * 0.32))))
        result = Image.merge("RGB", (r, g, b))

    if state.monochrome:
        result = ImageOps.grayscale(result).convert("RGB")

    if state.fade > 0:
        strength = max(0, min(60, state.fade)) / 100.0
        veil = Image.new("RGB", result.size, (220, 215, 204))
        result = Image.blend(result, veil, strength * 0.45)

    if state.grain > 0:
        amount = max(0, min(60, state.grain))
        noise = Image.effect_noise(result.size, max(4, amount * 1.25)).convert("L")
        noise_rgb = Image.merge("RGB", (noise, noise, noise))
        result = Image.blend(result, noise_rgb, amount / 270.0)

    if state.vignette > 0:
        mask = build_vignette_mask(
            result.size,
            state.vignette,
            state.vignette_extent,
            state.vignette_softness,
        )
        dark = Image.new("RGB", result.size, (12, 12, 12))
        result = Image.composite(dark, result, mask)

    return result

def rotate_source(image: Image.Image, rotation: int) -> Image.Image:
    rotation = rotation % 360
    if rotation == 90:
        return image.transpose(Image.Transpose.ROTATE_90)
    if rotation == 180:
        return image.transpose(Image.Transpose.ROTATE_180)
    if rotation == 270:
        return image.transpose(Image.Transpose.ROTATE_270)
    return image


def render_photo_box(
    source: Image.Image,
    box_size: tuple[int, int],
    state: PhotoState,
    background: tuple[int, int, int],
) -> Image.Image:
    box_width, box_height = box_size
    image = rotate_source(source, state.rotation)
    image = apply_photo_adjustments(image, state)
    source_width, source_height = image.size

    contain_mode = state.crop_mode in {
        "縦横比で自動最適化（見切れ防止)",
        "縦横比で自動最適化（見切れ防止）",
        "写真全体を収める",
    }
    if contain_mode:
        base_scale = min(box_width / source_width, box_height / source_height)
    else:
        base_scale = max(box_width / source_width, box_height / source_height)

    scale = max(0.1, base_scale * max(0.25, min(4.0, state.zoom)))
    resized = image.resize(
        (max(1, round(source_width * scale)), max(1, round(source_height * scale))),
        Image.Resampling.LANCZOS,
    )

    center_x = box_width / 2 + state.pan_x * box_width
    center_y = box_height / 2 + state.pan_y * box_height
    paste_x = round(center_x - resized.width / 2)
    paste_y = round(center_y - resized.height / 2)

    canvas = Image.new("RGB", (box_width, box_height), background)
    canvas.paste(resized, (paste_x, paste_y))
    return canvas


def wrap_caption_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized or max_lines <= 0:
        return []
    lines: list[str] = []
    overflow = False
    paragraphs = normalized.split("\n")
    for paragraph_index, paragraph in enumerate(paragraphs):
        if len(lines) >= max_lines:
            overflow = True
            break
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for character in paragraph:
            candidate = current + character
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
                continue
            lines.append(current)
            current = character
            if len(lines) >= max_lines:
                overflow = True
                break
        if overflow:
            break
        if current:
            lines.append(current)
        if len(lines) >= max_lines and paragraph_index < len(paragraphs) - 1:
            overflow = True
            break
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        overflow = True
    if overflow and lines:
        last = lines[-1].rstrip()
        while last:
            candidate = last + "…"
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width:
                lines[-1] = candidate
                break
            last = last[:-1]
        if not last:
            lines[-1] = "…"
    return lines


def layout_rects(
    layout_name: str,
    page_size: tuple[int, int],
    safe_insets: tuple[int, int, int, int],
    gutter: int,
) -> list[tuple[int, int, int, int]]:
    page_width, page_height = page_size
    top, right, bottom, left = safe_insets
    x0, y0 = left, top
    x1, y1 = page_width - right, page_height - bottom
    width, height = max(1, x1 - x0), max(1, y1 - y0)

    if layout_name == "2枚（上下）":
        h = (height - gutter) // 2
        return [(x0, y0, x1, y0 + h), (x0, y0 + h + gutter, x1, y1)]
    if layout_name == "2枚（左右）":
        w = (width - gutter) // 2
        return [(x0, y0, x0 + w, y1), (x0 + w + gutter, y0, x1, y1)]
    if layout_name == "4枚":
        w = (width - gutter) // 2
        h = (height - gutter) // 2
        return [
            (x0, y0, x0 + w, y0 + h),
            (x0 + w + gutter, y0, x1, y0 + h),
            (x0, y0 + h + gutter, x0 + w, y1),
            (x0 + w + gutter, y0 + h + gutter, x1, y1),
        ]
    if layout_name == "大1＋小2":
        if height >= width:
            big_h = round((height - gutter) * 0.64)
            small_w = (width - gutter) // 2
            return [
                (x0, y0, x1, y0 + big_h),
                (x0, y0 + big_h + gutter, x0 + small_w, y1),
                (x0 + small_w + gutter, y0 + big_h + gutter, x1, y1),
            ]
        big_w = round((width - gutter) * 0.64)
        small_h = (height - gutter) // 2
        return [
            (x0, y0, x0 + big_w, y1),
            (x0 + big_w + gutter, y0, x1, y0 + small_h),
            (x0 + big_w + gutter, y0 + small_h + gutter, x1, y1),
        ]
    return [(x0, y0, x1, y1)]


def fit_photo_region(
    source_size: tuple[int, int],
    max_size: tuple[int, int],
    mode: str,
) -> tuple[int, int]:
    max_width, max_height = max(1, max_size[0]), max(1, max_size[1])
    if mode == "縦横比で自動最適化（見切れ防止）":
        source_width, source_height = source_size
        aspect = source_width / max(1, source_height)
        width = max_width
        height = max(1, round(width / aspect))
        if height > max_height:
            height = max_height
            width = max(1, round(height * aspect))
        return width, height
    if mode == "写真全体を収める":
        return max_width, max_height
    return max_width, max_height


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def render_card(
    source: Image.Image,
    path: Path,
    state: PhotoState,
    card_size: tuple[int, int],
    global_options: GlobalOptions,
    index: int,
) -> tuple[Image.Image, CardMeta]:
    card_width, card_height = card_size
    short_edge = min(card_width, card_height)
    preset = FRAME_PRESETS.get(state.frame_name, FRAME_PRESETS["クラシックホワイト"])
    paper = tuple(preset["paper"])
    text_color = tuple(preset["text"]) + (255,)
    border_color = tuple(preset["border"]) + (255,)

    side_margin = max(5, round(short_edge * 0.055))
    top_margin = side_margin
    footer_gap = max(4, round(short_edge * 0.025))
    date_gap = max(4, round(short_edge * 0.015))
    caption_size = max(10, round(short_edge * 0.032))
    date_size = max(9, round(short_edge * 0.019))
    caption_pitch = caption_size + max(2, caption_size // 5)
    date_height = date_size if state.add_date else 0
    bottom_safety = max(
        side_margin,
        mm_to_pixels(global_options.date_inset_mm, global_options.print_dpi)
        if card_width > 700 else round(short_edge * 0.07),
    )
    requested_caption_height = state.caption_lines * caption_pitch if state.caption else 0
    footer_height = max(
        round(card_height * 0.20),
        footer_gap + requested_caption_height + (date_gap + date_height if state.add_date else 0) + bottom_safety,
    )
    max_photo_width = max(1, card_width - side_margin * 2)
    max_photo_height = max(1, card_height - top_margin - footer_height)

    rotated_size = source.size if state.rotation % 180 == 0 else (source.height, source.width)
    photo_width, photo_height = fit_photo_region(
        rotated_size,
        (max_photo_width, max_photo_height),
        state.crop_mode,
    )
    photo_x = (card_width - photo_width) // 2
    photo_y = top_margin

    card = Image.new("RGBA", (card_width, card_height), (*paper, 255))
    photo = render_photo_box(source, (photo_width, photo_height), state, paper)
    card.paste(photo, (photo_x, photo_y))
    draw = ImageDraw.Draw(card)
    draw.rectangle(
        (photo_x - 1, photo_y - 1, photo_x + photo_width, photo_y + photo_height),
        outline=border_color,
        width=max(1, short_edge // 900),
    )

    footer_top = photo_y + photo_height + footer_gap
    date_rect = (0, 0, 0, 0)
    date_top: Optional[int] = None
    date_draw_data: Optional[tuple[int, int, str, ImageFont.ImageFont]] = None
    if state.add_date:
        date_text = get_photo_date(path, source)
        date_font = choose_font(date_size)
        date_bbox = draw.textbbox((0, 0), date_text, font=date_font)
        safe_right = max(side_margin, bottom_safety)
        safe_bottom = max(side_margin, bottom_safety)
        date_x = card_width - safe_right - date_bbox[2]
        date_y = card_height - safe_bottom - date_bbox[3]
        date_top = date_y + date_bbox[1]
        date_rect = (
            date_x + date_bbox[0], date_y + date_bbox[1],
            date_x + date_bbox[2], date_y + date_bbox[3],
        )
        date_draw_data = (date_x, date_y, date_text, date_font)

    caption_rect = (side_margin, footer_top, card_width - side_margin, footer_top)
    if state.caption:
        caption_bottom = date_top - date_gap if date_top is not None else card_height - bottom_safety
        available_height = max(1, caption_bottom - footer_top)
        font_size = caption_size
        font = choose_font(font_size, handwritten=True)
        lines = wrap_caption_text(
            draw, state.caption, font, card_width - side_margin * 2, state.caption_lines
        )
        sample = draw.textbbox((0, 0), "あAg", font=font)
        line_height = max(1, sample[3] - sample[1])
        line_gap = max(2, font_size // 5)
        total = len(lines) * line_height + max(0, len(lines) - 1) * line_gap
        while total > available_height and font_size > 8:
            font_size -= 1
            font = choose_font(font_size, handwritten=True)
            lines = wrap_caption_text(
                draw, state.caption, font, card_width - side_margin * 2, state.caption_lines
            )
            sample = draw.textbbox((0, 0), "あAg", font=font)
            line_height = max(1, sample[3] - sample[1])
            line_gap = max(2, font_size // 5)
            total = len(lines) * line_height + max(0, len(lines) - 1) * line_gap
        current_y = footer_top
        bottom_used = footer_top
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (card_width - (bbox[2] - bbox[0])) // 2
            draw.text((x, current_y - bbox[1]), line, font=font, fill=text_color)
            current_y += line_height + line_gap
            bottom_used = current_y
        caption_rect = (side_margin, footer_top, card_width - side_margin, bottom_used)

    if date_draw_data is not None:
        draw.text(date_draw_data[:2], date_draw_data[2], font=date_draw_data[3], fill=text_color)

    if preset.get("notebook"):
        line_y = footer_top
        line_step = max(8, round(short_edge * 0.035))
        while line_y < card_height - side_margin:
            draw.line((side_margin, line_y, card_width - side_margin, line_y), fill=(168, 186, 204, 65), width=1)
            line_y += line_step

    if state.paper_texture:
        card = add_paper_texture(card, float(preset["texture"]))

    radius_fraction = float(preset.get("rounded", 0.0))
    if radius_fraction > 0:
        radius = max(1, round(short_edge * radius_fraction))
        mask = rounded_mask(card.size, radius)
        card.putalpha(mask)

    meta = CardMeta(
        index=index,
        card_rect=(0, 0, card_width, card_height),
        photo_rect=(photo_x, photo_y, photo_x + photo_width, photo_y + photo_height),
        caption_rect=caption_rect,
        date_rect=date_rect,
    )
    return card, meta


def render_page(
    states: list[PhotoState],
    start_index: int,
    global_options: GlobalOptions,
    printer_profile: PrinterProfile,
    preview_dpi: Optional[int] = None,
    image_cache: Optional[dict[str, Image.Image]] = None,
    explicit_indices: Optional[list[int]] = None,
    gutter_override: Optional[int] = None,
) -> PageRenderResult:
    """
    ページをレンダリングする。

    複数画像ページでは、画像同士の隙間を0にできる一方、
    集合全体が用紙端へ寄りすぎるとフチなし印刷拡大や搬送誤差で
    上下が欠けることがある。

    そのため複数画像時だけ、集合全体の外周へ印刷保護余白を確保する。
    プリンター補正値とは加算せず、大きい側を採用する。
    """
    paper_mm = PAPER_PRESETS.get(global_options.paper_name)
    dpi = preview_dpi or global_options.print_dpi
    if paper_mm is None:
        width = global_options.output_width or 2048
        page_size = (width, round(width * 1.48))
    else:
        page_size = (
            mm_to_pixels(paper_mm[0], dpi),
            mm_to_pixels(paper_mm[1], dpi),
        )

    page_width, page_height = page_size
    page = Image.new(
        "RGBA",
        page_size,
        (*global_options.page_background, 255),
    )
    effective_options = GlobalOptions(**asdict(global_options))
    effective_options.print_dpi = dpi

    layout_capacity = LAYOUT_CAPACITY.get(
        effective_options.layout_name,
        1,
    )
    if explicit_indices is None:
        indices_to_render = [
            start_index + slot
            for slot in range(layout_capacity)
            if start_index + slot < len(states)
        ]
    else:
        indices_to_render = [
            index
            for index in explicit_indices[:layout_capacity]
            if 0 <= index < len(states)
        ]

    if global_options.apply_printer_profile:
        safe_insets = (
            mm_to_pixels(printer_profile.top_mm, dpi),
            mm_to_pixels(printer_profile.right_mm, dpi),
            mm_to_pixels(printer_profile.bottom_mm, dpi),
            mm_to_pixels(printer_profile.left_mm, dpi),
        )
    else:
        safe_insets = (0, 0, 0, 0)

    # 複数画像だけ、集合全体を用紙端から内側へ移動する。
    # 内部の画像間隔はgutter_override=0のまま維持できる。
    if len(indices_to_render) >= 2:
        vertical_guard = mm_to_pixels(
            max(0.0, global_options.multi_vertical_guard_mm),
            dpi,
        )
        horizontal_guard = mm_to_pixels(
            max(0.0, global_options.multi_horizontal_guard_mm),
            dpi,
        )
        safe_insets = (
            max(safe_insets[0], vertical_guard),
            max(safe_insets[1], horizontal_guard),
            max(safe_insets[2], vertical_guard),
            max(safe_insets[3], horizontal_guard),
        )

    gutter = (
        max(0, int(gutter_override))
        if gutter_override is not None
        else max(3, mm_to_pixels(3.0, dpi))
    )
    rects = layout_rects(
        effective_options.layout_name,
        page_size,
        safe_insets,
        gutter,
    )
    cards: list[CardMeta] = []

    for slot, rect in enumerate(rects):
        if slot >= len(indices_to_render):
            continue

        index = indices_to_render[slot]
        state = states[index]
        path = state.file_path
        cache_key = str(path.resolve()) if path.exists() else str(path)

        try:
            if image_cache is not None and cache_key in image_cache:
                source = image_cache[cache_key].copy()
            else:
                source = open_source_image(path)
                if image_cache is not None:
                    image_cache[cache_key] = source.copy()
        except Exception:
            source = Image.new("RGB", (1200, 900), (220, 220, 220))
            placeholder = ImageDraw.Draw(source)
            placeholder.text(
                (40, 40),
                "画像を開けません",
                fill=(70, 70, 70),
                font=choose_font(44),
            )

        x0, y0, x1, y1 = rect
        card, meta = render_card(
            source,
            path,
            state,
            (max(1, x1 - x0), max(1, y1 - y0)),
            effective_options,
            index,
        )
        page.alpha_composite(card, (x0, y0))
        cards.append(
            CardMeta(
                index=index,
                card_rect=(x0, y0, x1, y1),
                photo_rect=(
                    x0 + meta.photo_rect[0],
                    y0 + meta.photo_rect[1],
                    x0 + meta.photo_rect[2],
                    y0 + meta.photo_rect[3],
                ),
                caption_rect=(
                    x0 + meta.caption_rect[0],
                    y0 + meta.caption_rect[1],
                    x0 + meta.caption_rect[2],
                    y0 + meta.caption_rect[3],
                ),
                date_rect=(
                    x0 + meta.date_rect[0],
                    y0 + meta.date_rect[1],
                    x0 + meta.date_rect[2],
                    y0 + meta.date_rect[3],
                ),
            )
        )

    safety_rect = (
        safe_insets[3],
        safe_insets[0],
        page_width - safe_insets[1],
        page_height - safe_insets[2],
    )
    return PageRenderResult(page, cards, safety_rect)

def save_image(image: Image.Image, path: Path, options: GlobalOptions) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    dpi = (options.print_dpi, options.print_dpi)
    if options.save_format == "PNG":
        image.save(path, "PNG", optimize=True, dpi=dpi)
        return
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, options.page_background)
        background.paste(image, mask=image.getchannel("A"))
        image = background
    image.convert("RGB").save(
        path, "JPEG", quality=max(70, min(100, options.jpeg_quality)),
        optimize=True, progressive=True, dpi=dpi,
    )


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {
            "last": {}, "presets": {}, "printer_profile": asdict(PrinterProfile()),
            "tutorial_seen": False,
        }
        self.load()

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except Exception:
            pass

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")


class ScrollableSettings(ttk.LabelFrame):
    def __init__(self, master: tk.Misc, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, width=360, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.inner = ttk.Frame(self.canvas, padding=(12, 8, 12, 18))
        self.inner.columnconfigure(0, weight=1)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._update_region)
        self.canvas.bind("<Configure>", self._resize_inner)
        self._bind_recursive(self)

    def _update_region(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_inner(self, event) -> None:
        self.canvas.itemconfigure(self.window_id, width=max(1, event.width))

    def _bind_recursive(self, widget: tk.Misc) -> None:
        widget.bind("<MouseWheel>", self._wheel, add="+")
        widget.bind("<Button-4>", self._wheel, add="+")
        widget.bind("<Button-5>", self._wheel, add="+")
        for child in widget.winfo_children():
            self._bind_recursive(child)

    def refresh_bindings(self) -> None:
        self._bind_recursive(self)

    def _wheel(self, event):
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return None
            units = -int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        self.canvas.yview_scroll(units, "units")
        return "break"


class PolaroidApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME}  v{APP_VERSION} — Print Studio")
        self.geometry("1460x900")
        self.minsize(1120, 720)

        self.store = SettingsStore(SETTINGS_FILE)
        self.photos: list[PhotoState] = []
        self.image_cache: dict[str, Image.Image] = {}
        self.selected_index: Optional[int] = None
        self.preview_photo: Optional[ImageTk.PhotoImage] = None
        self.preview_result: Optional[PageRenderResult] = None
        self.preview_display = (0, 0, 1.0)
        self.drag_origin: Optional[tuple[int, int, float, float]] = None
        self._syncing = False
        self._preview_after_id: Optional[str] = None
        self.project_path: Optional[Path] = None

        profile_data = self.store.data.get("printer_profile", {})
        self.printer_profile = PrinterProfile(**{
            key: profile_data.get(key, getattr(PrinterProfile(), key))
            for key in asdict(PrinterProfile())
        })

        last = self.store.data.get("last", {})

        # v2.6: 複数画像の外周保護を「標準」へ戻す。
        # v2.5の既定値「なし」または設定値なしの場合だけ一度移行し、
        # 控えめ・安全・広めなど利用者が明示的に選んだ値は維持する。
        settings_revision = int(
            self.store.data.get("settings_revision", 0)
        )
        if settings_revision < 26:
            if last.get("multi_guard_label") in {
                None,
                "なし（用紙端まで使用）",
            }:
                last["multi_guard_label"] = (
                    "標準 上下4mm・左右2mm（推奨）"
                )
            self.store.data["settings_revision"] = 26
            self.store.save()

        self.output_dir = tk.StringVar(
            value=last.get("output_dir", str(Path.home() / "Pictures" / APP_NAME))
        )
        self.layout_var = tk.StringVar(value=last.get("layout_name", "1枚"))
        self.paper_var = tk.StringVar(value=last.get("paper_name", "はがき 縦（100×148mm）"))
        self.dpi_var = tk.StringVar(value=last.get("dpi_label", "300 dpi（印刷推奨）"))
        self.date_inset_var = tk.StringVar(value=last.get("date_inset_label", "安全 12mm（推奨）"))
        self.multi_guard_var = tk.StringVar(
            value=last.get(
                "multi_guard_label",
                "標準 上下4mm・左右2mm（推奨）",
            )
        )
        self.output_width_var = tk.StringVar(value=last.get("output_width_label", "高画質 2048px"))
        self.format_var = tk.StringVar(value=last.get("format", "JPEG"))
        self.quality_var = tk.IntVar(value=int(last.get("quality", 94)))
        self.apply_profile_var = tk.BooleanVar(value=bool(last.get("apply_profile", True)))
        self.show_guides_var = tk.BooleanVar(value=bool(last.get("show_guides", True)))

        self.frame_var = tk.StringVar(value="クラシックホワイト")
        self.crop_var = tk.StringVar(value="縦横比で自動最適化（見切れ防止）")
        self.filter_var = tk.StringVar(value="なし")
        self.caption_lines_var = tk.StringVar(value="2行（標準）")
        self.add_date_var = tk.BooleanVar(value=True)
        self.texture_var = tk.BooleanVar(value=True)
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.pan_x_var = tk.DoubleVar(value=0.0)
        self.pan_y_var = tk.DoubleVar(value=0.0)
        self.brightness_var = tk.DoubleVar(value=1.0)
        self.contrast_var = tk.DoubleVar(value=1.0)
        self.saturation_var = tk.DoubleVar(value=1.0)
        self.warmth_var = tk.IntVar(value=0)
        self.grain_var = tk.IntVar(value=0)
        self.vignette_var = tk.IntVar(value=0)
        self.vignette_extent_var = tk.IntVar(value=45)
        self.vignette_softness_var = tk.IntVar(value=65)
        self.fade_var = tk.IntVar(value=0)
        self.monochrome_var = tk.BooleanVar(value=False)
        self.preset_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="写真を追加してください。")

        self._build_style()
        self._build_ui()
        self._bind_traces()
        self._update_vignette_indicator()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(150, self.update_preview)
        self.after(350, self._show_tutorial_if_needed)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Yu Gothic UI", 18, "bold"))
        style.configure("Section.TLabel", font=("Yu Gothic UI", 11, "bold"))
        style.configure("Primary.TButton", font=("Yu Gothic UI", 10, "bold"), padding=(12, 8))
        style.configure("TButton", padding=(7, 5))
        style.configure("TLabel", font=("Yu Gothic UI", 9))
        style.configure("TCheckbutton", font=("Yu Gothic UI", 9))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=0)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="画像をポラロイド風に。").pack(side="left", padx=14, pady=(7, 0))
        ttk.Button(header, text="使い方", command=self.show_tutorial).pack(side="right")
        ttk.Button(header, text="バージョン情報", command=self.show_about).pack(side="right", padx=(0, 6))

        left = ttk.LabelFrame(root, text="1. 写真とページ順", padding=8)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 8))
        left.rowconfigure(3, weight=1)

        add_row = ttk.Frame(left)
        add_row.grid(row=0, column=0, sticky="ew")
        ttk.Button(add_row, text="写真を追加", command=self.add_files).pack(side="left", fill="x", expand=True)
        ttk.Button(add_row, text="フォルダ", command=self.add_folder).pack(side="left", fill="x", expand=True, padx=(5, 0))

        project_row = ttk.Frame(left)
        project_row.grid(row=1, column=0, sticky="ew", pady=(5, 6))
        ttk.Button(project_row, text="プロジェクト保存", command=self.save_project).pack(side="left", fill="x", expand=True)
        ttk.Button(project_row, text="読込", command=self.load_project).pack(side="left", fill="x", expand=True, padx=(5, 0))

        ttk.Label(left, text="複数選択でまとめてプレビュー / クリックで写真ごとの設定を編集").grid(row=2, column=0, sticky="w", pady=(0, 4))
        list_frame = ttk.Frame(left)
        list_frame.grid(row=3, column=0, sticky="nsew")
        self.file_list = tk.Listbox(
            list_frame, width=31, height=28, exportselection=False,
            selectmode=tk.EXTENDED, font=("Yu Gothic UI", 9),
        )
        file_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=file_scroll.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        file_scroll.pack(side="right", fill="y")
        self.file_list.bind("<<ListboxSelect>>", self._list_selection_changed)

        order_row = ttk.Frame(left)
        order_row.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        for label, command in [
            ("↑", self.move_up), ("↓", self.move_down),
            ("複製", self.duplicate_selected), ("削除", self.remove_selected),
        ]:
            ttk.Button(order_row, text=label, command=command).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(left, text="全消去", command=self.clear_files).grid(row=5, column=0, sticky="ew", pady=(5, 0))

        center = ttk.LabelFrame(root, text="2. プレビューと直接編集", padding=8)
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 8))
        center.rowconfigure(1, weight=1)
        center.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(center)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(toolbar, text="↶ 90°", command=lambda: self.rotate_selected(-90)).pack(side="left")
        ttk.Button(toolbar, text="↷ 90°", command=lambda: self.rotate_selected(90)).pack(side="left", padx=(4, 0))
        ttk.Button(toolbar, text="位置・拡大を戻す", command=self.reset_transform).pack(side="left", padx=(4, 0))
        ttk.Checkbutton(toolbar, text="印刷安全ガイド", variable=self.show_guides_var, command=self.update_preview).pack(side="left", padx=10)
        ttk.Button(toolbar, text="印刷診断", command=self.show_diagnostics).pack(side="right")
        ttk.Button(toolbar, text="テストシート", command=self.create_test_sheet).pack(side="right", padx=(0, 5))

        self.preview_canvas = tk.Canvas(center, bg="#d6d6d6", highlightthickness=0)
        self.preview_canvas.grid(row=1, column=0, sticky="nsew")
        self.preview_canvas.bind("<Configure>", lambda _e: self._schedule_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self._preview_press)
        self.preview_canvas.bind("<B1-Motion>", self._preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", lambda _e: setattr(self, "drag_origin", None))
        self.preview_canvas.bind("<MouseWheel>", self._preview_wheel)
        self.preview_canvas.bind("<Button-4>", self._preview_wheel)
        self.preview_canvas.bind("<Button-5>", self._preview_wheel)

        settings = ScrollableSettings(root, text="3. 仕上がり設定")
        settings.grid(row=1, column=2, sticky="nse")
        right = settings.inner
        row = 0

        row = self._section_label(right, row, "写真ごとの設定")
        row = self._combo(right, row, "フレーム", self.frame_var, list(FRAME_PRESETS))
        row = self._combo(right, row, "写真の収め方", self.crop_var, CROP_MODES)
        row = self._combo(right, row, "写真加工プリセット", self.filter_var, list(FILTER_PRESETS))

        ttk.Label(right, text="下部に入れる文字").grid(row=row, column=0, sticky="w", pady=(7, 3)); row += 1
        caption_frame = ttk.Frame(right); caption_frame.grid(row=row, column=0, sticky="ew"); caption_frame.columnconfigure(0, weight=1)
        self.caption_text = tk.Text(caption_frame, width=35, height=2, wrap="char", undo=True, font=("Yu Gothic UI", 9))
        self.caption_text.grid(row=0, column=0, sticky="ew")
        caption_scroll = ttk.Scrollbar(caption_frame, orient="vertical", command=self.caption_text.yview)
        caption_scroll.grid(row=0, column=1, sticky="ns")
        self.caption_text.configure(yscrollcommand=caption_scroll.set)
        self.caption_text.bind("<<Modified>>", self._caption_modified)
        self.caption_text.edit_modified(False); row += 1
        row = self._combo(right, row, "文字の入力行数", self.caption_lines_var, list(CAPTION_LINE_PRESETS))
        ttk.Checkbutton(right, text="撮影日を入れる", variable=self.add_date_var).grid(row=row, column=0, sticky="w"); row += 1
        ttk.Checkbutton(right, text="紙の質感を付ける", variable=self.texture_var).grid(row=row, column=0, sticky="w"); row += 1

        row = self._section_label(right, row, "位置")
        row = self._scale(right, row, "拡大率", self.zoom_var, 0.5, 3.0, 0.05)
        row = self._scale(right, row, "横位置", self.pan_x_var, -1.5, 1.5, 0.01)
        row = self._scale(right, row, "縦位置", self.pan_y_var, -1.5, 1.5, 0.01)

        position_buttons = ttk.Frame(right)
        position_buttons.grid(row=row, column=0, sticky="ew", pady=(5, 0))
        ttk.Button(
            position_buttons,
            text="位置をデフォルトへ戻す",
            command=self.reset_transform,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            position_buttons,
            text="左90°",
            command=lambda: self.rotate_selected(-90),
        ).pack(side="left", padx=(4, 0))
        ttk.Button(
            position_buttons,
            text="右90°",
            command=lambda: self.rotate_selected(90),
        ).pack(side="left", padx=(4, 0))
        row += 1

        row = self._section_label(right, row, "写真加工")
        row = self._scale(right, row, "明るさ", self.brightness_var, 0.5, 1.5, 0.01)
        row = self._scale(right, row, "コントラスト", self.contrast_var, 0.5, 1.5, 0.01)
        row = self._scale(right, row, "彩度", self.saturation_var, 0.0, 1.8, 0.01)
        row = self._scale(right, row, "色温度", self.warmth_var, -40, 40, 1)
        row = self._scale(right, row, "粒状感", self.grain_var, 0, 60, 1)
        row = self._scale(right, row, "ケラレ量", self.vignette_var, 0, 100, 1)
        row = self._scale(right, row, "ケラレ範囲", self.vignette_extent_var, 0, 100, 1)
        row = self._scale(right, row, "ケラレぼかし", self.vignette_softness_var, 0, 100, 1)

        ttk.Label(
            right,
            text="ケラレ・インジケーター",
        ).grid(row=row, column=0, sticky="w", pady=(6, 3))
        row += 1

        self.vignette_indicator = tk.Canvas(
            right,
            width=286,
            height=92,
            bg="#dedede",
            highlightthickness=1,
            highlightbackground="#aaaaaa",
        )
        self.vignette_indicator.grid(row=row, column=0, sticky="ew")
        row += 1

        row = self._scale(right, row, "色あせ", self.fade_var, 0, 60, 1)
        ttk.Checkbutton(
            right,
            text="白黒化",
            variable=self.monochrome_var,
        ).grid(row=row, column=0, sticky="w")
        row += 1

        processing_buttons = ttk.Frame(right)
        processing_buttons.grid(row=row, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(
            processing_buttons,
            text="写真加工をデフォルトへ戻す",
            command=self.reset_photo_adjustments,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            processing_buttons,
            text="位置と加工を全て戻す",
            command=self.reset_position_and_adjustments,
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))
        row += 1

        row = self._section_label(right, row, "ページと印刷")
        row = self._combo(right, row, "写真レイアウト", self.layout_var, list(LAYOUT_CAPACITY))
        row = self._combo(right, row, "印刷用紙", self.paper_var, list(PAPER_PRESETS))
        row = self._combo(right, row, "印刷解像度", self.dpi_var, list(DPI_PRESETS))
        row = self._combo(right, row, "日付の印刷安全余白", self.date_inset_var, list(DATE_INSET_PRESETS))
        row = self._combo(
            right,
            row,
            "複数画像の外周保護",
            self.multi_guard_var,
            list(MULTI_IMAGE_GUARD_PRESETS),
        )
        ttk.Label(
            right,
            text="画像同士の隙間は0のまま、集合全体だけを用紙端から内側へ移動します。",
            wraplength=290,
        ).grid(row=row, column=0, sticky="w", pady=(2, 4))
        row += 1
        row = self._combo(right, row, "基準解像度", self.output_width_var, list(OUTPUT_WIDTHS))
        ttk.Checkbutton(right, text="プリンター補正を適用", variable=self.apply_profile_var).grid(row=row, column=0, sticky="w"); row += 1
        ttk.Button(right, text="プリンター補正を設定", command=self.configure_printer_profile).grid(row=row, column=0, sticky="ew", pady=(4, 0)); row += 1

        row = self._section_label(right, row, "設定プリセット")
        self.preset_combo = ttk.Combobox(right, textvariable=self.preset_var, values=self._preset_names(), state="readonly", width=34)
        self.preset_combo.grid(row=row, column=0, sticky="ew"); row += 1
        preset_row = ttk.Frame(right); preset_row.grid(row=row, column=0, sticky="ew", pady=(4, 0)); row += 1
        ttk.Button(preset_row, text="保存", command=self.save_user_preset).pack(side="left", fill="x", expand=True)
        ttk.Button(preset_row, text="読込", command=self.load_user_preset).pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Button(preset_row, text="削除", command=self.delete_user_preset).pack(side="left", fill="x", expand=True, padx=(4, 0))

        row = self._section_label(right, row, "保存")
        row = self._combo(right, row, "保存形式", self.format_var, ["JPEG", "PNG"])
        quality_frame = ttk.Frame(right); quality_frame.grid(row=row, column=0, sticky="ew", pady=(4, 0)); row += 1
        ttk.Label(quality_frame, text="JPEG画質").pack(side="left")
        ttk.Spinbox(quality_frame, from_=70, to=100, width=6, textvariable=self.quality_var).pack(side="right")
        ttk.Label(right, text="保存先").grid(row=row, column=0, sticky="w", pady=(7, 3)); row += 1
        ttk.Entry(right, textvariable=self.output_dir, width=35).grid(row=row, column=0, sticky="ew"); row += 1
        ttk.Button(right, text="保存先を選ぶ", command=self.select_output_dir).grid(row=row, column=0, sticky="ew", pady=(4, 0)); row += 1
        ttk.Button(right, text="現在のページを変換", style="Primary.TButton", command=self.convert_current_page).grid(row=row, column=0, sticky="ew", pady=(12, 5)); row += 1
        ttk.Button(right, text="すべてのページを変換", style="Primary.TButton", command=self.convert_all_pages).grid(row=row, column=0, sticky="ew"); row += 1
        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.grid(row=row, column=0, sticky="ew", pady=(10, 6)); row += 1
        ttk.Button(right, text="保存先を開く", command=self.open_output_dir).grid(row=row, column=0, sticky="ew"); row += 1
        ttk.Button(right, text="エラーログを開く", command=self.open_error_log).grid(row=row, column=0, sticky="ew", pady=(4, 0)); row += 1

        settings.refresh_bindings()

        footer = ttk.Frame(root)
        footer.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(7, 0))
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Label(footer, text=f"v{APP_VERSION} Print Studio").pack(side="right")

    def _section_label(self, parent: ttk.Frame, row: int, text: str) -> int:
        if row:
            ttk.Separator(parent).grid(row=row, column=0, sticky="ew", pady=10); row += 1
        ttk.Label(parent, text=text, style="Section.TLabel").grid(row=row, column=0, sticky="w"); return row + 1

    def _combo(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable, values: list[str]) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(6, 3)); row += 1
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=34).grid(row=row, column=0, sticky="ew")
        return row + 1

    def _scale(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable, from_: float, to: float, resolution: float) -> int:
        frame = ttk.Frame(parent); frame.grid(row=row, column=0, sticky="ew", pady=(5, 0)); frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=label, width=10).grid(row=0, column=0, sticky="w")
        scale = tk.Scale(
            frame, variable=variable, from_=from_, to=to, resolution=resolution,
            orient="horizontal", showvalue=True, length=220,
        )
        scale.grid(row=0, column=1, sticky="ew")
        return row + 1

    def _bind_traces(self) -> None:
        photo_vars = [
            self.frame_var, self.crop_var, self.filter_var, self.caption_lines_var,
            self.add_date_var, self.texture_var, self.zoom_var,
            self.pan_x_var, self.pan_y_var, self.brightness_var,
            self.contrast_var, self.saturation_var, self.warmth_var, self.grain_var,
            self.vignette_var, self.vignette_extent_var,
            self.vignette_softness_var, self.fade_var, self.monochrome_var,
        ]
        for variable in photo_vars:
            variable.trace_add("write", self._photo_control_changed)
        global_vars = [
            self.layout_var, self.paper_var, self.dpi_var, self.date_inset_var,
            self.multi_guard_var, self.output_width_var, self.format_var, self.quality_var,
            self.apply_profile_var, self.show_guides_var,
        ]
        for variable in global_vars:
            variable.trace_add("write", lambda *_args: self._schedule_preview())

    def _caption_modified(self, _event=None) -> None:
        if not self.caption_text.edit_modified():
            return
        self.caption_text.edit_modified(False)
        if not self._syncing and self.selected_index is not None:
            self.photos[self.selected_index].caption = self.caption_text.get("1.0", "end-1c")
        self._schedule_preview()

    def _photo_control_changed(self, *_args) -> None:
        if self._syncing or self.selected_index is None or self.selected_index >= len(self.photos):
            return
        state = self.photos[self.selected_index]
        # Applying a named filter immediately sets all related controls.
        if state.filter_name != self.filter_var.get():
            state.filter_name = self.filter_var.get()
            preset = FILTER_PRESETS.get(state.filter_name)
            if preset:
                self._syncing = True
                self.brightness_var.set(preset["brightness"])
                self.contrast_var.set(preset["contrast"])
                self.saturation_var.set(preset["saturation"])
                self.warmth_var.set(preset["warmth"])
                self.grain_var.set(preset["grain"])
                self.vignette_var.set(preset["vignette"])
                self.vignette_extent_var.set(
                    preset.get("vignette_extent", 45)
                )
                self.vignette_softness_var.set(
                    preset.get("vignette_softness", 65)
                )
                self.fade_var.set(preset["fade"])
                self.monochrome_var.set(preset["monochrome"])
                self._syncing = False
        state.frame_name = self.frame_var.get()
        state.crop_mode = self.crop_var.get()
        state.filter_name = self.filter_var.get()
        state.caption_lines = CAPTION_LINE_PRESETS.get(self.caption_lines_var.get(), 2)
        state.add_date = self.add_date_var.get()
        state.paper_texture = self.texture_var.get()
        state.zoom = float(self.zoom_var.get())
        state.pan_x = float(self.pan_x_var.get())
        state.pan_y = float(self.pan_y_var.get())
        state.brightness = float(self.brightness_var.get())
        state.contrast = float(self.contrast_var.get())
        state.saturation = float(self.saturation_var.get())
        state.warmth = int(self.warmth_var.get())
        state.grain = int(self.grain_var.get())
        state.vignette = int(self.vignette_var.get())
        state.vignette_extent = int(self.vignette_extent_var.get())
        state.vignette_softness = int(self.vignette_softness_var.get())
        state.fade = int(self.fade_var.get())
        state.monochrome = self.monochrome_var.get()
        self.caption_text.configure(height=min(state.caption_lines, 6))
        self._update_vignette_indicator()
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        if self._preview_after_id:
            try:
                self.after_cancel(self._preview_after_id)
            except Exception:
                pass
        self._preview_after_id = self.after(80, self.update_preview)

    def _current_global_options(self) -> GlobalOptions:
        vertical_guard, horizontal_guard = MULTI_IMAGE_GUARD_PRESETS.get(
            self.multi_guard_var.get(),
            (4.0, 2.0),
        )
        return GlobalOptions(
            layout_name=self.layout_var.get(),
            paper_name=self.paper_var.get(),
            print_dpi=DPI_PRESETS.get(self.dpi_var.get(), 300),
            date_inset_mm=DATE_INSET_PRESETS.get(self.date_inset_var.get(), 12.0),
            output_width=OUTPUT_WIDTHS.get(self.output_width_var.get()),
            save_format=self.format_var.get(),
            jpeg_quality=int(self.quality_var.get()),
            apply_printer_profile=self.apply_profile_var.get(),
            multi_vertical_guard_mm=vertical_guard,
            multi_horizontal_guard_mm=horizontal_guard,
        )

    def _new_state(self, path: Path) -> PhotoState:
        return PhotoState(path=str(path))

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="写真を選択",
            filetypes=[("対応画像", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.dng"), ("すべて", "*.*")],
        )
        self._append_paths(Path(path) for path in paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="写真フォルダを選択")
        if not folder:
            return
        self._append_paths(sorted(
            path for path in Path(folder).iterdir()
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ))

    def _append_paths(self, paths: Iterable[Path]) -> None:
        existing = {Path(state.path).resolve() for state in self.photos if Path(state.path).exists()}
        added = 0
        for path in paths:
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved in existing:
                continue
            self.photos.append(self._new_state(path))
            self.file_list.insert("end", path.name)
            existing.add(resolved); added += 1
        if added:
            self.select_photo(len(self.photos) - 1)
            self.status_var.set(f"{added}枚追加しました。合計 {len(self.photos)}枚")
        self._schedule_preview()

    def _selected_list_indices(self) -> list[int]:
        return [int(index) for index in self.file_list.curselection()]

    def _preview_layout_for_count(self, count: int) -> str:
        """
        複数選択時の自動レイアウト。
        プレビューとページ変換の両方で同じ並びを使用する。
        """
        if count <= 1:
            return self.layout_var.get()

        paper = PAPER_PRESETS.get(self.paper_var.get(), (100, 148))
        portrait_page = paper[1] >= paper[0]

        if count == 2:
            return "2枚（上下）" if portrait_page else "2枚（左右）"
        if count == 3:
            return "大1＋小2"
        return "4枚"

    def _preview_selection_indices(self) -> list[int]:
        """
        左側で複数選択されていれば、その選択順の写真をプレビューへ使う。
        単一選択または未選択時は、従来どおり現在ページを表示する。
        """
        selected = self._selected_list_indices()
        if len(selected) >= 2:
            layout_name = self._preview_layout_for_count(len(selected))
            capacity = LAYOUT_CAPACITY.get(layout_name, 1)
            return selected[:capacity]

        capacity = LAYOUT_CAPACITY.get(self.layout_var.get(), 1)
        start = self.current_page_start()
        return list(range(start, min(len(self.photos), start + capacity)))

    def _selection_groups(self, indices: list[int], group_size: int = 4) -> list[list[int]]:
        """選択画像をページ単位へ分割する。"""
        clean = [
            index for index in indices
            if 0 <= index < len(self.photos)
        ]
        return [
            clean[position:position + group_size]
            for position in range(0, len(clean), group_size)
            if clean[position:position + group_size]
        ]

    def _selected_conversion_tasks(self, all_selected: bool) -> list[ConversionTask]:
        """
        複数選択中の画像を、プレビューと同じ規則で変換タスクへする。

        現在ページ:
            現在プレビューに表示中の最大4枚を1ページへ保存。
        すべてのページ:
            選択画像を最大4枚ずつに分け、全選択画像を保存。
        """
        selected = self._selected_list_indices()
        if len(selected) < 2:
            return []

        groups = (
            self._selection_groups(selected, 4)
            if all_selected
            else [self._preview_selection_indices()]
        )

        tasks: list[ConversionTask] = []
        for group in groups:
            if not group:
                continue
            tasks.append(
                ConversionTask(
                    start_index=0,
                    explicit_indices=list(group),
                    layout_name=self._preview_layout_for_count(len(group)),
                    gutter_override=0,
                    page_background=(242, 239, 232),
                    selected_export=True,
                )
            )
        return tasks

    def _normal_conversion_tasks(self, starts: list[int]) -> list[ConversionTask]:
        return [
            ConversionTask(start_index=start)
            for start in starts
        ]

    def select_photo(self, index: int, preserve_selection: bool = False) -> None:
        if not self.photos:
            self.selected_index = None
            return

        index = max(0, min(index, len(self.photos) - 1))
        self.selected_index = index

        if not preserve_selection:
            self.file_list.selection_clear(0, "end")
        self.file_list.selection_set(index)
        self.file_list.activate(index)
        self.file_list.see(index)

        self._load_state_to_controls(self.photos[index])
        self._schedule_preview()

    def _list_selection_changed(self, _event=None) -> None:
        selection = self._selected_list_indices()
        if not selection:
            return

        active_index = int(self.file_list.index("active"))
        if active_index not in selection:
            active_index = selection[-1]

        active_index = max(0, min(active_index, len(self.photos) - 1))
        self.selected_index = active_index
        self._load_state_to_controls(self.photos[active_index])
        self._schedule_preview()

    def _load_state_to_controls(self, state: PhotoState) -> None:
        self._syncing = True
        self.frame_var.set(state.frame_name)
        self.crop_var.set(state.crop_mode)
        self.filter_var.set(state.filter_name)
        line_label = next((label for label, value in CAPTION_LINE_PRESETS.items() if value == state.caption_lines), "2行（標準）")
        self.caption_lines_var.set(line_label)
        self.add_date_var.set(state.add_date)
        self.texture_var.set(state.paper_texture)
        self.zoom_var.set(state.zoom)
        self.pan_x_var.set(state.pan_x)
        self.pan_y_var.set(state.pan_y)
        self.brightness_var.set(state.brightness)
        self.contrast_var.set(state.contrast)
        self.saturation_var.set(state.saturation)
        self.warmth_var.set(state.warmth)
        self.grain_var.set(state.grain)
        self.vignette_var.set(state.vignette)
        self.vignette_extent_var.set(
            getattr(state, "vignette_extent", 45)
        )
        self.vignette_softness_var.set(
            getattr(state, "vignette_softness", 65)
        )
        self.fade_var.set(state.fade)
        self.monochrome_var.set(state.monochrome)
        self.caption_text.delete("1.0", "end")
        self.caption_text.insert("1.0", state.caption)
        self.caption_text.edit_modified(False)
        self.caption_text.configure(height=min(state.caption_lines, 6))
        self._syncing = False
        self._update_vignette_indicator()

    def remove_selected(self) -> None:
        indices = list(self.file_list.curselection())
        if not indices and self.selected_index is not None:
            indices = [self.selected_index]
        for index in reversed(indices):
            del self.photos[index]
            self.file_list.delete(index)
        if self.photos:
            self.select_photo(min(indices[0] if indices else 0, len(self.photos) - 1))
        else:
            self.selected_index = None
            self.preview_canvas.delete("all")
        self._schedule_preview()

    def clear_files(self) -> None:
        self.photos.clear(); self.file_list.delete(0, "end"); self.selected_index = None
        self.preview_canvas.delete("all"); self.status_var.set("写真を追加してください。")

    def duplicate_selected(self) -> None:
        if self.selected_index is None:
            return
        data = asdict(self.photos[self.selected_index])
        self.photos.insert(self.selected_index + 1, PhotoState(**data))
        self.file_list.insert(self.selected_index + 1, Path(data["path"]).name + "（複製）")
        self.select_photo(self.selected_index + 1)

    def move_up(self) -> None:
        if self.selected_index is None or self.selected_index <= 0:
            return
        i = self.selected_index
        self.photos[i - 1], self.photos[i] = self.photos[i], self.photos[i - 1]
        self._refresh_file_list(); self.select_photo(i - 1)

    def move_down(self) -> None:
        if self.selected_index is None or self.selected_index >= len(self.photos) - 1:
            return
        i = self.selected_index
        self.photos[i + 1], self.photos[i] = self.photos[i], self.photos[i + 1]
        self._refresh_file_list(); self.select_photo(i + 1)

    def _refresh_file_list(self) -> None:
        self.file_list.delete(0, "end")
        for state in self.photos:
            self.file_list.insert("end", Path(state.path).name)

    def current_page_start(self) -> int:
        capacity = LAYOUT_CAPACITY.get(self.layout_var.get(), 1)
        index = self.selected_index or 0
        return (index // capacity) * capacity

    def update_preview(self) -> None:
        self._preview_after_id = None
        self.preview_canvas.delete("all")
        if not self.photos:
            self.preview_canvas.create_text(
                max(1, self.preview_canvas.winfo_width()) // 2,
                max(1, self.preview_canvas.winfo_height()) // 2,
                text="写真を追加してください。",
                font=("Yu Gothic UI", 14),
            )
            return

        base_options = self._current_global_options()
        preview_dpi = min(150, base_options.print_dpi)
        selected = self._selected_list_indices()
        preview_indices = self._preview_selection_indices()

        options = GlobalOptions(**asdict(base_options))
        explicit_indices = None
        start_index = self.current_page_start()
        gutter_override = None

        if len(selected) >= 2:
            options.layout_name = self._preview_layout_for_count(len(preview_indices))
            # 複数画像のあいだに隙間を作らず、余白だけ柔らかな紙色にする。
            options.page_background = (242, 239, 232)
            explicit_indices = preview_indices
            start_index = 0
            gutter_override = 0

        result = render_page(
            self.photos,
            start_index,
            options,
            self.printer_profile,
            preview_dpi=preview_dpi,
            image_cache=self.image_cache,
            explicit_indices=explicit_indices,
            gutter_override=gutter_override,
        )
        self.preview_result = result

        canvas_width = max(200, self.preview_canvas.winfo_width() - 24)
        canvas_height = max(200, self.preview_canvas.winfo_height() - 24)
        displayed = ImageOps.contain(
            result.image,
            (canvas_width, canvas_height),
            Image.Resampling.LANCZOS,
        )
        self.preview_photo = ImageTk.PhotoImage(displayed)
        origin_x = (self.preview_canvas.winfo_width() - displayed.width) // 2
        origin_y = (self.preview_canvas.winfo_height() - displayed.height) // 2
        scale = displayed.width / result.image.width
        self.preview_display = (origin_x, origin_y, scale)
        self.preview_canvas.create_image(
            origin_x,
            origin_y,
            image=self.preview_photo,
            anchor="nw",
        )

        if self.show_guides_var.get():
            self._draw_guides(result, origin_x, origin_y, scale)

    def _draw_guides(self, result: PageRenderResult, ox: int, oy: int, scale: float) -> None:
        def box(rect, outline, dash=None, width=1):
            x0, y0, x1, y1 = rect
            self.preview_canvas.create_rectangle(
                ox + x0 * scale, oy + y0 * scale, ox + x1 * scale, oy + y1 * scale,
                outline=outline, dash=dash, width=width,
            )
        if result.safety_rect:
            box(result.safety_rect, "#d94841", dash=(6, 4), width=2)
        for meta in result.cards:
            box(meta.card_rect, "#555555", dash=(2, 3))
            selected_set = set(self._selected_list_indices())
            if meta.index == self.selected_index:
                box(meta.photo_rect, "#2775c5", width=3)
            elif meta.index in selected_set:
                box(meta.photo_rect, "#4a98e6", width=2)
            else:
                box(meta.photo_rect, "#2775c5", width=1)
            if meta.caption_rect[3] > meta.caption_rect[1]:
                box(meta.caption_rect, "#218c54", dash=(4, 3))
            if meta.date_rect[2] > meta.date_rect[0]:
                box(meta.date_rect, "#a26b00", dash=(3, 3))

    def _canvas_to_page(self, x: int, y: int) -> tuple[float, float]:
        ox, oy, scale = self.preview_display
        return ((x - ox) / max(scale, 1e-6), (y - oy) / max(scale, 1e-6))

    def _preview_press(self, event) -> None:
        if not self.preview_result:
            return
        px, py = self._canvas_to_page(event.x, event.y)
        keep_group = len(self._selected_list_indices()) >= 2
        for meta in self.preview_result.cards:
            x0, y0, x1, y1 = meta.card_rect
            if x0 <= px <= x1 and y0 <= py <= y1:
                self.select_photo(meta.index, preserve_selection=keep_group)
                state = self.photos[meta.index]
                self.drag_origin = (event.x, event.y, state.pan_x, state.pan_y)
                return

    def _preview_drag(self, event) -> None:
        if self.drag_origin is None or self.selected_index is None or not self.preview_result:
            return
        meta = next((m for m in self.preview_result.cards if m.index == self.selected_index), None)
        if not meta:
            return
        ox, oy, scale = self.preview_display
        width = max(1, (meta.photo_rect[2] - meta.photo_rect[0]) * scale)
        height = max(1, (meta.photo_rect[3] - meta.photo_rect[1]) * scale)
        start_x, start_y, pan_x, pan_y = self.drag_origin
        state = self.photos[self.selected_index]
        state.pan_x = max(-1.5, min(1.5, pan_x + (event.x - start_x) / width))
        state.pan_y = max(-1.5, min(1.5, pan_y + (event.y - start_y) / height))
        self._syncing = True
        self.pan_x_var.set(state.pan_x)
        self.pan_y_var.set(state.pan_y)
        self._syncing = False
        self._schedule_preview()

    def _preview_wheel(self, event):
        if self.selected_index is None:
            return None
        if getattr(event, "num", None) == 4:
            direction = 1
        elif getattr(event, "num", None) == 5:
            direction = -1
        else:
            direction = 1 if int(getattr(event, "delta", 0)) > 0 else -1
        state = self.photos[self.selected_index]
        state.zoom = max(0.5, min(3.0, state.zoom + direction * 0.05))
        self._syncing = True; self.zoom_var.set(state.zoom); self._syncing = False
        self._schedule_preview()
        return "break"

    def rotate_selected(self, amount: int) -> None:
        if self.selected_index is None:
            return
        state = self.photos[self.selected_index]
        state.rotation = (state.rotation + amount) % 360
        self._schedule_preview()

    def reset_transform(self) -> None:
        """選択写真の位置・拡大率・回転をデフォルトへ戻す。"""
        if self.selected_index is None:
            return
        state = self.photos[self.selected_index]
        state.zoom = 1.0
        state.pan_x = 0.0
        state.pan_y = 0.0
        state.rotation = 0
        self._load_state_to_controls(state)
        self._schedule_preview()

    def reset_photo_adjustments(self) -> None:
        """選択写真の写真加工だけをデフォルトへ戻す。"""
        if self.selected_index is None:
            return

        state = self.photos[self.selected_index]
        state.filter_name = "なし"
        state.brightness = 1.0
        state.contrast = 1.0
        state.saturation = 1.0
        state.warmth = 0
        state.grain = 0
        state.vignette = 0
        state.vignette_extent = 45
        state.vignette_softness = 65
        state.fade = 0
        state.monochrome = False

        self._load_state_to_controls(state)
        self._schedule_preview()

    def reset_position_and_adjustments(self) -> None:
        """位置と写真加工をまとめてデフォルトへ戻す。"""
        if self.selected_index is None:
            return
        self.reset_transform()
        self.reset_photo_adjustments()

    def _update_vignette_indicator(self) -> None:
        """
        ケラレ量・範囲・ぼかしを小さな視覚表示へ反映する。
        保存画像には含まれないUI専用インジケーター。
        """
        canvas = getattr(self, "vignette_indicator", None)
        if canvas is None:
            return

        width = max(140, canvas.winfo_width())
        height = max(70, canvas.winfo_height())
        if width <= 1 or height <= 1:
            width, height = 286, 92

        amount = int(self.vignette_var.get())
        extent = int(self.vignette_extent_var.get())
        softness = int(self.vignette_softness_var.get())

        preview = Image.new("RGB", (width, height), (164, 184, 196))
        # 中央の簡易被写体で、暗部の広がりを目視しやすくする。
        draw = ImageDraw.Draw(preview)
        draw.rectangle(
            (width * 0.18, height * 0.22, width * 0.82, height * 0.78),
            fill=(205, 191, 161),
        )
        draw.ellipse(
            (width * 0.42, height * 0.30, width * 0.58, height * 0.70),
            fill=(224, 214, 190),
        )

        if amount > 0:
            mask = build_vignette_mask(
                preview.size,
                amount,
                extent,
                softness,
            )
            dark = Image.new("RGB", preview.size, (8, 8, 8))
            preview = Image.composite(dark, preview, mask)

        self._vignette_indicator_photo = ImageTk.PhotoImage(preview)
        canvas.delete("all")
        canvas.create_image(
            width // 2,
            height // 2,
            image=self._vignette_indicator_photo,
            anchor="center",
        )
        canvas.create_text(
            7,
            7,
            anchor="nw",
            text=(
                f"量 {amount}%  /  範囲 {extent}%  /  "
                f"ぼかし {softness}%"
            ),
            fill="white" if amount >= 45 else "#222222",
            font=("Yu Gothic UI", 8, "bold"),
        )

    def select_output_dir(self) -> None:
        folder = filedialog.askdirectory(title="保存先を選択", initialdir=self.output_dir.get())
        if folder:
            self.output_dir.set(folder)

    def _page_count(self) -> int:
        capacity = LAYOUT_CAPACITY.get(self.layout_var.get(), 1)
        return max(1, math.ceil(len(self.photos) / capacity)) if self.photos else 0

    def convert_current_page(self) -> None:
        if not self.photos:
            messagebox.showinfo(APP_NAME, "写真を追加してください。")
            return

        # 複数選択中は、画面に表示されている組み合わせをそのまま1ページへ保存する。
        tasks = self._selected_conversion_tasks(all_selected=False)
        if not tasks:
            tasks = self._normal_conversion_tasks([self.current_page_start()])

        self._start_conversion(tasks)

    def convert_all_pages(self) -> None:
        if not self.photos:
            messagebox.showinfo(APP_NAME, "写真を追加してください。")
            return

        # 複数選択中は、選択画像だけを最大4枚ずつまとめて全ページ保存する。
        tasks = self._selected_conversion_tasks(all_selected=True)
        if not tasks:
            capacity = LAYOUT_CAPACITY.get(self.layout_var.get(), 1)
            tasks = self._normal_conversion_tasks(
                list(range(0, len(self.photos), capacity))
            )

        self._start_conversion(tasks)

    def _start_conversion(self, tasks: list[ConversionTask]) -> None:
        output = Path(self.output_dir.get()).expanduser()
        options = self._current_global_options()

        # UI操作で選択状態が変わっても処理中の内容が変化しないよう、
        # 変換タスクと写真設定を開始時点で複製する。
        frozen_tasks = [
            ConversionTask(
                start_index=task.start_index,
                explicit_indices=(
                    list(task.explicit_indices)
                    if task.explicit_indices is not None
                    else None
                ),
                layout_name=task.layout_name,
                gutter_override=task.gutter_override,
                page_background=task.page_background,
                selected_export=task.selected_export,
            )
            for task in tasks
        ]
        frozen_photos = [
            PhotoState(**asdict(state))
            for state in self.photos
        ]
        frozen_profile = PrinterProfile(**asdict(self.printer_profile))

        self.progress.configure(maximum=len(frozen_tasks), value=0)

        selected_mode = any(task.selected_export for task in frozen_tasks)
        if selected_mode:
            selected_count = sum(
                len(task.explicit_indices or [])
                for task in frozen_tasks
            )
            self.status_var.set(
                f"選択した{selected_count}枚を"
                f"{len(frozen_tasks)}ページへ変換中…"
            )
        else:
            self.status_var.set(f"{len(frozen_tasks)}ページを変換中…")

        threading.Thread(
            target=self._conversion_worker,
            args=(
                frozen_tasks,
                output,
                options,
                frozen_photos,
                frozen_profile,
            ),
            daemon=True,
        ).start()

    def _conversion_worker(
        self,
        tasks: list[ConversionTask],
        output: Path,
        base_options: GlobalOptions,
        photos: list[PhotoState],
        printer_profile: PrinterProfile,
    ) -> None:
        succeeded = 0
        errors: list[str] = []
        extension = ".png" if base_options.save_format == "PNG" else ".jpg"

        for number, task in enumerate(tasks, start=1):
            try:
                options = GlobalOptions(**asdict(base_options))
                if task.layout_name:
                    options.layout_name = task.layout_name
                if task.page_background is not None:
                    options.page_background = task.page_background

                result = render_page(
                    photos,
                    task.start_index,
                    options,
                    printer_profile,
                    preview_dpi=None,
                    image_cache=self.image_cache,
                    explicit_indices=task.explicit_indices,
                    gutter_override=task.gutter_override,
                )

                if task.selected_export:
                    stem = f"ZCS_Polaroid_selected_{number:03d}"
                else:
                    capacity = LAYOUT_CAPACITY.get(options.layout_name, 1)
                    page_number = task.start_index // capacity + 1
                    stem = f"ZCS_Polaroid_page_{page_number:03d}"

                path = output / f"{stem}{extension}"
                counter = 2
                while path.exists():
                    path = output / f"{stem}_{counter}{extension}"
                    counter += 1

                save_image(result.image, path, options)
                succeeded += 1

            except Exception as exc:
                errors.append(f"ページ{number}: {exc}")

            self.after(
                0,
                lambda value=number: self.progress.configure(value=value),
            )

        self.after(
            0,
            lambda: self._conversion_finished(succeeded, errors, output),
        )

    def _conversion_finished(self, succeeded: int, errors: list[str], output: Path) -> None:
        self.status_var.set(f"完了：{succeeded}ページ / エラー {len(errors)}件")
        if errors:
            messagebox.showwarning(APP_NAME, f"{succeeded}ページ保存しました。\n\n" + "\n".join(errors[:8]))
        else:
            messagebox.showinfo(APP_NAME, f"{succeeded}ページ保存しました。\n\n{output}")

    def save_project(self) -> None:
        path = filedialog.asksaveasfilename(
            title="プロジェクトを保存", defaultextension=PROJECT_EXTENSION,
            filetypes=[("ZCS Polaroid Project", f"*{PROJECT_EXTENSION}")],
            initialfile=(self.project_path.name if self.project_path else "新しい作品.zcsp"),
        )
        if not path:
            return
        payload = {
            "app": APP_NAME, "version": APP_VERSION,
            "global": {
                "layout": self.layout_var.get(), "paper": self.paper_var.get(),
                "dpi": self.dpi_var.get(), "date_inset": self.date_inset_var.get(),
                "multi_guard": self.multi_guard_var.get(),
                "output_width": self.output_width_var.get(), "format": self.format_var.get(),
                "quality": self.quality_var.get(), "apply_profile": self.apply_profile_var.get(),
                "output_dir": self.output_dir.get(),
            },
            "printer_profile": asdict(self.printer_profile),
            "photos": [asdict(state) for state in self.photos],
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.project_path = Path(path)
        self.status_var.set(f"プロジェクトを保存しました：{self.project_path.name}")

    def load_project(self) -> None:
        path = filedialog.askopenfilename(
            title="プロジェクトを開く", filetypes=[("ZCS Polaroid Project", f"*{PROJECT_EXTENSION}")]
        )
        if not path:
            return
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            global_data = payload.get("global", {})
            self.layout_var.set(global_data.get("layout", "1枚"))
            self.paper_var.set(global_data.get("paper", "はがき 縦（100×148mm）"))
            self.dpi_var.set(global_data.get("dpi", "300 dpi（印刷推奨）"))
            self.date_inset_var.set(global_data.get("date_inset", "安全 12mm（推奨）"))
            self.multi_guard_var.set(
                global_data.get(
                    "multi_guard",
                    "標準 上下4mm・左右2mm（推奨）",
                )
            )
            self.output_width_var.set(global_data.get("output_width", "高画質 2048px"))
            self.format_var.set(global_data.get("format", "JPEG"))
            self.quality_var.set(global_data.get("quality", 94))
            self.apply_profile_var.set(global_data.get("apply_profile", True))
            self.output_dir.set(global_data.get("output_dir", str(Path.home() / "Pictures" / APP_NAME)))
            profile = payload.get("printer_profile", {})
            self.printer_profile = PrinterProfile(**{
                key: profile.get(key, getattr(PrinterProfile(), key)) for key in asdict(PrinterProfile())
            })
            valid_photo_fields = {
                field.name for field in fields(PhotoState)
            }
            self.photos = [
                PhotoState(
                    **{
                        key: value
                        for key, value in data.items()
                        if key in valid_photo_fields
                    }
                )
                for data in payload.get("photos", [])
            ]
            self._refresh_file_list()
            self.project_path = Path(path)
            if self.photos:
                self.select_photo(0)
            missing = [state.path for state in self.photos if not Path(state.path).exists()]
            if missing:
                messagebox.showwarning(APP_NAME, f"見つからない写真が{len(missing)}件あります。\nプレビューでは代替表示になります。")
            self._schedule_preview()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"プロジェクトを開けませんでした。\n{exc}")

    def _preset_names(self) -> list[str]:
        return sorted(self.store.data.get("presets", {}).keys())

    def save_user_preset(self) -> None:
        if self.selected_index is None:
            messagebox.showinfo(APP_NAME, "写真を選択してください。")
            return
        name = simpledialog.askstring(APP_NAME, "プリセット名を入力してください。")
        if not name:
            return
        state = asdict(self.photos[self.selected_index]); state.pop("path", None); state.pop("caption", None)
        self.store.data.setdefault("presets", {})[name] = {
            "photo": state,
            "global": {
                "layout": self.layout_var.get(), "paper": self.paper_var.get(),
                "dpi": self.dpi_var.get(), "date_inset": self.date_inset_var.get(),
            },
        }
        self.store.save(); self.preset_combo.configure(values=self._preset_names()); self.preset_var.set(name)

    def load_user_preset(self) -> None:
        name = self.preset_var.get()
        preset = self.store.data.get("presets", {}).get(name)
        if not preset or self.selected_index is None:
            return
        state = self.photos[self.selected_index]
        for key, value in preset.get("photo", {}).items():
            if hasattr(state, key):
                setattr(state, key, value)
        global_data = preset.get("global", {})
        self.layout_var.set(global_data.get("layout", self.layout_var.get()))
        self.paper_var.set(global_data.get("paper", self.paper_var.get()))
        self.dpi_var.set(global_data.get("dpi", self.dpi_var.get()))
        self.date_inset_var.set(global_data.get("date_inset", self.date_inset_var.get()))
        self.multi_guard_var.set(
            global_data.get("multi_guard", self.multi_guard_var.get())
        )
        self._load_state_to_controls(state); self._schedule_preview()

    def delete_user_preset(self) -> None:
        name = self.preset_var.get()
        if not name:
            return
        self.store.data.get("presets", {}).pop(name, None)
        self.store.save(); self.preset_var.set(""); self.preset_combo.configure(values=self._preset_names())

    def show_diagnostics(self) -> None:
        if not self.photos:
            messagebox.showinfo(APP_NAME, "写真を追加してください。")
            return
        options = self._current_global_options()
        paper = PAPER_PRESETS.get(options.paper_name)
        lines = ["印刷診断", ""]
        if paper:
            lines.append(f"用紙：{options.paper_name} / {options.print_dpi}dpi")
        capacity = LAYOUT_CAPACITY.get(options.layout_name, 1)
        lines.append(f"レイアウト：{options.layout_name}（1ページ最大{capacity}枚）")
        lines.append(f"プリンター補正：{'適用' if options.apply_printer_profile else '未適用'}")
        lines.append(
            "複数画像の外周保護："
            f"上下{options.multi_vertical_guard_mm:g}mm / "
            f"左右{options.multi_horizontal_guard_mm:g}mm"
        )
        lines.append("")

        result = render_page(
            self.photos, self.current_page_start(), options, self.printer_profile,
            preview_dpi=options.print_dpi, image_cache=self.image_cache,
        )
        for meta in result.cards:
            state = self.photos[meta.index]
            try:
                source = self.image_cache.get(str(state.file_path.resolve())) or open_source_image(state.file_path)
                sw, sh = source.size if state.rotation % 180 == 0 else (source.height, source.width)
                pw = (meta.photo_rect[2] - meta.photo_rect[0]) / options.print_dpi
                ph = (meta.photo_rect[3] - meta.photo_rect[1]) / options.print_dpi
                effective = min(sw / max(pw, 0.01), sh / max(ph, 0.01))
                quality = "良好" if effective >= 300 else ("注意" if effective >= 150 else "不足")
                crop = "見切れの可能性あり" if state.crop_mode in {"フレームに合わせてトリミング", "手動調整"} or state.zoom > 1.02 else "見切れにくい"
                lines += [
                    f"{meta.index + 1}. {state.file_path.name}",
                    f"   元画像：{sw}×{sh}px / 実効約{effective:.0f}dpi（{quality}）",
                    f"   配置：{crop} / 文字{state.caption_lines}行 / 日付{'あり' if state.add_date else 'なし'}",
                ]
            except Exception as exc:
                lines.append(f"{meta.index + 1}. {state.file_path.name}：診断不可（{exc}）")
        lines.append("")
        if options.date_inset_mm < 10:
            lines.append("警告：日付の安全余白が10mm未満です。")
        if any(value > 0 for value in [self.printer_profile.top_mm, self.printer_profile.right_mm, self.printer_profile.bottom_mm, self.printer_profile.left_mm]):
            lines.append("プリンター固有の見切れ補正値が設定されています。")
        messagebox.showinfo(APP_NAME, "\n".join(lines))

    def create_test_sheet(self) -> None:
        options = self._current_global_options()
        paper = PAPER_PRESETS.get(options.paper_name)
        if paper is None:
            messagebox.showinfo(APP_NAME, "テストシートには用紙サイズを選択してください。")
            return
        width = mm_to_pixels(paper[0], options.print_dpi); height = mm_to_pixels(paper[1], options.print_dpi)
        image = Image.new("RGB", (width, height), (255, 255, 255)); draw = ImageDraw.Draw(image)
        font = choose_font(max(16, round(min(width, height) * 0.025)))
        draw.text((mm_to_pixels(8, options.print_dpi), mm_to_pixels(5, options.print_dpi)), "ZCS Printer Test Sheet", fill=(0, 0, 0), font=font)
        for mm, tone in [(2, 40), (5, 80), (10, 120), (15, 165)]:
            inset = mm_to_pixels(mm, options.print_dpi)
            draw.rectangle((inset, inset, width - inset - 1, height - inset - 1), outline=(tone, tone, tone), width=max(1, options.print_dpi // 150))
            draw.text((inset + 4, inset + 4), f"{mm}mm", fill=(tone, tone, tone), font=choose_font(max(11, font.size // 2 if hasattr(font, 'size') else 12)))
        center_x, center_y = width // 2, height // 2
        draw.line((center_x, 0, center_x, height), fill=(150, 150, 150), width=1)
        draw.line((0, center_y, width, center_y), fill=(150, 150, 150), width=1)
        output = Path(self.output_dir.get()).expanduser(); output.mkdir(parents=True, exist_ok=True)
        path = output / "ZCS_Printer_Test_Sheet.png"
        image.save(path, "PNG", dpi=(options.print_dpi, options.print_dpi))
        messagebox.showinfo(APP_NAME, f"テストシートを保存しました。\n{path}\n\n印刷後、切れたmmを『プリンター補正を設定』へ入力してください。")

    def configure_printer_profile(self) -> None:
        dialog = tk.Toplevel(self); dialog.title("プリンター補正"); dialog.transient(self); dialog.grab_set()
        frame = ttk.Frame(dialog, padding=14); frame.pack(fill="both", expand=True)
        vars_ = {
            "top_mm": tk.DoubleVar(value=self.printer_profile.top_mm),
            "right_mm": tk.DoubleVar(value=self.printer_profile.right_mm),
            "bottom_mm": tk.DoubleVar(value=self.printer_profile.bottom_mm),
            "left_mm": tk.DoubleVar(value=self.printer_profile.left_mm),
        }
        ttk.Label(frame, text="テスト印刷で切れた量をmmで入力します。", wraplength=320).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        for row, (key, label) in enumerate([("top_mm", "上"), ("right_mm", "右"), ("bottom_mm", "下"), ("left_mm", "左")], start=1):
            ttk.Label(frame, text=f"{label}の見切れ").grid(row=row, column=0, sticky="w", pady=3)
            ttk.Spinbox(frame, from_=0, to=30, increment=0.5, width=8, textvariable=vars_[key]).grid(row=row, column=1, sticky="e")
        def save_profile():
            self.printer_profile = PrinterProfile(
                top_mm=max(0.0, vars_["top_mm"].get()), right_mm=max(0.0, vars_["right_mm"].get()),
                bottom_mm=max(0.0, vars_["bottom_mm"].get()), left_mm=max(0.0, vars_["left_mm"].get()),
            )
            self.store.data["printer_profile"] = asdict(self.printer_profile); self.store.save()
            dialog.destroy(); self._schedule_preview()
        ttk.Button(frame, text="保存", style="Primary.TButton", command=save_profile).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def open_output_dir(self) -> None:
        path = Path(self.output_dir.get()).expanduser(); path.mkdir(parents=True, exist_ok=True)
        self._open_path(path)

    def open_error_log(self) -> None:
        if not ERROR_LOG.exists():
            ERROR_LOG.write_text("現在、記録されたエラーはありません。", encoding="utf-8")
        self._open_path(ERROR_LOG)

    def _open_path(self, path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess; subprocess.run(["open", str(path)], check=False)
            else:
                import subprocess; subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"開けませんでした。\n{exc}")

    def show_tutorial(self) -> None:
        messagebox.showinfo(
            f"{APP_NAME}の使い方",
            "1. 写真を追加します。\n"
            "2. 写真枠をクリックし、写真ごとの文字・加工・フレームを設定します。\n"
            "3. 左側の写真一覧は複数選択できます。複数選択時は、まとめてプレビューへ並びます。\n"
            "4. 複数画像の外周保護は初期状態で『標準 上下4mm・左右2mm』です。\n"
            "5. 複数選択中に『現在のページを変換』を押すと、プレビューと同じ組み合わせで保存されます。\n"
            "6. 『すべてのページを変換』では、選択画像を最大4枚ずつに分けて保存します。\n"
            "7. 位置はドラッグまたは横位置・縦位置インジケーターで調整できます。\n"
            "8. ケラレ量・範囲・ぼかしは視覚インジケーターで確認できます。\n"
            "4. レイアウトと用紙を選び、印刷安全ガイドと印刷診断を確認します。\n"
            "5. 『すべてのページを変換』で保存します。\n\n"
            "作業途中は.zcspプロジェクトとして保存できます。"
        )

    def _show_tutorial_if_needed(self) -> None:
        if not self.store.data.get("tutorial_seen", False):
            self.show_tutorial(); self.store.data["tutorial_seen"] = True; self.store.save()

    def show_about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME} v{APP_VERSION}\nPrint Studio\n\n画像をポラロイド風に。\n"
            "写真編集、印刷診断、複数レイアウト、プロジェクト保存に対応。"
        )

    def _save_last_settings(self) -> None:
        self.store.data["last"] = {
            "output_dir": self.output_dir.get(), "layout_name": self.layout_var.get(),
            "paper_name": self.paper_var.get(), "dpi_label": self.dpi_var.get(),
            "date_inset_label": self.date_inset_var.get(),
            "multi_guard_label": self.multi_guard_var.get(),
            "output_width_label": self.output_width_var.get(),
            "format": self.format_var.get(), "quality": self.quality_var.get(),
            "apply_profile": self.apply_profile_var.get(), "show_guides": self.show_guides_var.get(),
        }
        self.store.data["printer_profile"] = asdict(self.printer_profile)
        self.store.save()

    def on_close(self) -> None:
        self._save_last_settings(); self.destroy()


def main() -> None:
    try:
        app = PolaroidApp(); app.mainloop()
    except Exception:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        ERROR_LOG.write_text(traceback.format_exc(), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
