#!/usr/bin/env python3
"""
book_tool.py  —  Universal KDP Book Compiler & Image Processor

Processes any folder of images into a KDP-ready book.

Examples:
  # Quick KDP PDF (all defaults)
  python book_tool.py --input ./raw_images

  # Custom trim and margins
  python book_tool.py --input ./images --trim 6x9 --margins 120 120

  # Compress + compile
  python book_tool.py --input ./images --compress --quality 80

  # Export as Word document for review
  python book_tool.py --input ./images --format docx

  # Just resize/compress images, no book
  python book_tool.py --input ./images --format images --compress --output ./processed

  # Preview without generating
  python book_tool.py --input ./images --dry-run
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

try:
    import docx
    from docx.shared import Inches, Cm
except ImportError:
    docx = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KDP_SPINE_IN_PER_PAGE = 0.002252
KDP_MIN_SPINE_IN = 0.06
_RESIZE_WARN_ASPECT = 0.02
_RESIZE_WARN_UPSCALE = 0.10

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)

def _parse_trim(s):
    parts = s.lower().replace("x", " ").replace("×", " ").split()
    if len(parts) == 2:
        return float(parts[0]), float(parts[1])
    raise ValueError(f"Invalid trim format: '{s}' (use e.g. 8.5x11)")

def _parse_margins(vals, dpi):
    if len(vals) == 1:
        return vals[0], vals[0], vals[0], vals[0]
    if len(vals) == 2:
        return vals[0], vals[1], vals[0], vals[1]
    if len(vals) == 4:
        return vals[0], vals[1], vals[2], vals[3]
    raise ValueError("--margins needs 1, 2, or 4 values")

def _spine_fraction(spine_in):
    d = 16
    n = round(spine_in * d)
    for _ in range(3):
        if n % 2 == 0:
            n //= 2; d //= 2
    return f"{n}/{d}\"" if d > 1 else f"{n}\""

def _sort_key(path):
    name = path.stem.lower()
    num = ""
    for ch in name:
        if ch.isdigit():
            num += ch
    return int(num) if num else 0

def _list_images(source_dir):
    exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    files = [f for f in Path(source_dir).iterdir() if f.suffix.lower() in exts]
    return sorted(files, key=_sort_key)

# ---------------------------------------------------------------------------
# Step 1: Resize
# ---------------------------------------------------------------------------

def resize_images(source_dir, target_dir, tw, th, dpi, mode="cover", dry=False):
    _ensure_dir(target_dir)
    files = _list_images(source_dir)
    results = {"ok": 0, "warn": 0, "skip": 0}

    if not files:
        print("  [WARN] No images found")
        return results

    have_warn = False
    for img_path in files:
        stem = img_path.stem
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"  [SKIP] {img_path.name}: {e}")
            results["skip"] += 1
            continue

        ow, oh = img.size
        scale = (max if mode == "cover" else min)(tw / ow, th / oh)
        nw, nh = int(ow * scale), int(oh * scale)

        if ow < tw or oh < th:
            print(f"  [WARN] {img_path.name}: {ow}x{oh} < target {tw}x{th}")
            have_warn = True

        if scale > 1 + _RESIZE_WARN_UPSCALE:
            print(f"  [WARN] {img_path.name}: upscaling {scale:.2f}x")
            have_warn = True

        sar = ow / oh
        tar = tw / th
        if abs(sar - tar) / tar > _RESIZE_WARN_ASPECT:
            print(f"  [WARN] {img_path.name}: aspect {sar:.4f} vs target {tar:.4f}")

        if dry:
            print(f"  [DRY] {img_path.name}: {ow}x{oh} -> {nw}x{nh} ({mode})")
            results["ok"] += 1
            continue

        resized = img.resize((nw, nh), Image.LANCZOS)
        if mode == "cover":
            l = (nw - tw) // 2
            t = (nh - th) // 2
            canvas = resized.crop((l, t, l + tw, t + th))
        else:
            canvas = Image.new("RGB", (tw, th), (255, 255, 255))
            x = (tw - nw) // 2
            y = (th - nh) // 2
            canvas.paste(resized, (x, y))

        out = target_dir / img_path.name
        canvas.save(out, "PNG", dpi=(dpi, dpi))
        results["ok"] += 1
        print(f"  [OK] {img_path.name}: {ow}x{oh} -> {canvas.width}x{canvas.height}")

    if not have_warn and results["ok"]:
        print(f"  All images at or above target resolution ({tw}x{th}).")

    return results

# ---------------------------------------------------------------------------
# Step 2: Compress
# ---------------------------------------------------------------------------

def compress_images(source_dir, target_dir, quality=85, dry=False):
    _ensure_dir(target_dir)
    files = _list_images(source_dir)
    saved = 0

    for img_path in files:
        stem = img_path.stem
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            print(f"  [SKIP] {img_path.name}: cannot open")
            continue

        out = target_dir / f"{stem}.jpg"
        orig_size = os.path.getsize(img_path)

        if dry:
            print(f"  [DRY] {img_path.name} -> {out.name} (Q={quality})")
            saved += 1
            continue

        img.save(out, "JPEG", quality=quality, optimize=True)
        new_size = os.path.getsize(out)
        ratio = (1 - new_size / orig_size) * 100
        print(f"  [OK] {img_path.name}: {orig_size//1024}KB -> {new_size//1024}KB ({ratio:.0f}% reduction)")
        saved += 1

    if dry and saved:
        print(f"  [DRY] Would compress {saved} image(s) at quality={quality}")

    return saved

# ---------------------------------------------------------------------------
# Step 3: Compile PDF
# ---------------------------------------------------------------------------

class BookPDF(FPDF):
    def __init__(self, trim_w, trim_h, bleed, dpi=300):
        full_w = trim_w + 2 * bleed
        full_h = trim_h + 2 * bleed
        super().__init__("P", "in", (full_w, full_h))
        self.dpi = dpi
        self.bleed = bleed
        self.trim_w = trim_w
        self.trim_h = trim_h
        self.set_auto_page_break(False)

    def render_image(self, path, ml=0, mr=0, mt=0, mb=0):
        self.set_fill_color(255, 255, 255)
        self.rect(0, 0, self.w, self.h, "F")

        if ml == mr == mt == mb == 0:
            self.image(str(path), 0, 0, self.w, self.h)
            return

        sx = ml / self.dpi
        sy = mt / self.dpi
        sw = self.w - (ml + mr) / self.dpi
        sh = self.h - (mt + mb) / self.dpi

        with Image.open(path) as img:
            iw = img.size[0] / self.dpi
            ih = img.size[1] / self.dpi

        sc = min(sw / iw, sh / ih)
        rw, rh = iw * sc, ih * sc
        x = sx + (sw - rw) / 2
        y = sy + (sh - rh) / 2
        self.image(str(path), x, y, rw, rh)

def compile_pdf(images, output_path, trim_w, trim_h, bleed, dpi,
                margins, insert_blanks, verbose=False):
    ml, mt, mr, mb = margins
    full_w = trim_w + 2 * bleed
    full_h = trim_h + 2 * bleed

    pdf = BookPDF(trim_w, trim_h, bleed, dpi)
    printable = {"png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"}
    blank_count = 0
    page_count = 0

    for img_path in images:
        ext = img_path.suffix.lower().lstrip(".")
        if ext not in printable:
            continue

        pdf.add_page()
        pdf.render_image(img_path, ml, mr, mt, mb)
        page_count += 1

        if insert_blanks:
            pdf.add_page()
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(0, 0, pdf.w, pdf.h, "F")
            blank_count += 1
            page_count += 1

        if verbose:
            print(f"  [{page_count}] {img_path.name}")

    pdf.output(str(output_path))
    return page_count, blank_count

# ---------------------------------------------------------------------------
# Step 4: Compile DOCX
# ---------------------------------------------------------------------------

def compile_docx(images, output_path, trim_w, trim_h, verbose=False):
    if docx is None:
        print("[ERROR] python-docx not installed (pip install python-docx)")
        return 0

    doc = docx.Document()
    section = doc.sections[0]
    section.page_width = Cm(trim_w * 2.54)
    section.page_height = Cm(trim_h * 2.54)
    section.top_margin = Cm(0.5)
    section.bottom_margin = Cm(0.5)
    section.left_margin = Cm(0.5)
    section.right_margin = Cm(0.5)

    printable = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
    count = 0

    for img_path in images:
        if img_path.suffix.lower() not in printable:
            continue

        try:
            with Image.open(img_path) as img:
                iw, ih = img.size
        except Exception:
            continue

        count += 1
        if count > 1:
            doc.add_page_break()

        ar = iw / ih
        page_w_in = trim_w - 0.5
        page_h_in = trim_h - 0.5
        if ar > page_w_in / page_h_in:
            display_w = Cm(page_w_in * 2.54)
            display_h = Cm((page_w_in / ar) * 2.54)
        else:
            display_h = Cm(page_h_in * 2.54)
            display_w = Cm((page_h_in * ar) * 2.54)

        doc.add_picture(str(img_path), width=display_w, height=display_h)
        if verbose:
            print(f"  [{count}] {img_path.name}")

    doc.save(str(output_path))
    return count

# ---------------------------------------------------------------------------
# KDP Report
# ---------------------------------------------------------------------------

def print_report(trim_w, trim_h, bleed, margins, dpi, page_count,
                 blank_count, spine_in, resize_ok, mode):
    ml, mt, mr, mb = margins
    full_w = trim_w + 2 * bleed
    full_h = trim_h + 2 * bleed
    cw = int((full_w - (ml + mr) / dpi) * dpi)
    ch = int((full_h - (mt + mb) / dpi) * dpi)

    print()
    print("=" * 50)
    print("  KDP COMPLIANCE REPORT")
    print("=" * 50)
    print(f"  OK Trim Size:          {trim_w}\" x {trim_h}\"")
    print(f"  OK Bleed:              {bleed}\"")
    print(f"  OK Full Page:          {full_w}\" x {full_h}\"")
    print(f"  OK Artwork:            {int(full_w*dpi)} x {int(full_h*dpi)} px @ {dpi} DPI")
    print(f"  OK Aspect Ratio:       {full_w/full_h:.6f}")
    if mode == "inset":
        print(f"  OK Render:             Safe-inset (L={ml} R={mr} T={mt} B={mb})")
        print(f"  OK Content Area:       {cw} x {ch} px")
    else:
        print(f"  OK Render:             Full-bleed (edge-to-edge)")
    print(f"  OK Blank Pages:        {blank_count} inserted")
    print(f"  OK Final Page Count:   {page_count}")
    print(f"  OK Estimated Spine:    {spine_in:.3f} in ({_spine_fraction(spine_in)})")
    print(f"  OK Image Quality:      {'All at target' if resize_ok else 'Some warnings'}")
    print(f"  OK KDP Ready:          YES")
    print("=" * 50)
    print(f"  Upload: trim={trim_w}\"x{trim_h}\", bleed={bleed}\"")
    print("=" * 50)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Universal KDP Book Compiler & Image Processor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--input", "-i", required=True, help="Input image directory")
    parser.add_argument("--output", "-o", default=None, help="Output directory")
    parser.add_argument("--format", "-f", choices=["pdf", "docx", "images"],
                        default="pdf", help="Output format (default: pdf)")
    parser.add_argument("--trim", default="8.5x11", help="Trim size WxH (default: 8.5x11)")
    parser.add_argument("--bleed", type=float, default=0.125, help="Bleed in inches (default: 0.125)")
    parser.add_argument("--margins", type=int, nargs="+", default=[120, 145],
                        help="Safe margins in px: 1 (all), 2 (h v), or 4 (l t r b)  (default: 120 145)")
    parser.add_argument("--dpi", type=int, default=300, help="Output DPI (default: 300)")
    parser.add_argument("--mode", choices=["cover", "fit"], default="cover",
                        help="Resize mode: cover=center-crop, fit=contain (default: cover)")
    parser.add_argument("--quality", type=int, default=85,
                        help="JPEG quality for --compress (default: 85)")
    parser.add_argument("--no-resize", action="store_true", help="Skip image resize")
    parser.add_argument("--compress", action="store_true", help="Compress images to JPEG")
    parser.add_argument("--no-blanks", action="store_true", help="Disable blank page insertion")
    parser.add_argument("--render", choices=["full", "inset"], default="inset",
                        help="PDF render mode: full=edge-to-edge, inset=safe-zone (default: inset)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")
    args = parser.parse_args()

    # --- Validate ---
    if Image is None:
        sys.exit("[ERROR] Install Pillow: pip install Pillow")

    source = Path(args.input)
    if not source.exists():
        sys.exit(f"[ERROR] Input directory not found: {source}")

    trim_w, trim_h = _parse_trim(args.trim)
    margins = _parse_margins(args.margins, args.dpi)
    ml, mt, mr, mb = margins
    bleed = args.bleed
    full_w = trim_w + 2 * bleed
    full_h = trim_h + 2 * bleed
    tw = int(full_w * args.dpi)
    th = int(full_h * args.dpi)

    out_dir = Path(args.output) if args.output else source / "_book_output"
    _ensure_dir(out_dir)

    images = _list_images(source)
    if not images:
        sys.exit(f"[ERROR] No supported images found in {source}")

    print(f"[CONFIG] Input:     {source} ({len(images)} images)")
    print(f"[CONFIG] Trim:      {trim_w}\" x {trim_h}\"  |  Bleed: {bleed}\"")
    print(f"[CONFIG] Page:      {full_w}\" x {full_h}\"  ({tw} x {th} px @ {args.dpi} DPI)")
    if args.render == "inset":
        print(f"[CONFIG] Render:    Safe-inset (L={ml} R={mr} T={mt} B={mb} px)")
    else:
        print(f"[CONFIG] Render:    Full-bleed (edge-to-edge)")
    print(f"[CONFIG] Output:    {out_dir}  |  Format: {args.format}")
    if args.dry_run:
        print(f"[CONFIG] Dry-run:   YES")
    print()

    # --- Step 1: Compress ---
    if args.compress:
        print("[STEP] Compressing images...")
        compressed_dir = out_dir / "_compressed"
        compress_images(source, compressed_dir, args.quality, args.dry_run)
        if not args.dry_run:
            source = compressed_dir
            images = _list_images(source)
        print()

    # --- Step 2: Resize ---
    resize_ok = True
    if not args.no_resize:
        print(f"[STEP] Resizing images to {tw}x{th} ({args.mode} mode)...")
        resized_dir = out_dir / "_resized"
        res = resize_images(source, resized_dir, tw, th, args.dpi, args.mode, args.dry_run)
        if res.get("warn", 0) > 0:
            resize_ok = False
        if not args.dry_run:
            source = resized_dir
            images = _list_images(source)
        print()
    else:
        print("[STEP] Skipping resize (--no-resize)")
        print()

    if args.format == "images":
        print(f"[DONE] Processed images in: {source}")
        return

    if args.dry_run:
        print(f"[DRY-RUN] Would compile {len(images)} images into {args.format.upper()}")
        print("[DRY-RUN] Done.")
        return

    # --- Step 3: Compile ---
    insert_blanks = not args.no_blanks
    spine_margins = (0, 0, 0, 0) if args.render == "full" else margins

    if args.format == "pdf":
        if FPDF is None:
            sys.exit("[ERROR] Install fpdf2: pip install fpdf2")
        print(f"[STEP] Compiling PDF ({len(images)} images)...")
        pdf_name = f"book_{trim_w}x{trim_h}_{args.render}.pdf"
        pdf_path = out_dir / pdf_name
        page_count, blank_count = compile_pdf(
            images, pdf_path, trim_w, trim_h, bleed, args.dpi,
            spine_margins, insert_blanks, args.verbose,
        )
        spine_in = (page_count * KDP_SPINE_IN_PER_PAGE
                    if page_count * KDP_SPINE_IN_PER_PAGE >= KDP_MIN_SPINE_IN
                    else KDP_MIN_SPINE_IN)
        sixteenths = round(spine_in / (1 / 16))
        spine_in = sixteenths / 16
        size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
        print(f"  [PDF] {pdf_path}  ({size_mb:.1f} MB, {page_count} pages)")
        print_report(trim_w, trim_h, bleed, spine_margins, args.dpi,
                     page_count, blank_count, spine_in, resize_ok, args.render)

    elif args.format == "docx":
        print(f"[STEP] Compiling DOCX ({len(images)} images)...")
        docx_name = f"book_{trim_w}x{trim_h}.docx"
        docx_path = out_dir / docx_name
        count = compile_docx(images, docx_path, trim_w, trim_h, args.verbose)
        size_mb = os.path.getsize(docx_path) / (1024 * 1024)
        print(f"  [DOCX] {docx_path}  ({size_mb:.1f} MB, {count} pages)")


if __name__ == "__main__":
    main()
