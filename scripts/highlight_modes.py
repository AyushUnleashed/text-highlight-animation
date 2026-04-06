"""Highlight mode rendering functions.

Each mode function has the same signature and is registered in MODE_REGISTRY.
render_video.py dispatches to these via the registry — adding a new mode only
requires writing a function here and adding it to the dict.
"""
import math
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter


# ─── Helpers ────────────────────────────────────────────────────────────────

def hex_to_rgba(hex_color: str, opacity: float) -> tuple[int, int, int, int]:
    """Convert '#RRGGBB' + opacity to (R, G, B, A)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    a = int(opacity * 255)
    return (r, g, b, a)


def _wipe_profile_1d(mask_arr: np.ndarray) -> np.ndarray:
    """Extract a 1-D horizontal wipe multiplier from a 2-D mask.

    Takes the max across rows so underline/squiggly modes can apply the
    left-to-right wipe + feathered edge to their own stroke-shaped masks.
    """
    return np.max(mask_arr, axis=0)  # shape: (visible_w,)


# ─── Invert Mode ────────────────────────────────────────────────────────────

def render_invert(frame: Image.Image, region_box: tuple[int, int, int, int],
                  visible_w: int, mask_arr: np.ndarray, frame_opacity: float,
                  color_hex: str, opacity: float, is_dark: bool,
                  cfg: dict, rect_idx: int) -> Image.Image:
    """Invert RGB channels under the highlight region."""
    full_x, full_y, full_w, full_h = region_box

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

    final_mask = Image.fromarray(
        (mask_arr * frame_opacity / opacity if opacity > 0 else mask_arr).astype(np.uint8))
    frame.paste(blended, (full_x, full_y), final_mask)
    return frame


# ─── Marker Mode ────────────────────────────────────────────────────────────

def render_marker(frame: Image.Image, region_box: tuple[int, int, int, int],
                  visible_w: int, mask_arr: np.ndarray, frame_opacity: float,
                  color_hex: str, opacity: float, is_dark: bool,
                  cfg: dict, rect_idx: int) -> Image.Image:
    """Semi-transparent colored overlay (like a highlighter pen)."""
    full_x, full_y, full_w, full_h = region_box

    r, g, b, _ = hex_to_rgba(color_hex, 1.0)
    color_layer = Image.new("RGBA", (visible_w, full_h), (r, g, b, 255))
    final_mask_arr = mask_arr * frame_opacity
    color_layer.putalpha(Image.fromarray(final_mask_arr.astype(np.uint8)))
    frame.alpha_composite(color_layer, (full_x, full_y))
    return frame


# ─── Underline Mode ─────────────────────────────────────────────────────────

def _build_stroke_mask(full_w: int, stroke_h: int, frequency: float,
                       amplitude: float, jitter: float, seed: int,
                       tail_flick: bool = False) -> np.ndarray:
    """Generate a handwritten stroke mask (shared by underline and squiggly).

    Returns a float32 array of shape (stroke_h, full_w) with values 0-255.
    The stroke follows a sine wave with pressure taper and optional tail flick.
    """
    rng = np.random.RandomState(seed)
    mask = np.zeros((stroke_h, full_w), dtype=np.float32)
    if full_w <= 0 or stroke_h <= 0:
        return mask

    center_y = stroke_h / 2.0
    xs = np.arange(full_w, dtype=np.float64)
    ts = xs / max(1, full_w - 1)  # 0→1 normalised position
    phase = rng.uniform(0, 2 * math.pi)

    # Sine wave path
    wave_y = amplitude * np.sin(2 * math.pi * frequency * ts + phase)

    # Per-pixel jitter (seeded, deterministic per line)
    wave_y = wave_y + rng.uniform(-jitter, jitter, size=full_w)

    # Tail flick: slight upward curve at the end of the stroke
    if tail_flick:
        flick_start = 0.90
        flick_mask = ts > flick_start
        flick_t = np.where(flick_mask, (ts - flick_start) / (1.0 - flick_start), 0.0)
        wave_y = wave_y - amplitude * 1.5 * flick_t ** 2

    y_centers = center_y + wave_y

    # Pressure taper: thick in middle, thin at edges (parabolic)
    base_thickness = max(1.0, stroke_h * 0.45)
    pressure = 0.55 + 0.45 * (1.0 - (2 * ts - 1) ** 2)
    thicknesses = base_thickness * pressure

    # Vectorised: compute distance of every (row, col) from the stroke center
    ys = np.arange(stroke_h, dtype=np.float64).reshape(-1, 1)  # (stroke_h, 1)
    y_c = y_centers.reshape(1, -1)                               # (1, full_w)
    half_t = (thicknesses / 2.0).reshape(1, -1)                  # (1, full_w)

    dist = np.abs(ys - y_c) / np.maximum(0.5, half_t)
    alpha = np.clip(1.0 - dist ** 2, 0.0, 1.0) * 255.0
    return alpha.astype(np.float32)


def render_underline(frame: Image.Image, region_box: tuple[int, int, int, int],
                     visible_w: int, mask_arr: np.ndarray, frame_opacity: float,
                     color_hex: str, opacity: float, is_dark: bool,
                     cfg: dict, rect_idx: int) -> Image.Image:
    """Handwritten-style wavy underline below text."""
    full_x, full_y, full_w, full_h = region_box
    ucfg = cfg.get("underline", {})

    stroke_ratio = ucfg.get("stroke_ratio", 0.18)
    baseline_offset = ucfg.get("baseline_offset", 0.77)
    frequency = ucfg.get("frequency", 2.5)
    amplitude = ucfg.get("amplitude", 2.5)
    jitter_amt = ucfg.get("jitter", 1.0)
    tail_flick = ucfg.get("tail_flick", True)

    stroke_h = max(6, int(full_h * stroke_ratio))
    underline_y = full_y + int(full_h * baseline_offset) - stroke_h // 2
    canvas_h = frame.size[1]
    underline_y = max(0, min(canvas_h - stroke_h, underline_y))

    # Build full-width stroke, then crop to visible_w
    full_stroke = _build_stroke_mask(
        full_w, stroke_h, frequency, amplitude, jitter_amt,
        seed=rect_idx * 7 + 31, tail_flick=tail_flick)
    stroke_mask = full_stroke[:, :visible_w]

    # Apply 1-D wipe profile (feathered edge from the rounded-rect mask)
    wipe_1d = _wipe_profile_1d(mask_arr) / 255.0  # normalise to 0-1
    stroke_mask = stroke_mask * wipe_1d[np.newaxis, :]

    # Composite colored stroke
    r, g, b, _ = hex_to_rgba(color_hex, 1.0)
    color_layer = Image.new("RGBA", (visible_w, stroke_h), (r, g, b, 255))
    final_mask = (stroke_mask * frame_opacity).clip(0, 255).astype(np.uint8)
    color_layer.putalpha(Image.fromarray(final_mask))
    frame.alpha_composite(color_layer, (full_x, underline_y))
    return frame


# ─── Squiggly Mode ──────────────────────────────────────────────────────────

def _build_squiggly_mask(full_w: int, stroke_h: int, frequency: float,
                         amplitude: float, amp_variance: float,
                         seed: int) -> np.ndarray:
    """Generate a squiggly stroke with per-wave amplitude modulation."""
    rng = np.random.RandomState(seed)
    mask = np.zeros((stroke_h, full_w), dtype=np.float32)
    if full_w <= 0 or stroke_h <= 0:
        return mask

    center_y = stroke_h / 2.0
    xs = np.arange(full_w, dtype=np.float64)
    ts = xs / max(1, full_w - 1)
    phase = rng.uniform(0, 2 * math.pi)

    # Sine wave with per-wave amplitude modulation
    wave = np.sin(2 * math.pi * frequency * ts + phase)
    # Slow modulation envelope for irregular amplitude
    amp_mod = 1.0 + amp_variance * np.sin(2 * math.pi * 1.3 * ts + rng.uniform(0, 6))
    wave_y = amplitude * amp_mod * wave

    # Small jitter
    wave_y = wave_y + rng.uniform(-0.5, 0.5, size=full_w)

    y_centers = center_y + wave_y

    # Pressure taper (subtler than underline)
    base_thickness = max(1.0, stroke_h * 0.35)
    pressure = 0.7 + 0.3 * (1.0 - (2 * ts - 1) ** 2)
    thicknesses = base_thickness * pressure

    # Vectorised distance computation
    ys = np.arange(stroke_h, dtype=np.float64).reshape(-1, 1)
    y_c = y_centers.reshape(1, -1)
    half_t = (thicknesses / 2.0).reshape(1, -1)

    dist = np.abs(ys - y_c) / np.maximum(0.5, half_t)
    alpha = np.clip(1.0 - dist ** 2, 0.0, 1.0) * 255.0
    return alpha.astype(np.float32)


def render_squiggly(frame: Image.Image, region_box: tuple[int, int, int, int],
                    visible_w: int, mask_arr: np.ndarray, frame_opacity: float,
                    color_hex: str, opacity: float, is_dark: bool,
                    cfg: dict, rect_idx: int) -> Image.Image:
    """Squiggly wavy underline with pronounced oscillation."""
    full_x, full_y, full_w, full_h = region_box
    scfg = cfg.get("squiggly", {})

    stroke_ratio = scfg.get("stroke_ratio", 0.28)
    frequency = scfg.get("frequency", 5.0)
    amplitude = scfg.get("amplitude", 4.0)
    amp_variance = scfg.get("amplitude_variance", 0.4)

    stroke_h = max(8, int(full_h * stroke_ratio))
    # Position at same baseline as underline
    baseline_offset = scfg.get("baseline_offset", 0.77)
    underline_y = full_y + int(full_h * baseline_offset) - stroke_h // 2
    canvas_h = frame.size[1]
    underline_y = max(0, min(canvas_h - stroke_h, underline_y))

    full_stroke = _build_squiggly_mask(
        full_w, stroke_h, frequency, amplitude, amp_variance,
        seed=rect_idx * 7 + 31)
    stroke_mask = full_stroke[:, :visible_w]

    # Apply 1-D wipe profile
    wipe_1d = _wipe_profile_1d(mask_arr) / 255.0
    stroke_mask = stroke_mask * wipe_1d[np.newaxis, :]

    # Composite
    r, g, b, _ = hex_to_rgba(color_hex, 1.0)
    color_layer = Image.new("RGBA", (visible_w, stroke_h), (r, g, b, 255))
    final_mask = (stroke_mask * frame_opacity).clip(0, 255).astype(np.uint8)
    color_layer.putalpha(Image.fromarray(final_mask))
    frame.alpha_composite(color_layer, (full_x, underline_y))
    return frame


# ─── Crayon Mode ─────────────────────────────────────────────────────────────

# Cache crayon textures per rect to avoid regenerating every frame
_crayon_cache: dict[tuple, np.ndarray] = {}


def _create_rounded_mask(w: int, h: int, radius: int) -> Image.Image:
    """Create a rounded-rectangle alpha mask (2x render + downscale for AA)."""
    scale = 2
    sw, sh, sr = w * scale, h * scale, radius * scale
    mask_big = Image.new("L", (sw, sh), 0)
    draw = ImageDraw.Draw(mask_big)
    draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=255)
    return mask_big.resize((w, h), Image.LANCZOS)


def _build_crayon_texture(w: int, h: int, radius: int,
                          cfg: dict, seed: int) -> np.ndarray:
    """Generate a crayon/chalk texture mask: grain + hatching within rounded rect.

    Returns float32 array shape (h, w) with values 0-255.
    """
    ccfg = cfg.get("crayon", {})
    grain_density = ccfg.get("grain_density", 0.6)
    hatch_spacing = ccfg.get("hatch_spacing", 4)
    hatch_angle = ccfg.get("hatch_angle", 25)
    edge_roughness = ccfg.get("edge_roughness", 3.0)

    rng = np.random.RandomState(seed)

    # 1. Rounded rect boundary
    base = np.array(_create_rounded_mask(w, h, radius)).astype(np.float32) / 255.0

    # 2. Paper grain: blurred noise for clumpy wax-on-fiber texture
    grain = rng.random((h, w)).astype(np.float32)
    grain_pil = Image.fromarray((grain * 255).astype(np.uint8), "L")
    grain_pil = grain_pil.filter(ImageFilter.GaussianBlur(radius=1.3))
    grain = np.array(grain_pil).astype(np.float32) / 255.0
    # Non-linear boost for clumpy coverage
    grain = np.power(grain, 0.7)

    # 3. Diagonal hatching (directional stroke feel)
    angle_rad = math.radians(hatch_angle)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # Primary stroke direction
    proj = yy * math.cos(angle_rad) + xx * math.sin(angle_rad)
    stripe = (np.sin(proj * (2 * math.pi / max(1, hatch_spacing))
                     + rng.uniform(0, 2 * math.pi)) + 1.0) / 2.0
    # Secondary pass at slightly different angle for overlap
    angle2 = angle_rad + math.radians(rng.uniform(-12, 12))
    proj2 = yy * math.cos(angle2) + xx * math.sin(angle2)
    stripe2 = (np.sin(proj2 * (2 * math.pi / max(1, hatch_spacing + 1))
                      + rng.uniform(0, 2 * math.pi)) + 1.0) / 2.0
    strokes = np.maximum(stripe, stripe2)

    # 4. Combine grain + strokes
    texture = grain * 0.55 + strokes * 0.45
    # Boost contrast: push texture toward 0 or 1 for visible crayon strokes
    threshold = 1.0 - grain_density
    texture = np.where(texture > threshold,
                       0.6 + 0.4 * ((texture - threshold) / max(0.01, 1.0 - threshold)),
                       texture * 0.15)

    # 5. Rough edges: add noise to the boundary mask
    edge_noise = rng.normal(0, edge_roughness, size=(h, w)).astype(np.float32)
    edge_pil = Image.fromarray(
        np.clip((edge_noise + 128), 0, 255).astype(np.uint8), "L")
    edge_pil = edge_pil.filter(ImageFilter.GaussianBlur(radius=2.0))
    edge_factor = np.array(edge_pil).astype(np.float32) / 255.0
    rough_base = np.clip(base * (0.6 + 0.4 * edge_factor), 0, 1)

    result = rough_base * texture * 255.0
    return np.clip(result, 0, 255).astype(np.float32)


def render_crayon(frame: Image.Image, region_box: tuple[int, int, int, int],
                  visible_w: int, mask_arr: np.ndarray, frame_opacity: float,
                  color_hex: str, opacity: float, is_dark: bool,
                  cfg: dict, rect_idx: int) -> Image.Image:
    """Crayon/chalk textured highlight with grain and hatching."""
    full_x, full_y, full_w, full_h = region_box
    ccfg = cfg.get("crayon", {})
    opacity_boost = ccfg.get("base_opacity_boost", 1.3)

    radius = max(2, int(full_h * cfg.get("corner_radius", 0.22)))

    # Cache texture per rect geometry
    cache_key = (full_w, full_h, radius, rect_idx)
    if cache_key not in _crayon_cache:
        _crayon_cache[cache_key] = _build_crayon_texture(
            full_w, full_h, radius, cfg, seed=rect_idx * 13 + 59)
    full_texture = _crayon_cache[cache_key]

    # Crop to visible wipe width
    tex_crop = full_texture[:, :visible_w].copy()

    # Apply the wipe feathered edge from the rounded-rect mask
    # (mask_arr already has feather applied)
    wipe_factor = mask_arr / 255.0
    tex_crop *= wipe_factor

    # Composite coloured layer through textured mask
    r, g, b, _ = hex_to_rgba(color_hex, 1.0)
    color_layer = Image.new("RGBA", (visible_w, full_h), (r, g, b, 255))
    final_alpha = (tex_crop * frame_opacity * opacity_boost).clip(0, 255).astype(np.uint8)
    color_layer.putalpha(Image.fromarray(final_alpha))
    frame.alpha_composite(color_layer, (full_x, full_y))
    return frame


# ─── Registry ───────────────────────────────────────────────────────────────

MODE_REGISTRY = {
    "invert":    render_invert,
    "marker":    render_marker,
    "underline": render_underline,
    "squiggly":  render_squiggly,
    "crayon":    render_crayon,
}

ALL_MODES = list(MODE_REGISTRY.keys())
