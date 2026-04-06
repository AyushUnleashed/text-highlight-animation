"""Render highlight animation as MP4 using Pillow + FFmpeg.

Usage:
  python render_video.py <coords.json> <image_path> [options]

Reads the JSON produced by detect_lines.py, draws animated highlight
rectangles over the source image frame-by-frame, and pipes them to
FFmpeg to produce an MP4 (or a single PNG still).

No Node.js, no Remotion, no browser required.
"""
import json
import argparse
import math
import os
import struct
import subprocess
import sys
import tempfile
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

# ─── Config ──────────────────────────────────────────────────────────────────
_DEFAULT_CONFIG = os.path.join(os.path.dirname(__file__), "config.default.json")


def load_config(config_path: str | None = None) -> dict:
    """Load config from JSON files.

    Always starts from scripts/config.default.json (shipped with the tool).
    If --config is passed, that file is read and merged on top — so you only
    need to specify the keys you want to override.
    If no --config is passed, also checks .highlight/config.json in the
    working directory as a per-project override.
    """
    with open(_DEFAULT_CONFIG) as f:
        cfg = json.load(f)

    overlay_path = config_path or ".highlight/config.json"
    if os.path.isfile(overlay_path):
        with open(overlay_path) as f:
            cfg.update(json.load(f))

    return cfg


def ease_out_back(t: float) -> float:
    """Ease-out with slight overshoot — feels like a marker pen flicking across."""
    c1 = 1.70158
    c3 = c1 + 1.0
    return 1.0 + c3 * (t - 1.0) ** 3 + c1 * (t - 1.0) ** 2


def ease_out_cubic(t: float) -> float:
    """Cubic ease-out for smooth wipe deceleration."""
    return 1.0 - (1.0 - t) ** 3


def compute_delays_auto(lines: list[dict]) -> list[int]:
    """Word-count-based staggered delays (frames)."""
    delays = []
    d = 0
    for line in lines:
        delays.append(d)
        d += max(5, line["word_count"] * 4)
    return delays


def compute_delays_fixed(lines: list[dict], total_seconds: float, cfg: dict) -> list[int]:
    """Evenly distribute delays across a fixed total duration."""
    fps = cfg["fps"]
    total_frames = int(total_seconds * fps)
    available = total_frames - cfg["highlight_start_frame"] - cfg["wipe_frames"] - cfg["hold_frames"]
    if available < 0:
        available = 0
    n = len(lines)
    if n <= 1:
        return [0] * n
    step = available / (n - 1)
    return [round(i * step) for i in range(n)]


def parse_timestamps(ts_str: str, n_lines: int, cfg: dict) -> list[int]:
    """Parse comma-separated timestamps (seconds) into frame delays relative to highlight_start_frame.

    Example: "0.5,1.8,3.2" → [15, 54, 96] (at 30fps)
    """
    fps = cfg["fps"]
    start = cfg["highlight_start_frame"]
    parts = [float(t.strip()) for t in ts_str.split(",")]
    if len(parts) == 1:
        return None  # signal to caller: use as base offset only
    if len(parts) != n_lines:
        print(f"Error: --timestamps has {len(parts)} values but there are {n_lines} lines",
              file=sys.stderr)
        sys.exit(1)
    return [round(t * fps) - start for t in parts]


def parse_wipe_durations(wipe_str: str, n_lines: int, cfg: dict) -> list[int]:
    """Parse per-line wipe durations (seconds) into frame counts.

    Example: "0.8,0.3,1.0" → [24, 9, 30]
    Single value: "0.5" → [15, 15, 15] (applied to all lines)
    """
    fps = cfg["fps"]
    parts = [float(w.strip()) for w in wipe_str.split(",")]
    if len(parts) == 1:
        return [max(1, round(parts[0] * fps))] * n_lines
    if len(parts) != n_lines:
        print(f"Error: --wipe has {len(parts)} values but there are {n_lines} lines",
              file=sys.stderr)
        sys.exit(1)
    return [max(1, round(w * fps)) for w in parts]


