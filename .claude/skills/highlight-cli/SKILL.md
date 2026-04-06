---
name: highlight-cli
description: CLI tool for creating animated text highlight overlays on images using Python + FFmpeg. Use this skill when the user wants to highlight text in a screenshot, tweet, blog post, or any image — with an animated wipe/marker effect. Triggers on phrases like "highlight this text", "animate highlight on screenshot", "text highlight animation", "highlight these lines in the image". This skill wraps a standalone CLI tool — it handles all the deterministic work (OCR, frame rendering, video encoding) so you just need to call the right commands.
---

## What this does

Takes an image with text, detects lines via OCR, and renders an animated highlight overlay video (MP4) or still (PNG) using Pillow + FFmpeg. No Node.js or Remotion required.

## Tool location

The CLI lives at: `<this-skill-directory>/../../../bin/highlight`

Set it up as: `HIGHLIGHT="<this-skill-directory>/../../../bin/highlight"`

## Workflow

### First time in a project

```bash
$HIGHLIGHT setup      # creates .highlight/.venv, installs deps, checks tesseract + ffmpeg
```

### Creating a highlight animation

```bash
# Step 1: See what lines OCR detects
$HIGHLIGHT detect <image-path>

# Step 2: Generate everything (detect + render mp4)
$HIGHLIGHT generate <image-path> --lines 3-7

# Output lands in out/<image-name>.mp4
```

### Generate options

```
--lines N-M           Line range (0-indexed, from detect output)
--start "text"        Match start line by text content
--end "text"          Match end line by text content
--mode invert|marker  Style (default: invert — high contrast on any bg)
--color "#hex"        Highlight color
--opacity N           Highlight opacity (0.0-1.0)
--duration N          Override total video duration in seconds
--timestamps T1,T2,.. Per-line start times in seconds (for speech sync)
--wipe D or D1,D2,..  Wipe duration — single value or per-line (seconds)
--name OutputName     Custom output filename
```

### Other commands

```bash
$HIGHLIGHT render <image-path>              # render mp4 from existing coords.json
$HIGHLIGHT still <image-path>               # render single frame as PNG
$HIGHLIGHT still <image-path> --frame 45    # render specific frame
```

### Dependencies

- Python 3.8+
- Tesseract OCR (`apt install tesseract-ocr` / `brew install tesseract`)
- FFmpeg (`apt install ffmpeg` / `brew install ffmpeg`)

### Project structure

All tool state lives in `.highlight/` in the working directory:
- `.highlight/.venv/` — Python virtual environment
- `.highlight/coords.json` — last OCR output
- `out/` — rendered MP4 and PNG output
