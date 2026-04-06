# highlight

CLI tool that creates animated text highlight overlays on images. Give it a screenshot, pick the lines you want highlighted, and get an MP4 with an animated wipe effect and matching sound effects.

Uses OCR (RapidOCR / ONNX) to detect text lines, Pillow to render highlight frames, and FFmpeg to encode the video. No Node.js, no browser, no Remotion.

## Install

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install -y ffmpeg python3 python3-venv

# macOS
brew install ffmpeg python3
```

### Setup

```bash
# From this directory
bin/highlight setup
```

Setup creates a Python venv at `.highlight/.venv/` and installs `rapidocr-onnxruntime`, `pillow`, and `numpy`.

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
| `setup` | Create venv, install Python deps, check ffmpeg |
| `detect <image>` | Run OCR and show detected text lines with indices |
| `generate <image>` | Full pipeline: detect text + render MP4 with audio |
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

### Highlight modes

Five modes, each with a distinct visual style and matching sound effects:

```bash
# Invert (default) — color inversion, high contrast on any background
bin/highlight generate img.png --lines 3-7 --mode invert

# Marker — semi-transparent colored overlay, like a highlighter pen
bin/highlight generate img.png --lines 3-7 --mode marker --color "#FFE066" --opacity 0.45

# Underline — handwritten wavy underline with pressure taper and tail flick
bin/highlight generate img.png --lines 3-7 --mode underline

# Squiggly — spell-check style wavy underline with pronounced oscillation
bin/highlight generate img.png --lines 3-7 --mode squiggly

# Crayon — textured wax-on-paper highlight with grain and diagonal hatching
bin/highlight generate img.png --lines 3-7 --mode crayon
```

Each mode auto-selects appropriate default colors:
- **invert**: white (#ffffff)
- **marker**: cyan on dark backgrounds, golden yellow on light
- **underline / squiggly**: red (#FF4444 light, #FF6B6B dark)
- **crayon**: same as marker

### Sound effects

Each mode has its own set of sound effects that play in sync with the highlight animation:

| Mode | Sound style |
|------|-------------|
| invert | Highlighter pen stroke |
| marker | Highlighter pen stroke |
| underline | Pen writing on paper |
| squiggly | Fast scribble / scratching |
| crayon | Chalk / crayon on paper |

Sounds are automatically trimmed to match each line's wipe duration and delayed to sync with the animation. To produce a silent video:

```bash
bin/highlight generate img.png --lines 3-7 --no-audio
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

# Custom output path
bin/highlight generate img.png --lines 3-7 -o out/custom.mp4

# Render a still frame (PNG) instead of video
bin/highlight still img.png --frame 45

# Re-render from existing coords.json (after manual edits)
bin/highlight render img.png --wipe 0.5
```

## Configuration

All rendering parameters live in `scripts/config.default.json`. Override per-project by creating `.highlight/config.json` with only the keys you want to change.

Key parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `mode` | `invert` | Default highlight mode |
| `wipe_frames` | 18 | Frames per line wipe animation (0.6s at 30fps) |
| `hold_frames` | 30 | Frames to hold all highlights at end |
| `highlight_start_frame` | 20 | Delay before first line animates |
| `fps` | 30 | Video frame rate |
| `image_fill` | 0.9 | Image width as fraction of canvas |
| `feather_ratio` | 0.18 | Soft edge gradient width |
| `corner_radius` | 0.22 | Rounded corner radius (fraction of line height) |

Mode-specific config is nested:

```json
{
  "underline": { "frequency": 2.5, "amplitude": 2.5, "stroke_ratio": 0.18, "tail_flick": true },
  "squiggly": { "frequency": 5.0, "amplitude": 4.0, "stroke_ratio": 0.28 },
  "crayon":   { "grain_density": 0.6, "hatch_spacing": 4, "hatch_angle": 25 }
}
```

## How it works

1. **detect** — RapidOCR (ONNX-based) finds text lines, outputs bounding boxes as percentages of image dimensions. Saved to `.highlight/coords.json`.
2. **render** — Pillow draws highlight overlays frame-by-frame over the source image. Each line's highlight wipes left-to-right with an ease-out-back easing. Frames are piped as raw RGB to FFmpeg for H.264 encoding. Mode rendering is modular — each mode is a function in `scripts/highlight_modes.py` registered in `MODE_REGISTRY`.
3. **audio** — Per-line sound effects are picked from `sound_effects/<mode>/`, trimmed to the wipe duration, delayed to sync, mixed together, and muxed into the video via FFmpeg.

The source image is centered at 90% width on a canvas sized to the nearest standard aspect ratio (16:9, 9:16, 1:1, etc.).

## File structure

```
bin/highlight              CLI entry point (Bash)
scripts/
  config.default.json      Default rendering config
  detect_lines.py          OCR detection + line grouping
  render_video.py          Frame rendering + FFmpeg encoding + audio mixing
  highlight_modes.py       Mode rendering functions + MODE_REGISTRY
sound_effects/
  marker/                  Highlighter pen sounds (also used by invert)
  underline/               Pen stroke on paper sounds
  squiggly/                Fast scribble sounds
  crayon/                  Chalk/crayon on paper sounds
.highlight/
  .venv/                   Python virtual environment
  coords.json              Last OCR detection output (editable)
out/
  <name>.mp4               Rendered videos
  <name>_frameN.png        Still frames
```

## Advanced: editing coords.json

After running `detect`, you can manually edit `.highlight/coords.json` to tweak line positions, then re-render:

```bash
bin/highlight detect img.png --lines 3-7
# edit .highlight/coords.json — adjust top_pct, left_pct, width_pct, height_pct
bin/highlight render img.png
```
