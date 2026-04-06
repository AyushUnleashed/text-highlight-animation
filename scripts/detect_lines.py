"""Detect text line bounding boxes in any image using RapidOCR (ONNX-based).

Usage:
  python detect_lines.py <image_path> [--output path] [--start "text"] [--end "text"]
         [--lines 3-7] [--mode invert|marker] [--color "#hex"] [--opacity 0.0-1.0]

Outputs detected lines with bounding boxes, highlight style config, and image
dimensions (for aspect ratio calculation).

Two highlight modes:
  - "invert": white highlight + mixBlendMode 'difference'. High contrast on any bg.
  - "marker": semi-transparent colored highlight, no blend mode. Like a real pen.
"""
import json
import os
import argparse
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

_ocr = None


def get_ocr() -> RapidOCR:
    global _ocr
    if _ocr is None:
        _ocr = RapidOCR()
    return _ocr


def detect_bg_brightness(img: Image.Image) -> float:
    """Return average brightness of the image edges (background estimate)."""
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    edge_pixels = np.concatenate([
        arr[:int(h * 0.1), :].flatten(),
        arr[int(h * 0.9):, :].flatten(),
        arr[:, :int(w * 0.1)].flatten(),
        arr[:, int(w * 0.9):].flatten(),
    ])
    return float(np.mean(edge_pixels))


def detect_lines(img_path: str) -> list[dict]:
    """Run RapidOCR and group detections into lines with bounding boxes.

    RapidOCR uses ONNX-based deep-learning models (~50MB total, no PyTorch/CUDA)
    and handles colored backgrounds (e.g. white text on green) far better than
    Tesseract's pixel-thresholding approach.
    """
    img = Image.open(img_path)
    w, h = img.size

    ocr = get_ocr()
    # result: list of [bbox, text, confidence]
    # bbox: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]] (four corners, clockwise)
    result, _ = ocr(img_path)
    if not result:
        return []

    # Group word detections into lines by vertical proximity (within 15px).
    # Key = approximate top-y of the line.
    lines: dict[int, dict] = {}
    for bbox, text, _conf in result:
        text = text.strip()
        if not text:
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        x1, y1 = int(min(xs)), int(min(ys))
        x2, y2 = int(max(xs)), int(max(ys))

        matched_key = None
        for key in lines:
            if abs(key - y1) < 15:
                matched_key = key
                break
        if matched_key is None:
            matched_key = y1
            lines[matched_key] = {"words": [], "left": x1, "top": y1, "right": x2, "bottom": y2}

        lines[matched_key]["words"].append(text)
        lines[matched_key]["left"]   = min(lines[matched_key]["left"],   x1)
        lines[matched_key]["top"]    = min(lines[matched_key]["top"],    y1)
        lines[matched_key]["right"]  = max(lines[matched_key]["right"],  x2)
        lines[matched_key]["bottom"] = max(lines[matched_key]["bottom"], y2)

    results = []
    for key in sorted(lines.keys()):
        line = lines[key]
        text = " ".join(line["words"])
        results.append({
            "text": text,
            "word_count": len(line["words"]),
            "top_pct":    round(line["top"]                    / h * 100, 2),
            "left_pct":   round(line["left"]                   / w * 100, 2),
            "width_pct":  round((line["right"] - line["left"]) / w * 100, 2),
            "height_pct": round((line["bottom"] - line["top"]) / h * 100, 2),
        })
    return results


def find_range(lines: list[dict], start_text: str, end_text: str) -> list[dict]:
    """Find all lines between (inclusive) lines containing start_text and end_text."""
    start_idx = None
    end_idx = None
    for i, line in enumerate(lines):
        lower = line["text"].lower()
        if start_idx is None and start_text.lower() in lower:
            start_idx = i
        if end_text.lower() in lower:
            end_idx = i
    if start_idx is None or end_idx is None:
        return []
    return lines[start_idx:end_idx + 1]


def get_image_dimensions(img_path: str) -> dict:
    """Return image width, height, and the closest common aspect ratio under 1080p."""
    img = Image.open(img_path)
    w, h = img.size
    ratio = w / h

    common_ratios = [
        (1.0,    1080, 1080,  "1:1 (square)"),
        (16/9,   1920, 1080,  "16:9 (landscape)"),
        (9/16,   1080, 1920,  "9:16 (portrait/stories)"),
        (4/3,    1440, 1080,  "4:3 (classic)"),
        (3/4,    1080, 1440,  "3:4 (portrait)"),
        (3/2,    1620, 1080,  "3:2 (photo)"),
        (2/3,    1080, 1620,  "2:3 (portrait photo)"),
    ]

    best = min(common_ratios, key=lambda r: abs(ratio - r[0]))

    return {
        "original_width": w,
        "original_height": h,
        "aspect_ratio": round(ratio, 3),
        "suggested_width": best[1],
        "suggested_height": best[2],
        "aspect_label": best[3],
    }


def get_highlight_style(img_path: str, mode=None, color=None, opacity=None) -> dict:
    """Determine highlight style. Defaults to invert mode for maximum contrast."""
    img = Image.open(img_path)
    brightness = detect_bg_brightness(img)
    is_dark = brightness < 128

    if mode is None:
        mode = "invert"
    if color is None:
        if mode == "invert":
            color = "#ffffff"
        elif mode in ("underline", "squiggly"):
            color = "#FF6B6B" if is_dark else "#FF4444"  # Red — classic underline
        elif is_dark:
            color = "#5CE1E6"  # Soft cyan on dark backgrounds
        else:
            color = "#FFD93D"  # Warm golden yellow on light backgrounds
    if opacity is None:
        if mode == "invert":
            opacity = 1.0
        elif mode in ("underline", "squiggly"):
            opacity = 0.85
        elif mode == "crayon":
            opacity = 0.70
        else:
            opacity = 0.38

    blend_mode = "difference" if mode == "invert" else "normal"

    return {
        "mode": mode,
        "color": color,
        "opacity": opacity,
        "blendMode": blend_mode,
        "bgBrightness": round(brightness, 1),
        "isDarkBg": is_dark,
    }