def build_highlight_rects(coords_data: dict, canvas_w: int, canvas_h: int,
                          duration_seconds: float | None,
                          timestamps_str: str | None = None,
                          wipe_str: str | None = None,
                          img_path: str | None = None,
                          cfg: dict | None = None) -> tuple[list[dict], int]:
    """Convert line percentages to pixel rects with delays. Returns (rects, total_frames)."""
    if cfg is None:
        cfg = load_config()
    lines = coords_data["lines"]
    n = len(lines)

    # ── Compute image→canvas coordinate mapping ────────────────────────
    dims = coords_data.get("dimensions", {})
    orig_w = dims.get("original_width", canvas_w)
    orig_h = dims.get("original_height", canvas_h)

    target_w = int(canvas_w * cfg["image_fill"])
    scale = target_w / orig_w
    target_h = int(orig_h * scale)
    offset_x = (canvas_w - target_w) // 2
    offset_y = (canvas_h - target_h) // 2

    # ── Per-line wipe durations ──────────────────────────────────────────
    if wipe_str:
        wipe_frames_list = parse_wipe_durations(wipe_str, n, cfg)
    else:
        wipe_frames_list = [cfg["wipe_frames"]] * n

    # ── Per-line delays (start times) ────────────────────────────────────
    if timestamps_str:
        delays = parse_timestamps(timestamps_str, n, cfg)
        if delays is None:
            delays = compute_delays_auto(lines)
        last_end = max(cfg["highlight_start_frame"] + delays[i] + wipe_frames_list[i] for i in range(n))
        total_frames = last_end + cfg["hold_frames"]
    elif duration_seconds:
        delays = compute_delays_fixed(lines, duration_seconds, cfg)
        total_frames = int(duration_seconds * cfg["fps"])
    else:
        delays = compute_delays_auto(lines)
        last_delay = delays[-1] if delays else 0
        last_wipe = wipe_frames_list[-1] if wipe_frames_list else cfg["wipe_frames"]
        total_frames = cfg["highlight_start_frame"] + last_delay + last_wipe + cfg["hold_frames"]

    rects = []
    for i, line in enumerate(lines):
        raw_h_pct = line["height_pct"]

        top_pct    = line["top_pct"] + raw_h_pct * cfg["vertical_shift"] - cfg["padding_y"]
        left_pct   = line["left_pct"] - cfg["padding_x"]
        width_pct  = line["width_pct"] + cfg["padding_x"] * 2
        height_pct = raw_h_pct * cfg["height_scale"] + cfg["padding_y"] * 2

        x = offset_x + (left_pct / 100.0) * target_w
        y = offset_y + (top_pct / 100.0) * target_h
        w = (width_pct / 100.0) * target_w
        h = (height_pct / 100.0) * target_h

        rects.append({
            "x": x, "y": y, "w": w, "h": h,
            "delay": delays[i],
            "wipe_frames": wipe_frames_list[i],
        })

    return rects, total_frames


