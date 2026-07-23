from __future__ import annotations

import os
import re
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFont,
    ImageOps,
    ImageTk,
)

try:
    import rawpy  # DNG/RAWは任意対応
except Exception:
    rawpy = None


APP_NAME = "ZCS Polaroid Maker"
APP_VERSION = "1.8"

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".dng"
}

FRAME_PRESETS = {
    "クラシックホワイト": {
        "paper": (247, 245, 239),
        "text": (45, 45, 45),
        "texture": 0.035,
    },
    "クリーム": {
        "paper": (240, 229, 202),
        "text": (66, 53, 39),
        "texture": 0.045,
    },
    "ブラック": {
        "paper": (28, 28, 30),
        "text": (235, 235, 235),
        "texture": 0.020,
    },
    "ヴィンテージ": {
        "paper": (222, 207, 173),
        "text": (74, 56, 37),
        "texture": 0.070,
    },
}

OUTPUT_WIDTHS = {
    "元画像に合わせる": None,
    "SNS向け 1080px": 1080,
    "高画質 2048px": 2048,
    "印刷向け 3000px": 3000,
}

# 用紙寸法はミリメートル。Noneは従来どおりポラロイド画像だけを保存する。
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

# 重要な文字をプリンターの印刷不可領域・フチなし拡大から守る。
DATE_INSET_PRESETS = {
    "標準 10mm": 10.0,
    "安全 12mm（推奨）": 12.0,
    "広め 15mm": 15.0,
}

CAPTION_LINE_PRESETS = {
    "1行": 1,
    "2行（標準）": 2,
    "3行": 3,
    "4行": 4,
    "5行": 5,
    "6行": 6,
    "7行": 7,
    "8行": 8,
}


@dataclass
class RenderOptions:
    frame_name: str
    crop_mode: str
    output_width: Optional[int]
    caption: str
    caption_lines: int
    add_date: bool
    paper_texture: bool
    save_format: str
    jpeg_quality: int

    # v1.8: ZCS名称へ完全統一＋既定保存先更新
    paper_name: str
    print_dpi: int
    date_inset_mm: float
    page_background: tuple[int, int, int] = (255, 255, 255)


def open_source_image(path: Path) -> Image.Image:
    ext = path.suffix.lower()

    if ext == ".dng":
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
    """
    EXIF撮影日を優先し、取得できない場合はファイル更新日を使う。
    EXIFの末尾にタイムゾーン等が付いていても年月日を取り出す。
    """
    try:
        exif = image.getexif()
        for tag_id in (36867, 36868, 306):
            value = exif.get(tag_id)
            if not value:
                continue

            raw_value = str(value).replace("\x00", "").strip()
            match = re.match(
                r"^(\d{4})[:\-/](\d{2})[:\-/](\d{2})",
                raw_value,
            )
            if match:
                year, month, day = match.groups()
                return f"{year}.{month}.{day}"
    except Exception:
        pass

    try:
        return datetime.fromtimestamp(
            path.stat().st_mtime
        ).strftime("%Y.%m.%d")
    except Exception:
        # 空文字にせず、日付取得不能が分かる表示にする。
        return "日付不明"


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


def add_paper_texture(image: Image.Image, strength: float) -> Image.Image:
    if strength <= 0:
        return image

    noise = Image.effect_noise(image.size, 22).convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(0.65)
    alpha = max(6, min(40, int(255 * strength)))

    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    overlay.putalpha(noise.point(lambda p: int((p / 255) * alpha)))

    return Image.alpha_composite(image.convert("RGBA"), overlay)


