---
name: highlight-cli
description: CLI tool for creating animated text highlight overlays on images using Python + FFmpeg. Use this skill when the user wants to highlight text in a screenshot, tweet, blog post, or any image — with an animated wipe/marker effect. Triggers on phrases like "highlight this text", "animate highlight on screenshot", "text highlight animation", "highlight these lines in the image". This skill wraps a standalone CLI tool — it handles all the deterministic work (OCR, frame rendering, video encoding) so you just need to call the right commands.
---

## What this does

Takes an image with text, detects lines via OCR (RapidOCR / ONNX), and renders an animated highlight overlay video (MP4) with matching sound effects, or a still (PNG), using Pillow + FFmpeg. No Node.js or Remotion required.

## Tool location

The CLI lives at: `<this-skill-directory>/../../../bin/highlight`

Set it up as: `HIGHLIGHT="<this-skill-directory>/../../../bin/highlight"`

## Workflow

### First time in a project

```bash
$HIGHLIGHT setup      # creates .highlight/.venv, installs deps, checks ffmpeg
```

### Creating a highlight animation

```bash
# Step 1: See what lines OCR detects
$HIGHLIGHT detect <image-path>

# Step 2: Generate everything (detect + render mp4 + mix audio)
$HIGHLIGHT generate <image-path> --lines 3-7

# Output lands in out/<image-name>.mp4
```

### Generate options

```
--lines N-M           Line range (0-indexed, from detect output)
--start "text"        Match start line by text content
--end "text"          Match end line by text content
--mode MODE           Highlight style (see modes below, default: invert)
--color "#hex"        Highlight color
--opacity N           Highlight opacity (0.0-1.0)
--duration N          Override total video duration in seconds
--timestamps T1,T2,.. Per-line start times in seconds (for speech sync)
--wipe D or D1,D2,..  Wipe duration — single value or per-line (seconds)
--name OutputName     Custom output filename
--output/-o path      Custom output file path
--no-audio            Skip sound effect mixing (silent video)
```

### Highlight modes

Five modes available, each with distinct visuals and matching sound effects:

| Mode | Visual | Sound | Default color |
|------|--------|-------|---------------|
| `invert` (default) | Color inversion, high contrast on any bg | Highlighter pen | white |
| `marker` | Semi-transparent colored overlay | Highlighter pen | cyan (dark bg) / yellow (light bg) |
| `underline` | Handwritten wavy underline with pressure taper + tail flick | Pen on paper | red |
| `squiggly` | Spell-check style wavy underline, pronounced oscillation | Fast scribble | red |
| `crayon` | Textured wax-on-paper with grain + diagonal hatching | Chalk/crayon stroke | cyan (dark bg) / yellow (light bg) |

```bash
$HIGHLIGHT generate img.png --lines 3-7 --mode underline
$HIGHLIGHT generate img.png --lines 3-7 --mode squiggly
$HIGHLIGHT generate img.png --lines 3-7 --mode crayon
$HIGHLIGHT generate img.png --lines 3-7 --mode marker --color "#FFE066" --opacity 0.45
```

### Sound effects

Per-line SFX are auto-picked from `sound_effects/<mode>/`, trimmed to each line's wipe duration, and mixed into the video. Use `--no-audio` for silent output.

### Other commands

```bash
$HIGHLIGHT render <image-path>              # render mp4 from existing coords.json
$HIGHLIGHT still <image-path>               # render single frame as PNG
$HIGHLIGHT still <image-path> --frame 45    # render specific frame
```

### Configuration

All rendering parameters live in `scripts/config.default.json`. Override per-project via `.highlight/config.json`. Mode-specific config is nested:

```json
{
  "underline": { "frequency": 2.5, "amplitude": 2.5, "stroke_ratio": 0.18, "tail_flick": true },
  "squiggly": { "frequency": 5.0, "amplitude": 4.0, "stroke_ratio": 0.28 },
  "crayon":   { "grain_density": 0.6, "hatch_spacing": 4, "hatch_angle": 25 }
}
```

### Dependencies

- Python 3.8+
- FFmpeg (`apt install ffmpeg` / `brew install ffmpeg`)

### Project structure

All tool state lives in `.highlight/` in the working directory:
- `.highlight/.venv/` — Python virtual environment
- `.highlight/coords.json` — last OCR output
- `out/` — rendered MP4 and PNG output

### Architecture

Mode rendering is modular — each mode is a function in `scripts/highlight_modes.py` registered in a `MODE_REGISTRY` dict. Adding a new mode only requires writing a render function and adding it to the registry.

```
scripts/
  highlight_modes.py   — MODE_REGISTRY + render functions for all 5 modes
  render_video.py      — frame orchestration, timing, FFmpeg encoding, audio mixing
  detect_lines.py      — RapidOCR detection + line grouping + style defaults
  config.default.json  — all rendering parameters (flat + nested per-mode)
sound_effects/
  marker/              — highlighter pen sounds (also used by invert)
  underline/           — pen stroke on paper
  squiggly/            — fast scribble sounds
  crayon/              — chalk/crayon on paper
```
