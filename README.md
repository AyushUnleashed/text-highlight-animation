# highlight

CLI tool that creates animated text highlight overlays on images. Give it a screenshot, pick the lines you want highlighted, and get an MP4 with an animated wipe effect.

Uses OCR (Tesseract) to detect text lines, Pillow to render highlight frames, and FFmpeg to encode the video. No Node.js, no browser, no Remotion.

## Install

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install -y tesseract-ocr ffmpeg python3 python3-venv

# macOS
brew install tesseract ffmpeg python3
```

### Setup

```bash
# From this directory
bin/highlight setup
```

Setup creates a Python venv at `.highlight/.venv/` and installs `pillow`, `pytesseract`, and `numpy`.

To use from any directory, add the bin to your PATH:

```bash
# Add to ~/.bashrc or ~/.zshrc
export PATH="/path/to/highlight-text/bin:$PATH"
```

## Usage

### Quick start

```bash
# See what text lines OCR detects
bin/highlight detect screenshot.png

# Highlight lines 3 through 7, output as MP4
bin/highlight generate screenshot.png --lines 3-7
```

Output goes to `out/<image-name>.mp4`.

### Commands

| Command | Description |
|---------|-------------|
| `setup` | Create venv, install Python deps, check tesseract + ffmpeg |
| `detect <image>` | Run OCR and show detected text lines with indices |
| `generate <image>` | Full pipeline: detect text + render MP4 |
| `render <image>` | Render MP4 from existing `.highlight/coords.json` |
| `still <image>` | Render a single frame as PNG |

### Line selection

Pick which lines to highlight (0-indexed, from `detect` output):

```bash
# By index range
bin/highlight generate img.png --lines 3-7

# By text content match
bin/highlight generate img.png --start "first line text" --end "last line text"
```

### Highlight styles

Two modes:

```bash
# Invert (default) — white highlight with color inversion, high contrast on any background
bin/highlight generate img.png --lines 3-7 --mode invert

# Marker — semi-transparent colored overlay, like a highlighter pen
bin/highlight generate img.png --lines 3-7 --mode marker --color "#FFE066" --opacity 0.45
```

### Timing control

```bash
# Auto timing (default) — word-count-based stagger per line
bin/highlight generate img.png --lines 3-7

# Fixed total duration — lines spaced evenly within N seconds
bin/highlight generate img.png --lines 3-7 --duration 4

# Per-line start times — for syncing with speech/narration
bin/highlight generate img.png --lines 3-7 --timestamps 0.5,1.2,2.8,4.0

# Per-line wipe speed — how fast each line's highlight sweeps across
bin/highlight generate img.png --lines 3-7 --timestamps 0.5,1.2,2.8,4.0 --wipe 0.6,0.4,0.8,0.5

# Single wipe speed for all lines
bin/highlight generate img.png --lines 3-7 --wipe 0.8
```

### Other options

```bash
# Custom output filename
bin/highlight generate img.png --lines 3-7 --name my-highlight

# Render a still frame (PNG) instead of video
bin/highlight still img.png --frame 45

# Re-render from existing coords.json (after manual edits)
bin/highlight render img.png --wipe 0.5
```

## How it works

1. **detect** — Tesseract OCR finds text lines, outputs bounding boxes as percentages of image dimensions. Saved to `.highlight/coords.json`.
2. **render** — Pillow draws highlight rectangles frame-by-frame over the source image. Each line's highlight wipes left-to-right with a cubic ease-out. Frames are piped as raw RGB to FFmpeg which encodes them as H.264 MP4.

The source image is centered at 90% width on a canvas sized to the nearest standard aspect ratio (16:9, 9:16, 1:1, etc.).

## File structure

```
.highlight/
  .venv/          Python virtual environment
  coords.json     Last OCR detection output (editable)
out/
  <name>.mp4      Rendered videos
  <name>_frameN.png  Still frames
```

## Advanced: editing coords.json

After running `detect`, you can manually edit `.highlight/coords.json` to tweak line positions, then re-render:

```bash
bin/highlight detect img.png --lines 3-7
# edit .highlight/coords.json — adjust top_pct, left_pct, width_pct, height_pct
bin/highlight render img.png
```