def fit_photo_to_box(
    image: Image.Image,
    size: tuple[int, int],
    crop_mode: str,
    paper_color: tuple[int, int, int],
) -> Image.Image:
    target_width, target_height = size

    if crop_mode in {
        "正方形にトリミング",
        "フレームに合わせてトリミング",
    }:
        return ImageOps.fit(
            image.convert("RGB"),
            (target_width, target_height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

    contained = ImageOps.contain(
        image.convert("RGB"),
        (target_width, target_height),
        Image.Resampling.LANCZOS,
    )
    background = Image.new(
        "RGB",
        (target_width, target_height),
        paper_color,
    )
    x = (target_width - contained.width) // 2
    y = (target_height - contained.height) // 2
    background.paste(contained, (x, y))

    return background


def wrap_caption_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> tuple[list[str], bool]:
    """
    明示的な改行を尊重しつつ、文字幅を実測して折り返す。
    指定行数を超える場合は最終行を省略記号で終える。
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized or max_lines <= 0:
        return [], False

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
        for character_index, character in enumerate(paragraph):
            candidate = current + character
            bbox = draw.textbbox((0, 0), candidate, font=font)
            candidate_width = bbox[2] - bbox[0]

            if candidate_width <= max_width or not current:
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
        ellipsis = "…"
        last = lines[-1].rstrip()

        while last:
            candidate = last + ellipsis
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width:
                lines[-1] = candidate
                break
            last = last[:-1]

        if not last:
            lines[-1] = ellipsis

    return lines, overflow


def prepare_caption_layout(
    draw: ImageDraw.ImageDraw,
    caption: str,
    requested_lines: int,
    max_width: int,
    max_height: int,
    initial_size: int,
) -> tuple[ImageFont.ImageFont, list[str], int, int]:
    """
    指定行数と利用可能な高さの両方へ収まるよう、必要なら文字を縮小する。
    """
    minimum_size = max(12, round(initial_size * 0.58))

    for font_size in range(initial_size, minimum_size - 1, -1):
        font = choose_font(font_size, handwritten=True)
        lines, _overflow = wrap_caption_text(
            draw,
            caption,
            font,
            max_width,
            requested_lines,
        )

        sample_bbox = draw.textbbox((0, 0), "あAg", font=font)
        line_height = max(1, sample_bbox[3] - sample_bbox[1])
        line_gap = max(3, font_size // 5)
        total_height = (
            len(lines) * line_height
            + max(0, len(lines) - 1) * line_gap
        )

        if total_height <= max_height:
            return font, lines, line_gap, line_height

    font = choose_font(minimum_size, handwritten=True)
    lines, _overflow = wrap_caption_text(
        draw,
        caption,
        font,
        max_width,
        requested_lines,
    )
    sample_bbox = draw.textbbox((0, 0), "あAg", font=font)
    line_height = max(1, sample_bbox[3] - sample_bbox[1])
    line_gap = max(3, minimum_size // 5)

    return font, lines, line_gap, line_height


def render_polaroid(
    path: Path,
    options: RenderOptions,
    target_size: Optional[tuple[int, int]] = None,
) -> Image.Image:
    """
    選択した入力行数ぶんの文字領域と、撮影日専用の最下段を確保する。
    文字と日付は、縦方向に重ならない別領域へ描画される。
    """
    source = open_source_image(path)
    preset = FRAME_PRESETS[options.frame_name]
    paper = preset["paper"]
    caption = options.caption.strip()
    date_text = get_photo_date(path, source) if options.add_date else ""

    if target_size is None:
        if options.output_width is None:
            frame_width = max(900, min(3200, max(source.size)))
        else:
            frame_width = options.output_width

        short_edge = frame_width
        side_margin = max(24, round(frame_width * 0.055))
        top_margin = side_margin
        photo_width = frame_width - side_margin * 2

        caption_size_estimate = max(16, round(short_edge * 0.034))
        date_size_estimate = max(13, round(short_edge * 0.020))
        caption_rows = options.caption_lines if caption else 0
        caption_pitch = caption_size_estimate + max(
            4,
            caption_size_estimate // 5,
        )
        safe_bottom = round(short_edge * 0.08)
        footer_top_gap = max(9, round(short_edge * 0.028))
        caption_date_gap = max(8, round(short_edge * 0.018))

        required_footer = (
            footer_top_gap
            + caption_rows * caption_pitch
            + (
                caption_date_gap + date_size_estimate
                if date_text
                else 0
            )
            + safe_bottom
        )
        bottom_margin = max(
            round(frame_width * 0.205),
            side_margin * 3,
            required_footer,
        )
        photo_height = photo_width
        frame_height = top_margin + photo_height + bottom_margin

    else:
        frame_width, frame_height = target_size
        short_edge = min(frame_width, frame_height)

        side_margin = max(12, round(short_edge * 0.055))
        top_margin = side_margin
        photo_width = max(1, frame_width - side_margin * 2)

        caption_size_estimate = max(16, round(short_edge * 0.034))
        date_size_estimate = max(13, round(short_edge * 0.020))
        caption_rows = options.caption_lines if caption else 0
        caption_pitch = caption_size_estimate + max(
            4,
            caption_size_estimate // 5,
        )
        safe_bottom = mm_to_pixels(
            options.date_inset_mm,
            options.print_dpi,
        )
        footer_top_gap = max(9, round(short_edge * 0.028))
        caption_date_gap = max(8, round(short_edge * 0.018))

        # 選択行数と日付行を先に予約し、必要なら写真領域を縮める。
        required_footer = (
            footer_top_gap
            + caption_rows * caption_pitch
            + (
                caption_date_gap + date_size_estimate
                if date_text
                else 0
            )
            + safe_bottom
        )
        minimum_bottom = max(
            round(frame_height * 0.21),
            side_margin * 3,
            required_footer,
        )
        available_photo_height = max(
            1,
            frame_height - top_margin - minimum_bottom,
        )

        if (
            frame_height >= frame_width
            and available_photo_height >= photo_width
        ):
            photo_height = photo_width
        else:
            photo_height = available_photo_height

        bottom_margin = max(
            1,
            frame_height - top_margin - photo_height,
        )

    polaroid = Image.new(
        "RGBA",
        (frame_width, frame_height),
        (*paper, 255),
    )

    photo = fit_photo_to_box(
        source,
        (photo_width, photo_height),
        options.crop_mode,
        paper,
    )
    polaroid.paste(photo, (side_margin, top_margin))

    border_draw = ImageDraw.Draw(polaroid)
    border_color = tuple(max(0, channel - 24) for channel in paper) + (120,)
    border_draw.rectangle(
        [
            side_margin - 1,
            top_margin - 1,
            side_margin + photo_width,
            top_margin + photo_height,
        ],
        outline=border_color,
        width=max(1, short_edge // 1000),
    )

    if options.paper_texture:
        polaroid = add_paper_texture(
            polaroid,
            preset["texture"],
        )

    draw = ImageDraw.Draw(polaroid)
    text_color = preset["text"] + (255,)

    caption_size = max(16, round(short_edge * 0.034))
    date_size = max(13, round(short_edge * 0.020))
    date_font = choose_font(date_size)

    footer_top = (
        top_margin
        + photo_height
        + max(9, round(short_edge * 0.028))
    )
    caption_date_gap = max(8, round(short_edge * 0.018))

    # 日付の描画位置を先に確定し、その上までを文字専用領域とする。
    date_top: Optional[int] = None
    date_draw_data: Optional[tuple[int, int, str, ImageFont.ImageFont]] = None

    if date_text:
        if target_size is not None:
            safe_inset = mm_to_pixels(
                options.date_inset_mm,
                options.print_dpi,
            )
        else:
            safe_inset = round(short_edge * 0.08)

        safe_right = max(side_margin, safe_inset)
        safe_bottom = max(side_margin, safe_inset)

        date_bbox = draw.textbbox(
            (0, 0),
            date_text,
            font=date_font,
        )
        right_edge = frame_width - safe_right
        bottom_edge = frame_height - safe_bottom
        date_x = right_edge - date_bbox[2]
        date_y = bottom_edge - date_bbox[3]
        date_top = date_y + date_bbox[1]

        date_draw_data = (
            date_x,
            date_y,
            date_text,
            date_font,
        )

    if caption:
        caption_area_bottom = (
            date_top - caption_date_gap
            if date_top is not None
            else frame_height - max(
                side_margin,
                (
                    mm_to_pixels(
                        options.date_inset_mm,
                        options.print_dpi,
                    )
                    if target_size is not None
                    else round(short_edge * 0.08)
                ),
            )
        )
        caption_area_height = max(
            1,
            caption_area_bottom - footer_top,
        )
        caption_max_width = max(
            1,
            frame_width - side_margin * 2,
        )

        caption_font, lines, line_gap, line_height = prepare_caption_layout(
            draw=draw,
            caption=caption,
            requested_lines=options.caption_lines,
            max_width=caption_max_width,
            max_height=caption_area_height,
            initial_size=caption_size,
        )

        current_y = footer_top
        for line in lines:
            bbox = draw.textbbox(
                (0, 0),
                line,
                font=caption_font,
            )
            text_width = bbox[2] - bbox[0]
            x = (frame_width - text_width) // 2

            draw.text(
                (x, current_y - bbox[1]),
                line,
                font=caption_font,
                fill=text_color,
            )
            current_y += line_height + line_gap

    if date_draw_data is not None:
        date_x, date_y, date_value, resolved_date_font = date_draw_data
        draw.text(
            (date_x, date_y),
            date_value,
            font=resolved_date_font,
            fill=text_color,
        )

    return polaroid


def mm_to_pixels(mm: float, dpi: int) -> int:
    return max(1, round(mm / 25.4 * dpi))


def paper_pixel_size(options: RenderOptions) -> Optional[tuple[int, int]]:
    size_mm = PAPER_PRESETS.get(options.paper_name)
    if size_mm is None:
        return None

    width_mm, height_mm = size_mm
    return (
        mm_to_pixels(width_mm, options.print_dpi),
        mm_to_pixels(height_mm, options.print_dpi),
    )


def render_for_export(path: Path, options: RenderOptions) -> Image.Image:
    """
    用紙指定時は、選択した用紙の縦横寸法そのものをフレーム寸法にする。
    外側の余白や影は追加しないため、保存画像は用紙サイズにぴったり一致する。
    """
    page_size = paper_pixel_size(options)

    if page_size is None:
        return render_polaroid(path, options)

    return render_polaroid(
        path,
        options,
        target_size=page_size,
    )


def save_rendered(
    image: Image.Image,
    output_path: Path,
    options: RenderOptions,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dpi = (options.print_dpi, options.print_dpi)

    if options.save_format == "PNG":
        image.save(
            output_path,
            "PNG",
            optimize=True,
            dpi=dpi,
        )
        return

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, options.page_background)
        background.paste(image, mask=image.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")

    image.save(
        output_path,
        "JPEG",
        quality=options.jpeg_quality,
        optimize=True,
        progressive=True,
        dpi=dpi,
    )


class PolaroidApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("1320x840")
        self.minsize(1060, 720)

        self.files: list[Path] = []
        self.preview_photo: Optional[ImageTk.PhotoImage] = None
        self.output_dir = tk.StringVar(
            value=str(Path.home() / "Pictures" / "ZCS Polaroid Maker")
        )

        self.frame_var = tk.StringVar(value="クラシックホワイト")
        self.crop_var = tk.StringVar(value="フレームに合わせてトリミング")
        self.width_var = tk.StringVar(value="高画質 2048px")
        self.caption_lines_var = tk.StringVar(value="2行（標準）")
        self.add_date_var = tk.BooleanVar(value=True)
        self.texture_var = tk.BooleanVar(value=True)
        self.format_var = tk.StringVar(value="JPEG")
        self.quality_var = tk.IntVar(value=94)

        # v1.2: はがき縦を標準にし、用紙寸法ぴったりで出力
        self.paper_var = tk.StringVar(value="はがき 縦（100×148mm）")
        self.dpi_var = tk.StringVar(value="300 dpi（印刷推奨）")
        self.date_inset_var = tk.StringVar(value="安全 12mm（推奨）")

        self.status_var = tk.StringVar(value="写真を追加してください。")

        self._build_style()
        self._build_ui()
        self._bind_setting_updates()
        self._update_paper_control_state()
        self._update_date_control_state()
        self._update_caption_input_height()

    def _build_style(self) -> None:
        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Title.TLabel", font=("Yu Gothic UI", 18, "bold"))
        style.configure("Section.TLabel", font=("Yu Gothic UI", 11, "bold"))
        style.configure(
            "Primary.TButton",
            font=("Yu Gothic UI", 10, "bold"),
            padding=(12, 8),
        )
        style.configure("TButton", padding=(8, 6))
        style.configure("TLabel", font=("Yu Gothic UI", 9))
        style.configure("TCheckbutton", font=("Yu Gothic UI", 9))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.columnconfigure(2, weight=0)
        root.rowconfigure(1, weight=1)

        header = ttk.Frame(root)
        header.grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(0, 10),
        )

        ttk.Label(
            header,
            text="ZCS Polaroid Maker",
            style="Title.TLabel",
        ).pack(side="left")

        ttk.Label(
            header,
            text="画像をポラロイド風に。",
        ).pack(side="left", padx=14, pady=(7, 0))

        # 左：写真一覧
        left = ttk.LabelFrame(root, text="1. 写真", padding=10)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 10))
        left.rowconfigure(2, weight=1)

        ttk.Button(
            left,
            text="写真を追加",
            command=self.add_files,
        ).grid(row=0, column=0, sticky="ew")

        ttk.Button(
            left,
            text="フォルダを追加",
            command=self.add_folder,
        ).grid(row=1, column=0, sticky="ew", pady=(6, 8))

        list_frame = ttk.Frame(left)
        list_frame.grid(row=2, column=0, sticky="nsew")

        self.file_list = tk.Listbox(
            list_frame,
            width=30,
            height=28,
            exportselection=False,
            selectmode=tk.EXTENDED,
            font=("Yu Gothic UI", 9),
        )
        scrollbar = ttk.Scrollbar(
            list_frame,
            orient="vertical",
            command=self.file_list.yview,
        )
        self.file_list.configure(yscrollcommand=scrollbar.set)

        self.file_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.file_list.bind(
            "<<ListboxSelect>>",
            lambda _event: self.update_preview(),
        )

        button_row = ttk.Frame(left)
        button_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        ttk.Button(
            button_row,
            text="選択を削除",
            command=self.remove_selected,
        ).pack(side="left", fill="x", expand=True)

        ttk.Button(
            button_row,
            text="全消去",
            command=self.clear_files,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # 中央：プレビュー
        center = ttk.LabelFrame(root, text="2. プレビュー", padding=10)
        center.grid(row=1, column=1, sticky="nsew", padx=(0, 10))
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(
            center,
            bg="#d9d9d9",
            highlightthickness=0,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        self.preview_canvas.bind(
            "<Configure>",
            lambda _event: self.update_preview(),
        )

        # 右：設定（縦スクロール対応）
        right_shell = ttk.LabelFrame(
            root,
            text="3. 仕上がり設定",
            padding=(0, 4, 0, 0),
        )
        right_shell.grid(row=1, column=2, sticky="nse")
        right_shell.rowconfigure(0, weight=1)
        right_shell.columnconfigure(0, weight=1)

        self.settings_canvas = tk.Canvas(
            right_shell,
            width=342,
            highlightthickness=0,
            borderwidth=0,
        )
        self.settings_canvas.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        settings_scrollbar = ttk.Scrollbar(
            right_shell,
            orient="vertical",
            command=self.settings_canvas.yview,
        )
        settings_scrollbar.grid(
            row=0,
            column=1,
            sticky="ns",
        )
        self.settings_canvas.configure(
            yscrollcommand=settings_scrollbar.set,
        )

        right = ttk.Frame(
            self.settings_canvas,
            padding=(12, 8, 12, 14),
        )
        right.columnconfigure(0, weight=1)

        self.settings_window_id = self.settings_canvas.create_window(
            (0, 0),
            window=right,
            anchor="nw",
        )
        right.bind(
            "<Configure>",
            self._update_settings_scrollregion,
        )
        self.settings_canvas.bind(
            "<Configure>",
            self._resize_settings_inner,
        )

        row = 0
        row = self._add_combo(
            right,
            row,
            "フレーム",
            self.frame_var,
            list(FRAME_PRESETS.keys()),
        )
        row = self._add_combo(
            right,
            row,
            "写真の収め方",
            self.crop_var,
            ["フレームに合わせてトリミング", "写真全体を収める"],
        )
        row = self._add_combo(
            right,
            row,
            "ポラロイド画像の基準解像度",
            self.width_var,
            list(OUTPUT_WIDTHS.keys()),
        )

        ttk.Label(right, text="下部に入れる文字").grid(
            row=row,
            column=0,
            sticky="w",
            pady=(10, 3),
        )
        row += 1

        caption_input_frame = ttk.Frame(right)
        caption_input_frame.grid(row=row, column=0, sticky="ew")
        caption_input_frame.columnconfigure(0, weight=1)

        self.caption_text = tk.Text(
            caption_input_frame,
            width=34,
            height=2,
            wrap="char",
            undo=True,
            font=("Yu Gothic UI", 9),
        )
        self.caption_text.grid(row=0, column=0, sticky="ew")

        caption_text_scrollbar = ttk.Scrollbar(
            caption_input_frame,
            orient="vertical",
            command=self.caption_text.yview,
        )
        caption_text_scrollbar.grid(row=0, column=1, sticky="ns")
        self.caption_text.configure(
            yscrollcommand=caption_text_scrollbar.set,
        )

        self.caption_text.bind(
            "<<Modified>>",
            self._caption_text_modified,
        )
        self.caption_text.edit_modified(False)
        row += 1

        ttk.Label(
            right,
            text="文字の入力行数",
        ).grid(row=row, column=0, sticky="w", pady=(6, 3))
        row += 1

        self.caption_lines_combo = ttk.Combobox(
            right,
            textvariable=self.caption_lines_var,
            values=list(CAPTION_LINE_PRESETS.keys()),
            state="readonly",
            width=32,
        )
        self.caption_lines_combo.grid(row=row, column=0, sticky="ew")
        row += 1

        ttk.Label(
            right,
            text="1～8行。改行可能で、指定行数を超えた文字は末尾を…で省略します。",
            wraplength=255,
        ).grid(row=row, column=0, sticky="w", pady=(4, 0))
        row += 1

        ttk.Checkbutton(
            right,
            text="撮影日を入れる",
            variable=self.add_date_var,
        ).grid(row=row, column=0, sticky="w", pady=(8, 0))
        row += 1

        ttk.Label(
            right,
            text="日付の印刷安全余白",
        ).grid(row=row, column=0, sticky="w", pady=(6, 3))
        row += 1

        self.date_inset_combo = ttk.Combobox(
            right,
            textvariable=self.date_inset_var,
            values=list(DATE_INSET_PRESETS.keys()),
            state="readonly",
            width=32,
        )
        self.date_inset_combo.grid(row=row, column=0, sticky="ew")
        row += 1

        ttk.Checkbutton(
            right,
            text="紙の質感を付ける",
            variable=self.texture_var,
        ).grid(row=row, column=0, sticky="w")
        row += 1

        ttk.Separator(right).grid(
            row=row,
            column=0,
            sticky="ew",
            pady=10,
        )
        row += 1

        ttk.Label(
            right,
            text="印刷用紙",
            style="Section.TLabel",
        ).grid(row=row, column=0, sticky="w")
        row += 1

        self.paper_combo = ttk.Combobox(
            right,
            textvariable=self.paper_var,
            values=list(PAPER_PRESETS.keys()),
            state="readonly",
            width=32,
        )
        self.paper_combo.grid(row=row, column=0, sticky="ew", pady=(4, 0))
        row += 1

        ttk.Label(right, text="印刷解像度").grid(
            row=row,
            column=0,
            sticky="w",
            pady=(8, 3),
        )
        row += 1

        self.dpi_combo = ttk.Combobox(
            right,
            textvariable=self.dpi_var,
            values=list(DPI_PRESETS.keys()),
            state="readonly",
            width=32,
        )
        self.dpi_combo.grid(row=row, column=0, sticky="ew")
        row += 1

        ttk.Label(
            right,
            text="入力行数ぶんの文字領域と、撮影日専用の最下段を確保します。",
            wraplength=255,
        ).grid(row=row, column=0, sticky="w", pady=(5, 0))
        row += 1

        ttk.Separator(right).grid(
            row=row,
            column=0,
            sticky="ew",
            pady=10,
        )
        row += 1

        row = self._add_combo(
            right,
            row,
            "保存形式",
            self.format_var,
            ["JPEG", "PNG"],
        )

        quality_frame = ttk.Frame(right)
        quality_frame.grid(row=row, column=0, sticky="ew", pady=(8, 0))

        ttk.Label(
            quality_frame,
            text="JPEG画質",
        ).pack(side="left")

        ttk.Spinbox(
            quality_frame,
            from_=70,
            to=100,
            width=6,
            textvariable=self.quality_var,
        ).pack(side="right")
        row += 1

        ttk.Label(
            right,
            text="保存先",
            style="Section.TLabel",
        ).grid(row=row, column=0, sticky="w", pady=(10, 0))
        row += 1

        ttk.Entry(
            right,
            textvariable=self.output_dir,
            width=34,
        ).grid(row=row, column=0, sticky="ew", pady=(4, 4))
        row += 1

        ttk.Button(
            right,
            text="保存先を選ぶ",
            command=self.select_output_dir,
        ).grid(row=row, column=0, sticky="ew")
        row += 1

        ttk.Button(
            right,
            text="選択中を変換",
            style="Primary.TButton",
            command=self.convert_selected,
        ).grid(row=row, column=0, sticky="ew", pady=(14, 6))
        row += 1

        ttk.Button(
            right,
            text="すべて変換",
            style="Primary.TButton",
            command=self.convert_all,
        ).grid(row=row, column=0, sticky="ew")
        row += 1

        self.progress = ttk.Progressbar(right, mode="determinate")
        self.progress.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(10, 14),
        )

        # 設定欄内のどこにマウスポインターがあっても、
        # ホイールで右パネル全体をスクロールできる。
        self._bind_settings_mousewheel_recursive(right_shell)

        footer = ttk.Frame(root)
        footer.grid(
            row=2,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(10, 0),
        )

        ttk.Label(
            footer,
            textvariable=self.status_var,
        ).pack(side="left")

        ttk.Button(
            footer,
            text="保存先を開く",
            command=self.open_output_dir,
        ).pack(side="right")

    def _update_settings_scrollregion(self, _event=None) -> None:
        """右設定パネルの内容全体をスクロール範囲へ反映する。"""
        self.settings_canvas.configure(
            scrollregion=self.settings_canvas.bbox("all"),
        )

    def _resize_settings_inner(self, event) -> None:
        """
        内側フレームの横幅をキャンバス表示幅へ合わせ、
        横方向にはみ出さないようにする。
        """
        canvas_width = max(1, int(event.width))
        self.settings_canvas.itemconfigure(
            self.settings_window_id,
            width=canvas_width,
        )

    def _bind_settings_mousewheel_recursive(self, widget) -> None:
        """右設定欄の全子ウィジェットへホイール操作を割り当てる。"""
        widget.bind(
            "<MouseWheel>",
            self._on_settings_mousewheel,
            add="+",
        )
        widget.bind(
            "<Button-4>",
            self._on_settings_mousewheel,
            add="+",
        )
        widget.bind(
            "<Button-5>",
            self._on_settings_mousewheel,
            add="+",
        )

        for child in widget.winfo_children():
            self._bind_settings_mousewheel_recursive(child)

    def _on_settings_mousewheel(self, event):
        """Windows・macOS・Linuxのホイールイベントを処理する。"""
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return None

            if abs(delta) >= 120:
                units = -int(delta / 120)
            else:
                units = -1 if delta > 0 else 1

        self.settings_canvas.yview_scroll(units, "units")
        return "break"

    def _add_combo(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        values: list[str],
    ) -> int:
        ttk.Label(parent, text=label).grid(
            row=row,
            column=0,
            sticky="w",
            pady=((8 if row else 0), 3),
        )
        row += 1

        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
            width=32,
        )
        combo.grid(row=row, column=0, sticky="ew")
        return row + 1

    def _bind_setting_updates(self) -> None:
        variables = [
            self.frame_var,
            self.crop_var,
            self.width_var,
            self.caption_lines_var,
            self.add_date_var,
            self.date_inset_var,
            self.texture_var,
            self.format_var,
            self.quality_var,
            self.paper_var,
            self.dpi_var,
        ]

        for variable in variables:
            variable.trace_add(
                "write",
                lambda *_args: self.after_idle(self._settings_changed),
            )

    def _settings_changed(self) -> None:
        self._update_paper_control_state()
        self._update_date_control_state()
        self._update_caption_input_height()
        self.update_preview()

    def _update_paper_control_state(self) -> None:
        has_paper = PAPER_PRESETS.get(self.paper_var.get()) is not None
        state = "readonly" if has_paper else "disabled"
        self.dpi_combo.configure(state=state)

    def _update_date_control_state(self) -> None:
        state = "readonly" if self.add_date_var.get() else "disabled"
        self.date_inset_combo.configure(state=state)

    def _update_caption_input_height(self) -> None:
        rows = CAPTION_LINE_PRESETS.get(
            self.caption_lines_var.get(),
            2,
        )
        # 7～8行指定でも右設定欄が過度に縦長にならないよう、
        # 入力欄自体は最大6行表示とし、内部スクロールで編集する。
        self.caption_text.configure(height=min(rows, 6))

    def _caption_text_modified(self, _event=None) -> None:
        if not self.caption_text.edit_modified():
            return

        self.caption_text.edit_modified(False)
        self.after_idle(self.update_preview)

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="写真を選択",
            filetypes=[
                (
                    "対応画像",
                    "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.dng",
                ),
                ("すべてのファイル", "*.*"),
            ],
        )
        self._append_paths(Path(path) for path in paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="写真フォルダを選択")
        if not folder:
            return

        paths = sorted(
            path
            for path in Path(folder).iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        self._append_paths(paths)

    def _append_paths(self, paths: Iterable[Path]) -> None:
        existing = {path.resolve() for path in self.files}
        added = 0

        for path in paths:
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path

            if (
                path.suffix.lower() not in SUPPORTED_EXTENSIONS
                or resolved in existing
            ):
                continue

            self.files.append(path)
            self.file_list.insert("end", path.name)
            existing.add(resolved)
            added += 1

        if added:
            last_index = len(self.files) - 1
            self.file_list.selection_clear(0, "end")
            self.file_list.selection_set(last_index)
            self.file_list.see(last_index)
            self.status_var.set(
                f"{added}枚追加しました。合計 {len(self.files)}枚"
            )
            self.update_preview()
        else:
            self.status_var.set(
                "追加できる新しい写真がありませんでした。"
            )

    def remove_selected(self) -> None:
        indices = list(self.file_list.curselection())

        for index in reversed(indices):
            del self.files[index]
            self.file_list.delete(index)

        if self.files:
            new_index = min(
                indices[0] if indices else 0,
                len(self.files) - 1,
            )
            self.file_list.selection_set(new_index)

        self.update_preview()

    def clear_files(self) -> None:
        self.files.clear()
        self.file_list.delete(0, "end")
        self.preview_canvas.delete("all")
        self.status_var.set("写真を追加してください。")

    def select_output_dir(self) -> None:
        folder = filedialog.askdirectory(
            title="保存先を選択",
            initialdir=self.output_dir.get(),
        )
        if folder:
            self.output_dir.set(folder)

    def _current_options(self) -> RenderOptions:
        return RenderOptions(
            frame_name=self.frame_var.get(),
            crop_mode=self.crop_var.get(),
            output_width=OUTPUT_WIDTHS[self.width_var.get()],
            caption=self.caption_text.get("1.0", "end-1c"),
            caption_lines=CAPTION_LINE_PRESETS[
                self.caption_lines_var.get()
            ],
            add_date=self.add_date_var.get(),
            paper_texture=self.texture_var.get(),
            save_format=self.format_var.get(),
            jpeg_quality=max(
                70,
                min(100, int(self.quality_var.get())),
            ),
            paper_name=self.paper_var.get(),
            print_dpi=DPI_PRESETS[self.dpi_var.get()],
            date_inset_mm=DATE_INSET_PRESETS[self.date_inset_var.get()],
        )

    def _selected_indices(self) -> list[int]:
        return list(self.file_list.curselection())

    def update_preview(self) -> None:
        if not self.files:
            return

        indices = self._selected_indices()
        index = indices[0] if indices else 0

        if index >= len(self.files):
            return

        try:
            image = render_for_export(
                self.files[index],
                self._current_options(),
            )

            canvas_width = max(
                200,
                self.preview_canvas.winfo_width() - 30,
            )
            canvas_height = max(
                200,
                self.preview_canvas.winfo_height() - 30,
            )

            preview = ImageOps.contain(
                image,
                (canvas_width, canvas_height),
                Image.Resampling.LANCZOS,
            )

            self.preview_photo = ImageTk.PhotoImage(preview)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(
                self.preview_canvas.winfo_width() // 2,
                self.preview_canvas.winfo_height() // 2,
                image=self.preview_photo,
                anchor="center",
            )

        except Exception as exc:
            self.preview_canvas.delete("all")
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width() // 2,
                self.preview_canvas.winfo_height() // 2,
                text=f"プレビューできません\n{exc}",
                justify="center",
                width=max(
                    250,
                    self.preview_canvas.winfo_width() - 50,
                ),
            )

    def convert_selected(self) -> None:
        indices = self._selected_indices()

        if not indices:
            messagebox.showinfo(
                APP_NAME,
                "変換する写真を選択してください。",
            )
            return

        self._start_conversion(
            [self.files[index] for index in indices]
        )

    def convert_all(self) -> None:
        if not self.files:
            messagebox.showinfo(APP_NAME, "写真を追加してください。")
            return

        self._start_conversion(list(self.files))

    def _start_conversion(self, paths: list[Path]) -> None:
        output_dir = Path(self.output_dir.get()).expanduser()
        options = self._current_options()

        self.progress.configure(maximum=len(paths), value=0)
        self.status_var.set(f"{len(paths)}枚を変換中…")

        worker = threading.Thread(
            target=self._conversion_worker,
            args=(paths, output_dir, options),
            daemon=True,
        )
        worker.start()

    def _conversion_worker(
        self,
        paths: list[Path],
        output_dir: Path,
        options: RenderOptions,
    ) -> None:
        succeeded = 0
        errors: list[str] = []

        extension = (
            ".png"
            if options.save_format == "PNG"
            else ".jpg"
        )

        for current, path in enumerate(paths, start=1):
            try:
                rendered = render_for_export(path, options)

                paper_suffix = ""
                if PAPER_PRESETS.get(options.paper_name) is not None:
                    safe_paper_name = (
                        options.paper_name
                        .split("（", 1)[0]
                        .replace(" ", "_")
                    )
                    paper_suffix = f"_{safe_paper_name}"

                output_path = output_dir / (
                    f"{path.stem}_polaroid{paper_suffix}{extension}"
                )

                counter = 2
                while output_path.exists():
                    output_path = output_dir / (
                        f"{path.stem}_polaroid"
                        f"{paper_suffix}_{counter}{extension}"
                    )
                    counter += 1

                save_rendered(rendered, output_path, options)
                succeeded += 1

            except Exception as exc:
                errors.append(f"{path.name}: {exc}")

            finally:
                self.after(
                    0,
                    lambda value=current: self.progress.configure(
                        value=value
                    ),
                )

        self.after(
            0,
            lambda: self._conversion_finished(
                succeeded,
                errors,
                output_dir,
            ),
        )

    def _conversion_finished(
        self,
        succeeded: int,
        errors: list[str],
        output_dir: Path,
    ) -> None:
        if errors:
            error_text = "\n".join(errors[:8])

            if len(errors) > 8:
                error_text += f"\nほか {len(errors) - 8}件"

            messagebox.showwarning(
                APP_NAME,
                f"{succeeded}枚を保存しました。\n\n"
                f"変換できなかった写真:\n{error_text}",
            )
        else:
            messagebox.showinfo(
                APP_NAME,
                f"{succeeded}枚を保存しました。\n\n{output_dir}",
            )

        self.status_var.set(
            f"完了：{succeeded}枚保存 / エラー {len(errors)}件"
        )

    def open_output_dir(self) -> None:
        path = Path(self.output_dir.get()).expanduser()
        path.mkdir(parents=True, exist_ok=True)

        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", str(path)], check=False)
            else:
                import subprocess
                subprocess.run(["xdg-open", str(path)], check=False)

        except Exception as exc:
            messagebox.showerror(
                APP_NAME,
                f"保存先を開けませんでした。\n{exc}",
            )


def main() -> None:
    try:
        app = PolaroidApp()
        app.mainloop()
    except Exception:
        log_path = Path.cwd() / "zcs_polaroid_maker_error.log"
        log_path.write_text(
            traceback.format_exc(),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
