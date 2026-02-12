import csv
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable, List, Optional, Tuple

import qrcode
from PIL import Image
from reportlab.lib.pagesizes import landscape
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas


@dataclass(frozen=True)
class LabelRow:
    cins: str
    carpet_name: str
    qr_text: str


_FONT_NAME: Optional[str] = None


def _try_register_ttf_font() -> Optional[str]:
    global _FONT_NAME
    if _FONT_NAME is not None:
        return _FONT_NAME

    candidates = [
        "arial.ttf",
        "arialuni.ttf",
        "segoeui.ttf",
        "calibri.ttf",
        "tahoma.ttf",
    ]
    fonts_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    for fn in candidates:
        path = os.path.join(fonts_dir, fn)
        if os.path.exists(path):
            name = os.path.splitext(fn)[0]
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                _FONT_NAME = name
                return _FONT_NAME
            except Exception:
                continue

    _FONT_NAME = None
    return None


def _normalize_header(s: str) -> str:
    return (s or "").strip().lower()


def _sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
    except csv.Error:
        return csv.excel


def read_labels_from_txt(path: str, encoding: str = "utf-8") -> List[LabelRow]:
    rows: List[LabelRow] = []
    with open(path, "r", encoding=encoding, errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                continue
            cins, rest = line.split(":", 1)
            cins = cins.strip()
            rest = rest.strip()
            carpet_name = rest.replace("-", " ")
            rows.append(LabelRow(cins=cins, carpet_name=carpet_name, qr_text=line))
    return rows


def read_labels_from_csv(path: str, encoding: str = "utf-8") -> List[LabelRow]:
    with open(path, "r", encoding=encoding, errors="replace", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = _sniff_dialect(sample)
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            return []

        header_map = {_normalize_header(h): h for h in reader.fieldnames}

        def get_field(d: dict, *names: str) -> Optional[str]:
            for n in names:
                key = header_map.get(_normalize_header(n))
                if key is not None:
                    v = d.get(key)
                    if v is not None and str(v).strip() != "":
                        return str(v).strip()
            return None

        rows: List[LabelRow] = []
        for d in reader:
            cins = get_field(d, "cins", "type")
            if not cins:
                continue

            carpet_name = get_field(d, "carpet_name", "carpet name", "name")
            carpet_name2 = get_field(d, "carpet_name2", "carpet_name_2", "slug")
            qr_text = get_field(d, "qr_code", "qr", "qr_text")

            if not carpet_name and carpet_name2:
                carpet_name = carpet_name2.replace("-", " ")
            if not carpet_name:
                carpet_name = ""

            if not qr_text:
                if carpet_name2:
                    qr_text = f"{cins}:{carpet_name2}"
                else:
                    qr_text = f"{cins}:{carpet_name.replace(' ', '-')}"

            rows.append(LabelRow(cins=cins, carpet_name=carpet_name, qr_text=qr_text))

    return rows


def read_labels(path: str, encoding: str = "utf-8") -> List[LabelRow]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".txt":
        return read_labels_from_txt(path, encoding=encoding)
    if ext == ".csv":
        return read_labels_from_csv(path, encoding=encoding)
    raise ValueError("Desteklenen dosya uzantıları: .txt, .csv")


def _make_qr_image(qr_text: str, box_size: int = 8, border: int = 1) -> Image.Image:
    return _make_qr_image_with_logo(qr_text=qr_text, box_size=box_size, border=border, logo_path=None)


def _make_qr_image_with_logo(
    *,
    qr_text: str,
    box_size: int = 8,
    border: int = 1,
    logo_path: Optional[str] = None,
    logo_scale: float = 0.22,
) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=border,
    )
    qr.add_data(qr_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    if hasattr(img, "convert"):
        img = img.convert("RGB")

    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image.open(logo_path)
            if hasattr(logo, "convert"):
                logo = logo.convert("RGBA")

            w, h = img.size
            target = int(min(w, h) * logo_scale)
            if target > 0:
                logo.thumbnail((target, target), Image.Resampling.LANCZOS)

            lw, lh = logo.size
            pad = max(2, int(target * 0.12))
            bg = Image.new("RGBA", (lw + 2 * pad, lh + 2 * pad), (255, 255, 255, 255))
            bg.paste(logo, (pad, pad), logo)

            x = (w - bg.size[0]) // 2
            y = (h - bg.size[1]) // 2
            img_rgba = img.convert("RGBA")
            img_rgba.paste(bg, (x, y), bg)
            img = img_rgba.convert("RGB")
        except Exception:
            pass
    return img


def _wrap_text(canvas: Canvas, text: str, x: float, y: float, max_width: float, line_height: float) -> float:
    words = (text or "").split()
    if not words:
        return y
    line = ""
    for w in words:
        candidate = (line + " " + w).strip()
        if canvas.stringWidth(candidate) <= max_width:
            line = candidate
        else:
            canvas.drawString(x, y, line)
            y -= line_height
            line = w
    if line:
        canvas.drawString(x, y, line)
        y -= line_height
    return y


def _turkish_upper(s: str) -> str:
    if not s:
        return ""
    s = s.replace("i", "İ").replace("ı", "I")
    return s.upper()


def generate_labels_pdf(
    labels: Iterable[LabelRow],
    output_pdf_path: str,
    width_mm: float = 80.0,
    height_mm: float = 50.0,
    qr_mm: float = 32.0,
    margin_mm: float = 4.0,
    logo_path: Optional[str] = None,
    logo_scale: float = 0.22,
) -> None:
    page_w = width_mm * mm
    page_h = height_mm * mm
    qr_size = qr_mm * mm
    margin = margin_mm * mm

    c = Canvas(output_pdf_path, pagesize=(page_w, page_h))
    font_name = _try_register_ttf_font() or "Helvetica"
    font_name_bold = font_name

    for row in labels:
        qr_img = _make_qr_image_with_logo(qr_text=row.qr_text, logo_path=logo_path, logo_scale=logo_scale)
        bio = BytesIO()
        qr_img.save(bio, format="PNG")
        bio.seek(0)
        qr_reader = ImageReader(bio)

        qr_x = page_w - margin - qr_size
        qr_y = margin + (6 * mm)
        c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size, preserveAspectRatio=True, mask='auto')

        text_x = margin
        text_y_top = page_h - margin - 8
        text_max_w = qr_x - margin - text_x

        c.setFont(font_name_bold, 12)
        c.drawString(text_x, text_y_top, (row.cins or "").strip())

        c.setFont(font_name, 10)
        _wrap_text(c, _turkish_upper((row.carpet_name or "").strip()), text_x, text_y_top - 16, text_max_w, 12)

        c.setFont(font_name, 8)
        _wrap_text(c, (row.qr_text or "").strip(), text_x, margin + 10, text_max_w, 10)

        c.showPage()

    c.save()


def generate_qr_list_pdf(
    labels: Iterable[LabelRow],
    output_pdf_path: str,
    cols: int = 5,
    rows: int = 12,
    margin_mm: float = 8.0,
    gap_mm: float = 2.0,
    logo_path: Optional[str] = None,
    logo_scale: float = 0.22,
) -> None:
    page_w, page_h = A4
    margin = margin_mm * mm
    gap = gap_mm * mm

    cell_w = (page_w - 2 * margin - (cols - 1) * gap) / cols
    cell_h = (page_h - 2 * margin - (rows - 1) * gap) / rows

    c = Canvas(output_pdf_path, pagesize=A4)
    font_name = _try_register_ttf_font() or "Helvetica"
    c.setFont(font_name, 7)

    items = list(labels)
    per_page = cols * rows
    page_count = (len(items) + per_page - 1) // per_page

    for pidx in range(page_count):
        start = pidx * per_page
        chunk = items[start : start + per_page]

        for i, row in enumerate(chunk):
            r = i // cols
            col = i % cols

            x0 = margin + col * (cell_w + gap)
            y0 = page_h - margin - (r + 1) * cell_h - r * gap

            qr_side = min(cell_w, cell_h) - (6 * mm)
            qr_side = max(qr_side, 10 * mm)

            qr_img = _make_qr_image_with_logo(qr_text=row.qr_text, box_size=6, border=1, logo_path=logo_path, logo_scale=logo_scale)
            bio = BytesIO()
            qr_img.save(bio, format="PNG")
            bio.seek(0)
            qr_reader = ImageReader(bio)

            qr_x = x0 + (cell_w - qr_side) / 2
            qr_y = y0 + (cell_h - qr_side) / 2 + (2 * mm)
            c.drawImage(qr_reader, qr_x, qr_y, width=qr_side, height=qr_side, preserveAspectRatio=True, mask='auto')

            txt = (row.qr_text or "").strip()
            txt_w = c.stringWidth(txt)
            max_w = cell_w - (2 * mm)
            if txt_w > max_w:
                while txt and c.stringWidth(txt + "…") > max_w:
                    txt = txt[:-1]
                txt = txt + "…"
            c.drawCentredString(x0 + cell_w / 2, y0 + (2 * mm), txt)

        c.showPage()

    c.save()


def default_output_pdf(input_path: str) -> str:
    base, _ = os.path.splitext(input_path)
    return base + "_etiketler.pdf"


def main_cli(argv: Optional[List[str]] = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="label_qr_pdf")
    p.add_argument("input", help=".txt veya .csv")
    p.add_argument("--out", default=None, help="Çıktı PDF yolu")
    p.add_argument("--width", type=float, default=80.0, help="Etiket genişliği (mm)")
    p.add_argument("--height", type=float, default=50.0, help="Etiket yüksekliği (mm)")
    p.add_argument("--encoding", default="utf-8", help="Dosya encoding")
    args = p.parse_args(argv)

    labels = read_labels(args.input, encoding=args.encoding)
    out = args.out or default_output_pdf(args.input)
    generate_labels_pdf(labels, out, width_mm=args.width, height_mm=args.height)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
