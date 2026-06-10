# 📖 Book Tool — User Manual

A simple tool that turns your images into a print-ready book for Amazon KDP.

---

## What does it do?

Takes a folder of images (PNG, JPG, etc.) and:

1. **Resizes** them to the correct print size
2. **Compiles** them into a KDP-ready PDF with proper margins
3. **Adds blank pages** automatically (so nothing prints on the back of a coloring page)
4. **Shows a compliance report** so you know the PDF is ready to upload

---

## Quick Start

### Step 1: Put your images in a folder

```
my-images/
├── cover.png
├── page-01.png
├── page-02.png
└── ...
```

### Step 2: Run the tool

Open a terminal in the folder where `book_tool.py` is located and run:

```bash
python book_tool.py --input ./my-images
```

### Step 3: Find your PDF

The PDF will be in `my-images/_book_output/book_8.5x11.0_inset.pdf`.

Upload it to KDP with:
- **Trim size:** 8.5 × 11 in
- **Bleed:** 0.125 in (yes)
- **Paper:** White
- **Color:** Black & White

---

## All Options Explained

### `--input` (or `-i`) — Your image folder

```
python book_tool.py --input ./my-images
```

Point this to the folder containing your images. The tool will use all images it finds (sorted by name).

---

### `--output` (or `-o`) — Where to save

```
python book_tool.py --input ./my-images --output ./my-book
```

Default: creates a `_book_output` folder inside your image folder.

---

### `--format` (or `-f`) — Output type

| Value | What you get |
|-------|-------------|
| `pdf` (default) | KDP-ready PDF with margins, blank pages, and compliance report |
| `docx` | Word document (each image on its own page — great for review) |
| `images` | Just the processed images (resized/compressed), no book file |

Examples:
```
python book_tool.py --input ./images --format docx
python book_tool.py --input ./images --format images --compress
```

---

### `--trim` — Book size

```
python book_tool.py --input ./images --trim 6x9
python book_tool.py --input ./images --trim 8.5x11
```

Default is `8.5x11` (standard US letter / KDP coloring book size). Use any width × height in inches.

---

### `--margins` — Safe zone margins

```
python book_tool.py --input ./images --margins 120
python book_tool.py --input ./images --margins 120 145
python book_tool.py --input ./images --margins 120 145 120 145
```

Controls how much white space to leave around your images. This prevents KDP from flagging "image outside margins" errors.

| Number of values | What it means |
|-----------------|---------------|
| 1 (`120`) | All four sides = 120 px |
| 2 (`120 145`) | Left/Right = 120, Top/Bottom = 145 |
| 4 (`120 145 120 145`) | Left, Top, Right, Bottom individually |

Default: `120 145` (120 px sides, 145 px top/bottom).

Set to `0` for full-bleed (edge-to-edge, no margins).

---

### `--render` — How images are placed

```
python book_tool.py --input ./images --render inset
python book_tool.py --input ./images --render full
```

| Mode | What it does |
|------|-------------|
| `inset` (default) | Scales image down to fit inside the safe margins. White space around edges. Safe for KDP. |
| `full` | Places image edge-to-edge. Use only if your images already have correct margins built in. |

---

### `--bleed` — Bleed size

```
python book_tool.py --input ./images --bleed 0.125
```

Default: `0.125` inches (standard KDP bleed). Leave this alone unless you know what you're doing.

---

### `--dpi` — Resolution

```
python book_tool.py --input ./images --dpi 300
```

Default: `300` (standard print quality). Leave this alone.

---

### `--mode` — How images are resized

```
python book_tool.py --input ./images --mode cover
python book_tool.py --input ./images --mode fit
```

| Mode | What it does | Best for |
|------|-------------|----------|
| `cover` (default) | Crops edges to fill the page exactly | Full-page artwork, coloring pages |
| `fit` | Shrinks image to fit entirely, may leave white bars | Photos, mixed aspect ratios |

---

### `--compress` — Reduce file size

```
python book_tool.py --input ./images --compress
python book_tool.py --input ./images --compress --quality 80
```

Converts images to JPEG and compresses them before building the PDF. This makes the PDF smaller.

- `--quality` controls the JPEG quality (1–100, default: 85)
- Lower = smaller file but worse quality
- 80–90 is a good balance

---

### `--no-resize` — Skip resizing

```
python book_tool.py --input ./images --no-resize
```

Use this if your images are already the correct size (2625 × 3375 px for 8.5×11 at 300 DPI).

---

### `--no-blanks` — Skip blank pages

```
python book_tool.py --input ./images --no-blanks
```

By default, a blank page is inserted after every image page (for single-sided coloring books). Use this flag to disable that.

---

### `--dry-run` — Preview without saving

```
python book_tool.py --input ./images --dry-run
```

Shows what the tool would do, without actually creating any files. Use this to check your settings first.

---

### `--verbose` (or `-v`) — Detailed output

```
python book_tool.py --input ./images -v
```

Shows every image name as it's processed.

---

## Examples

### Basic coloring book (recommended)

```bash
python book_tool.py --input ./my-coloring-pages
```

Resizes images to 2625×3375 px, adds 120/145 px safe margins, inserts blank reverse pages, creates KDP PDF.

### Review copy as Word document

```bash
python book_tool.py --input ./my-images --format docx
```

Creates a .docx with each image on its own page. Share with editors or preview on screen.

### Photo book, full-bleed, no blanks

```bash
python book_tool.py --input ./photos --render full --no-blanks
```

Places images edge-to-edge with no margins and no blank pages.

### Small format booklet

```bash
python book_tool.py --input ./images --trim 6x9 --margins 80 100
```

Creates a 6×9 inch booklet with 80 px side margins and 100 px top/bottom margins.

### Compress first, then build

```bash
python book_tool.py --input ./large-images --compress --quality 80
```

Compresses all images to JPEG quality 80, resizes them, then builds the PDF.

### Just process images, no book

```bash
python book_tool.py --input ./images --format images --compress --output ./clean-images
```

Compresses and resizes images, saves them to `./clean-images`, no PDF created.

---

## KDP Upload Settings

When uploading your PDF to Amazon KDP:

| Setting | Value |
|---------|-------|
| Trim size | 8.5 × 11 in |
| Bleed | **Yes** (0.125 in) |
| Paper | White |
| Interior | Black & White (or Color) |
| Pages | Shown in the compliance report |

---

## Troubleshooting

### "No supported images found"

Your folder doesn't contain any images the tool can read. Supported formats: PNG, JPG, JPEG, TIF, TIFF, BMP, WEBP.

### Images are stretched or have white bars

Try the other `--mode`:
- If images have white bars → use `--mode cover`
- If images are cropped too much → use `--mode fit`

### KDP says "image outside margins"

The safe margins are too small. Increase `--margins`:
```bash
python book_tool.py --input ./images --margins 150 150
```

### PDF is too large

Use `--compress --quality 75` to reduce file size.

### I want to see what the tool will do first

Use `--dry-run` to preview without creating any files.

---

## File Structure After Running

```
my-images/
├── page-01.png
├── page-02.png
├── ...
└── _book_output/           ← created by the tool
    ├── _resized/           ← resized versions of your images
    ├── book_8.5x11.0_inset.pdf   ← YOUR KDP-READY PDF
    └── book_8.5x11.0.docx  ← (if you used --format docx)
```