def hex_to_rgba(hex_color: str, opacity: float) -> tuple[int, int, int, int]:
    """Convert '#RRGGBB' + opacity to (R, G, B, A)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    a = int(opacity * 255)
    return (r, g, b, a)


def _create_rounded_mask(w: int, h: int, radius: int) -> Image.Image:
    """Create a rounded-rectangle alpha mask. White = inside, black = outside."""
    # Render at 2x for anti-aliased edges, then downscale
    scale = 2
    sw, sh, sr = w * scale, h * scale, radius * scale
    mask_big = Image.new("L", (sw, sh), 0)
    draw = ImageDraw.Draw(mask_big)
    draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=255)
    mask = mask_big.resize((w, h), Image.LANCZOS)
    return mask


def render_frame(base_img: Image.Image, rects: list[dict], style: dict,
                 frame_num: int, cfg: dict | None = None) -> Image.Image:
    """Render a single animation frame with highlight overlays."""
    if cfg is None:
        cfg = load_config()
    mode = style["mode"]
    color_hex = style["color"]
    opacity = style["opacity"]
    is_dark = style["isDarkBg"]

    # Work in RGBA
    frame = base_img.copy().convert("RGBA")
    canvas_w, canvas_h = frame.size

    for rect in rects:
        trigger_frame = cfg["highlight_start_frame"] + rect["delay"]

        if frame_num < trigger_frame:
            continue

        # Wipe progress: 0.0 → 1.0 over this line's wipe duration
        line_wipe = rect.get("wipe_frames", cfg["wipe_frames"])
        elapsed = frame_num - trigger_frame
        raw_t = min(1.0, elapsed / line_wipe)

        # Use ease-out-back for the wipe (slight overshoot, like a pen flick)
        wipe_progress = ease_out_back(raw_t) if raw_t < 1.0 else 1.0

        # Opacity fades in quickly during the first 30% of the wipe
        opacity_fade = min(1.0, raw_t / 0.3) if raw_t < 1.0 else 1.0
        frame_opacity = opacity * opacity_fade

        # Full rect dimensions (for mask shape)
        full_x = int(rect["x"])
        full_y = int(rect["y"])
        full_w = int(rect["w"])
        full_h = int(rect["h"])

        # Clamp wipe_progress (ease_out_back can overshoot past 1.0 briefly)
        clamped_progress = max(0.0, min(1.0, wipe_progress))

        # Current visible width of the highlight (wipe left-to-right)
        visible_w = int(rect["w"] * clamped_progress)
        if visible_w <= 0:
            continue

        # Clamp full rect to canvas
        full_x = max(0, full_x)
        full_y = max(0, full_y)
        full_w = min(full_w, canvas_w - full_x)
        full_h = min(full_h, canvas_h - full_y)
        visible_w = min(visible_w, full_w)

        if full_w <= 0 or full_h <= 0 or visible_w <= 0:
            continue

        # Rounded corner radius proportional to height
        radius = max(2, int(full_h * cfg["corner_radius"]))

        # Create the rounded mask at full width, then crop to visible portion (wipe)
        full_mask = _create_rounded_mask(full_w, full_h, radius)
        wipe_mask = full_mask.crop((0, 0, visible_w, full_h))

        # Apply feathered leading edge — soft gradient fade at the wipe front
        mask_arr = np.array(wipe_mask).astype(np.float32)
        if clamped_progress < 1.0:
            feather_px = max(4, int(full_w * cfg["feather_ratio"]))
            feather_start = max(0, visible_w - feather_px)
            for col in range(feather_start, visible_w):
                t = (col - feather_start) / feather_px  # 0 at start → 1 at edge
                fade = 1.0 - t * t  # Quadratic fade-out toward the edge
                mask_arr[:, col] *= fade

        if mode == "invert":
            # Extract region, invert, then composite through feathered rounded mask
            region = frame.crop((full_x, full_y, full_x + visible_w, full_y + full_h))
            r, g, b, a = region.split()
            r = ImageChops.invert(r)
            g = ImageChops.invert(g)
            b = ImageChops.invert(b)
            inverted = Image.merge("RGBA", (r, g, b, a))

            if frame_opacity < 1.0:
                blended = Image.blend(region, inverted, frame_opacity)
            else:
                blended = inverted

            final_mask = Image.fromarray((mask_arr * frame_opacity / opacity if opacity > 0 else mask_arr).astype(np.uint8))
            frame.paste(blended, (full_x, full_y), final_mask)
        else:
            # Marker mode: soft colored overlay with rounded corners + feathered edge
            r, g, b, _ = hex_to_rgba(color_hex, 1.0)
            color_layer = Image.new("RGBA", (visible_w, full_h), (r, g, b, 255))
            final_mask_arr = mask_arr * frame_opacity
            color_layer.putalpha(Image.fromarray(final_mask_arr.astype(np.uint8)))
            frame.alpha_composite(color_layer, (full_x, full_y))

    return frame


def render_still(base_img: Image.Image, rects: list[dict], style: dict,
                 frame_num: int, output_path: str, cfg: dict | None = None):
    """Render a single frame and save as PNG."""
    frame = render_frame(base_img, rects, style, frame_num, cfg)
    frame = frame.convert("RGB")
    frame.save(output_path, "PNG")


def render_mp4(base_img: Image.Image, rects: list[dict], style: dict,
               total_frames: int, output_path: str, canvas_w: int, canvas_h: int,
               cfg: dict | None = None):
    """Render all frames and pipe to FFmpeg for MP4 output."""
    if cfg is None:
        cfg = load_config()
    # Ensure even dimensions (required by h264)
    canvas_w = canvas_w if canvas_w % 2 == 0 else canvas_w + 1
    canvas_h = canvas_h if canvas_h % 2 == 0 else canvas_h + 1

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{canvas_w}x{canvas_h}",
        "-pix_fmt", "rgb24",
        "-r", str(cfg["fps"]),
        "-i", "-",
        "-c:v", "libx264",
        "-preset", cfg["ffmpeg_preset"],
        "-crf", str(cfg["crf"]),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]

    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        for f_num in range(total_frames):
            frame = render_frame(base_img, rects, style, f_num, cfg)
            frame = frame.convert("RGB").resize((canvas_w, canvas_h), Image.LANCZOS)
            proc.stdin.write(frame.tobytes())

            # Progress
            if (f_num + 1) % cfg["fps"] == 0 or f_num == total_frames - 1:
                pct = int((f_num + 1) / total_frames * 100)
                print(f"\r  Rendering: {f_num + 1}/{total_frames} frames ({pct}%)", end="", flush=True)

        proc.stdin.close()
        stderr = proc.stderr.read()
        proc.wait()

        if proc.returncode != 0:
            print(f"\nFFmpeg error:\n{stderr.decode()}", file=sys.stderr)
            sys.exit(1)

        print()  # newline after progress
    except BrokenPipeError:
        stderr = proc.stderr.read()
        proc.wait()
        print(f"\nFFmpeg error:\n{stderr.decode()}", file=sys.stderr)
        sys.exit(1)


def prepare_base_image(img_path: str, canvas_w: int, canvas_h: int,
                       bg_color: str, cfg: dict | None = None) -> Image.Image:
    """Load source image, center it on a canvas with padding (like the old Remotion layout)."""
    if cfg is None:
        cfg = load_config()
    src = Image.open(img_path).convert("RGBA")
    src_w, src_h = src.size

    # Target: image fills image_fill% of canvas width, centered
    target_w = int(canvas_w * cfg["image_fill"])
    scale = target_w / src_w
    target_h = int(src_h * scale)

    src_resized = src.resize((target_w, target_h), Image.LANCZOS)

    # Create canvas
    canvas = Image.new("RGBA", (canvas_w, canvas_h), bg_color)
    offset_x = (canvas_w - target_w) // 2
    offset_y = (canvas_h - target_h) // 2
    canvas.paste(src_resized, (offset_x, offset_y), src_resized)

    return canvas


def build_default_name(image_path: str, coords_data: dict, total_frames: int, cfg: dict) -> str:
    """Build a descriptive output filename from render parameters.

    Format: {image}_{n}lines_{mode}_{color}_{duration}s
    Example: tech_crunch_ex_4lines_marker_ffe066_2.8s
    """
    base = os.path.splitext(os.path.basename(image_path))[0]
    style = coords_data["style"]
    n_lines = len(coords_data["lines"])
    mode = style["mode"]
    color = style["color"].lstrip("#").lower()
    duration = round(total_frames / cfg["fps"], 1)
    # Format duration: drop decimal if it's a whole number (e.g. 3.0 → 3)
    dur_str = str(int(duration)) if duration == int(duration) else str(duration)
    return f"{base}_{n_lines}lines_{mode}_{color}_{dur_str}s"


def main():
    parser = argparse.ArgumentParser(
        description="Render highlight animation as MP4 or still PNG")
    parser.add_argument("coords_json", help="Path to coords JSON from detect_lines.py")
    parser.add_argument("image", help="Path to the source image")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path (default: out/<name>.mp4 or .png)")
    parser.add_argument("--duration-seconds", type=float, default=None,
                        help="Override total video duration in seconds")
    parser.add_argument("--timestamps", default=None,
                        help="Per-line start times in seconds, comma-separated (e.g. '0.5,1.8,3.2')")
    parser.add_argument("--wipe", default=None,
                        help="Wipe duration in seconds — single value for all lines or comma-separated per line (e.g. '0.5' or '0.8,0.3,1.0')")
    parser.add_argument("--still", action="store_true",
                        help="Render a single frame instead of video")
    parser.add_argument("--frame", type=int, default=None,
                        help="Frame number for --still (default: auto-pick near end)")
    parser.add_argument("--name", default=None,
                        help="Output name (default: derived from image filename)")
    parser.add_argument("--config", default=None,
                        help="Path to config JSON (default: .highlight/config.json if it exists)")

    args = parser.parse_args()

    cfg = load_config(args.config)

    with open(args.coords_json) as f:
        coords_data = json.load(f)

    style = coords_data["style"]
    dims = coords_data["dimensions"]

    canvas_w = dims["suggested_width"]
    canvas_h = dims["suggested_height"]

    bg_color = cfg["dark_bg_color"] if style["isDarkBg"] else cfg["light_bg_color"]

    # Build rects and compute duration
    rects, total_frames = build_highlight_rects(
        coords_data, canvas_w, canvas_h, args.duration_seconds,
        timestamps_str=args.timestamps, wipe_str=args.wipe, cfg=cfg)

    # Determine output name
    name = args.name
    if not name:
        name = build_default_name(args.image, coords_data, total_frames, cfg)

    # Prepare base image (centered on canvas)
    base_img = prepare_base_image(args.image, canvas_w, canvas_h, bg_color, cfg)

    os.makedirs("out", exist_ok=True)

    if args.still:
        frame_num = args.frame
        if frame_num is None:
            frame_num = min(total_frames - 1,
                           cfg["highlight_start_frame"] + (rects[-1]["delay"] if rects else 0) + cfg["wipe_frames"] + 2)
        output_path = args.output or f"out/{name}_frame{frame_num}.png"
        render_still(base_img, rects, style, frame_num, output_path, cfg)
        meta = {
            "output_path": output_path,
            "frame": frame_num,
            "total_frames": total_frames,
            "canvas": f"{canvas_w}x{canvas_h}",
        }
        print(json.dumps(meta))
    else:
        output_path = args.output or f"out/{name}.mp4"
        print(f"  Canvas: {canvas_w}x{canvas_h}, {total_frames} frames ({round(total_frames/cfg['fps'], 1)}s)")
        render_mp4(base_img, rects, style, total_frames, output_path, canvas_w, canvas_h, cfg)
        meta = {
            "output_path": output_path,
            "total_frames": total_frames,
            "duration_seconds": round(total_frames / cfg["fps"], 1),
            "fps": cfg["fps"],
            "canvas": f"{canvas_w}x{canvas_h}",
        }
        print(json.dumps(meta))


if __name__ == "__main__":
    main()
