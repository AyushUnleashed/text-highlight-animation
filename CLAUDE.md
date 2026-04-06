# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A CLI tool that creates animated text highlight overlays on images. Takes a screenshot/image, detects text via OCR, renders animated highlight wipes frame-by-frame with Pillow, pipes to FFmpeg for H.264 encoding, and mixes per-line sound effects into the final MP4.

## Commands

```bash
bin/highlight setup                          # Create venv, install deps, check ffmpeg
bin/highlight detect <image>                 # Run OCR, show detected lines
bin/highlight generate <image> --lines N-M   # Full pipeline: detect + render + audio
bin/highlight render <image>                 # Re-render from existing .highlight/coords.json
bin/highlight still <image> --frame N        # Single PNG frame
```

The Python venv lives at `.highlight/.venv/`. To run Python scripts directly:
```bash
.highlight/.venv/bin/python scripts/detect_lines.py <image>
.highlight/.venv/bin/python scripts/render_video.py .highlight/coords.json <image>
```

No test suite exists. Validation is visual — use `--still` for fast iteration, then render full MP4.

## Architecture

```
Image → detect_lines.py (RapidOCR/ONNX) → .highlight/coords.json
  → render_video.py (Pillow frames → FFmpeg pipe → MP4)
  → mix_audio (per-line SFX trimmed/delayed → FFmpeg filter_complex → mux)
```

### Rendering Pipeline (render_video.py)

`render_frame()` is the core loop. For each line rect per frame it:
1. Computes wipe progress via `ease_out_back()` easing (0→1 with overshoot)
2. Calculates `visible_w` (left-to-right reveal) and opacity fade-in (first 30% of wipe)
3. Creates a rounded-rect mask, crops to `visible_w`, applies feathered leading edge
4. **Dispatches to `MODE_REGISTRY[mode](...)`** — this is where mode-specific rendering happens

### Mode Registry (highlight_modes.py)

All mode rendering is in `highlight_modes.py`. Each mode is a function with a shared signature registered in `MODE_REGISTRY`:

```python
def render_<mode>(frame, region_box, visible_w, mask_arr, frame_opacity,
                  color_hex, opacity, is_dark, cfg, rect_idx) -> Image
```

To add a new mode: write a render function, add it to `MODE_REGISTRY`, update `detect_lines.py` mode choices and default colors/opacities.

- **invert/marker**: use the 2D `mask_arr` directly as composite mask
- **underline/squiggly**: generate their own stroke mask, use `_wipe_profile_1d(mask_arr)` for the horizontal wipe
- **crayon**: generates a noise+hatching texture, cached in `_crayon_cache` across frames

### Audio Pipeline (render_video.py: mix_audio)

After video renders, `mix_audio()` picks random SFX from `sound_effects/<mode>/` per line, trims each to the line's wipe duration with fade-out, delays to trigger time, mixes via FFmpeg `filter_complex`, and muxes into the video. `invert` reuses `marker/` sounds.

## Config

`scripts/config.default.json` has all defaults. Per-project overrides go in `.highlight/config.json` (merged on top). CLI flags override both.

Mode-specific config is nested under the mode name:
```json
{
  "underline": { "frequency": 2.5, "amplitude": 2.5, "stroke_ratio": 0.18 },
  "squiggly": { "frequency": 5.0, "amplitude": 4.0 },
  "crayon":   { "grain_density": 0.6, "hatch_angle": 25 }
}
```

## Key Non-Obvious Details

- **coords.json uses percentages**: bounding boxes are stored as % of image dimensions, converted to pixels at render time relative to the canvas
- **Canvas sizing**: image is centered at `image_fill`% width on a canvas sized to the nearest standard aspect ratio (16:9, 9:16, 1:1, etc.)
- **Deterministic randomness**: underline/squiggly jitter and crayon texture use `np.random.RandomState(seed)` keyed to `rect_idx` — consistent across frames, no flicker
- **coords.json is editable**: users can tweak line positions after `detect` and re-render without re-running OCR
- **Background brightness detection**: `detect_lines.py` samples edge pixels to determine dark/light bg, which drives default color selection per mode
