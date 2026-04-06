"""Generate a Remotion TSX component from highlight coords JSON.

Usage:
  python generate_component.py <coords.json> <image_filename> \
    [--output <path>] [--duration-seconds <float>] [--component-name <Name>]

Reads the JSON produced by detect_lines.py and writes a complete Remotion component.
Pure template fill — no LLM needed.

The image_filename is the basename (e.g., "screenshot.png") that lives in public/
and will be referenced via staticFile().
"""
import json
import re
import argparse
import math


PADDING_Y = 0.5
PADDING_X = 0.6
HIGHLIGHT_START_FRAME = 20
WIPE_FRAMES = 14
HOLD_FRAMES = 30
FPS = 30


def to_pascal_case(filename: str) -> str:
    """Convert a filename (without extension) to PascalCase + 'Highlight'."""
    name = filename.rsplit(".", 1)[0]
    parts = re.split(r"[-_\s]+", name)
    return "".join(p.capitalize() for p in parts) + "Highlight"


def compute_delays_auto(lines: list[dict]) -> list[int]:
    """Word-count-based staggered delays."""
    delays = []
    d = 0
    for line in lines:
        delays.append(d)
        d += max(5, line["word_count"] * 4)
    return delays


def compute_delays_fixed(lines: list[dict], total_seconds: float) -> list[int]:
    """Evenly distribute delays across a fixed total duration."""
    total_frames = int(total_seconds * FPS)
    available = total_frames - HIGHLIGHT_START_FRAME - WIPE_FRAMES - HOLD_FRAMES
    if available < 0:
        available = 0
    n = len(lines)
    if n <= 1:
        return [0] * n
    step = available / (n - 1)
    return [round(i * step) for i in range(n)]


def generate_tsx(coords_data: dict, image_filename: str,
                 component_name: str, duration_seconds: float | None) -> tuple[str, int]:
    """Generate TSX string and total duration in frames."""
    style = coords_data["style"]
    lines = coords_data["lines"]

    if duration_seconds:
        delays = compute_delays_fixed(lines, duration_seconds)
        total_frames = int(duration_seconds * FPS)
    else:
        delays = compute_delays_auto(lines)
        last_delay = delays[-1] if delays else 0
        total_frames = HIGHLIGHT_START_FRAME + last_delay + WIPE_FRAMES + HOLD_FRAMES

    line_entries = []
    for i, line in enumerate(lines):
        top = round(line["top_pct"] - PADDING_Y, 2)
        left = round(line["left_pct"] - PADDING_X, 2)
        width = round(line["width_pct"] + PADDING_X * 2, 2)
        height = round(line["height_pct"] + PADDING_Y * 2, 2)
        line_entries.append(
            f"  {{ top: {top}, left: {left}, width: {width}, "
            f"height: {height}, delay: {delays[i]} }}"
        )

    lines_array = ",\n".join(line_entries)
    bg_color = "#000000" if style["isDarkBg"] else "#f5f5f5"

    tsx = f'''import React from 'react';
import {{
  AbsoluteFill, Img, spring, useCurrentFrame, useVideoConfig, staticFile,
}} from 'remotion';

const HIGHLIGHT_COLOR = '{style["color"]}';
const HIGHLIGHT_OPACITY = {style["opacity"]};
const BLEND_MODE = '{style["blendMode"]}' as const;
const HIGHLIGHT_START_FRAME = {HIGHLIGHT_START_FRAME};

interface HighlightLine {{
  top: number;
  left: number;
  width: number;
  height: number;
  delay: number;
}}

const HIGHLIGHT_LINES: HighlightLine[] = [
{lines_array},
];

const AnimatedHighlight: React.FC<{{
  line: HighlightLine;
  globalDelay: number;
}}> = ({{line, globalDelay}}) => {{
  const frame = useCurrentFrame();
  const {{fps}} = useVideoConfig();

  const scaleX = spring({{
    fps,
    frame,
    config: {{damping: 200}},
    delay: globalDelay + line.delay,
    durationInFrames: {WIPE_FRAMES},
  }});

  return (
    <div
      style={{{{
        position: 'absolute',
        top: `${{line.top}}%`,
        left: `${{line.left}}%`,
        width: `${{line.width}}%`,
        height: `${{line.height}}%`,
        backgroundColor: HIGHLIGHT_COLOR,
        opacity: HIGHLIGHT_OPACITY,
        borderRadius: 3,
        transform: `scaleX(${{Math.min(1, scaleX)}})`,
        transformOrigin: 'left center',
        mixBlendMode: BLEND_MODE,
      }}}}
    />
  );
}};

export const {component_name}: React.FC = () => {{
  return (
    <AbsoluteFill
      style={{{{
        backgroundColor: '{bg_color}',
        alignItems: 'center',
        justifyContent: 'center',
      }}}}
    >
      <div style={{{{
        position: 'relative',
        width: '90%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}}}>
        <Img
          src={{staticFile('{image_filename}')}}
          style={{{{ width: '100%', borderRadius: 16 }}}}
        />
        {{HIGHLIGHT_LINES.map((line, i) => (
          <AnimatedHighlight
            key={{i}}
            line={{line}}
            globalDelay={{HIGHLIGHT_START_FRAME}}
          />
        ))}}
      </div>
    </AbsoluteFill>
  );
}};
'''
    return tsx, total_frames


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Remotion highlight component from OCR coordinates")
    parser.add_argument("coords_json", help="Path to coords JSON (default: .highlight/coords.json)",
                        nargs="?", default=".highlight/coords.json")
    parser.add_argument("image_filename", help="Image filename in public/ (e.g. 'photo.png')")
    parser.add_argument("--output", "-o", help="Output TSX file path", default=None)
    parser.add_argument("--duration-seconds", type=float, default=None,
                        help="Override total duration in seconds")
    parser.add_argument("--component-name", default=None,
                        help="Component name (default: derived from image filename)")
    args = parser.parse_args()

    with open(args.coords_json) as f:
        coords_data = json.load(f)

    component_name = args.component_name or to_pascal_case(args.image_filename)
    output_path = args.output or f"src/text-highlights/{component_name}.tsx"

    tsx, total_frames = generate_tsx(
        coords_data, args.image_filename, component_name, args.duration_seconds)

    with open(output_path, "w") as f:
        f.write(tsx)

    meta = {
        "component_name": component_name,
        "output_path": output_path,
        "duration_frames": total_frames,
        "fps": FPS,
        "duration_seconds": round(total_frames / FPS, 1),
    }
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