def parse_line_range(line_spec: str) -> tuple[int, int]:
    """Parse a line range spec like '3-7' or '5' into (start, end) inclusive."""
    if "-" in line_spec:
        parts = line_spec.split("-", 1)
        return int(parts[0]), int(parts[1])
    n = int(line_spec)
    return n, n


def main():
    parser = argparse.ArgumentParser(description="Detect text lines in an image")
    parser.add_argument("image", help="Path to the image")
    parser.add_argument("--output", "-o", default=".highlight/coords.json",
                        help="Output path for coords JSON (default: .highlight/coords.json)")
    parser.add_argument("--start", help="Start text to search for", default=None)
    parser.add_argument("--end", help="End text to search for", default=None)
    parser.add_argument("--lines", help="Line range to select, e.g. '3-7' or '5'",
                        default=None)
    parser.add_argument("--mode", choices=["invert", "marker", "underline", "squiggly", "crayon"],
                        default=None,
                        help="Highlight mode. Defaults to 'invert' for max contrast.")
    parser.add_argument("--color", default=None,
                        help="Highlight color as hex (e.g. '#FFE066').")
    parser.add_argument("--opacity", type=float, default=None,
                        help="Highlight opacity 0.0-1.0.")
    parser.add_argument("--config", default=None,
                        help="Path to config JSON (default: .highlight/config.json if it exists). "
                             "Provides fallback defaults for mode, color, opacity.")
    args = parser.parse_args()

    # Load config: start from config.default.json, overlay user config on top
    _default_cfg_path = os.path.join(os.path.dirname(__file__), "config.default.json")
    with open(_default_cfg_path) as f:
        cfg = json.load(f)
    overlay_path = args.config or ".highlight/config.json"
    if os.path.isfile(overlay_path):
        with open(overlay_path) as f:
            cfg.update(json.load(f))

    # CLI flags take priority over config
    mode    = args.mode    or cfg.get("mode")
    color   = args.color   or cfg.get("color")
    opacity = args.opacity if args.opacity is not None else cfg.get("opacity")

    lines = detect_lines(args.image)

    print(f"Detected {len(lines)} lines:\n")
    for i, line in enumerate(lines):
        print(f"  {i:2d}. \"{line['text']}\"")
        print(f"      top={line['top_pct']}% left={line['left_pct']}% "
              f"w={line['width_pct']}% h={line['height_pct']}%")

    style = get_highlight_style(args.image, mode, color, opacity)
    dims = get_image_dimensions(args.image)

    print(f"\n--- Image dimensions ---")
    print(f"  Original:  {dims['original_width']}x{dims['original_height']} "
          f"(ratio: {dims['aspect_ratio']})")
    print(f"  Suggested: {dims['suggested_width']}x{dims['suggested_height']} "
          f"({dims['aspect_label']})")

    print(f"\n--- Highlight style ---")
    print(f"  Background brightness: {style['bgBrightness']} "
          f"({'dark' if style['isDarkBg'] else 'light'})")
    print(f"  Mode:      {style['mode']}")
    print(f"  Color:     {style['color']}")
    print(f"  Opacity:   {style['opacity']}")
    print(f"  BlendMode: {style['blendMode']}")

    # Select lines based on user input; track start/end indices for naming
    matched = lines
    line_start, line_end = 0, max(0, len(lines) - 1)
    if args.lines:
        line_start, line_end = parse_line_range(args.lines)
        matched = lines[line_start:line_end + 1]
        print(f"\n--- Selected lines {line_start}-{line_end} ({len(matched)} lines) ---\n")
        for line in matched:
            print(f"  \"{line['text']}\"")
            print(f"      top={line['top_pct']}% left={line['left_pct']}% "
                  f"w={line['width_pct']}% h={line['height_pct']}%")
    elif args.start and args.end:
        matched = find_range(lines, args.start, args.end)
        # Resolve indices in the original list
        if matched:
            line_start = lines.index(matched[0])
            line_end = lines.index(matched[-1])
        print(f"\n--- Matched {len(matched)} lines ---\n")
        for line in matched:
            print(f"  \"{line['text']}\"")
            print(f"      top={line['top_pct']}% left={line['left_pct']}% "
                  f"w={line['width_pct']}% h={line['height_pct']}%")

    # Calculate auto duration
    total_words = sum(l["word_count"] for l in matched)
    delays = []
    d = 0
    for l in matched:
        delays.append(d)
        d += max(5, l["word_count"] * 4)
    last_delay = delays[-1] if delays else 0
    auto_duration_frames = 20 + last_delay + 18 + 30
    auto_duration_seconds = round(auto_duration_frames / 30, 1)

    print(f"\n--- Auto duration ---")
    print(f"  Lines: {len(matched)}, Words: {total_words}")
    print(f"  Duration: {auto_duration_frames} frames ({auto_duration_seconds}s at 30fps)")

    # Save output
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    output = {"style": style, "dimensions": dims, "lines": matched,
              "line_range": {"start": line_start, "end": line_end},
              "auto_duration": {"frames": auto_duration_frames,
                                "seconds": auto_duration_seconds}}
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
