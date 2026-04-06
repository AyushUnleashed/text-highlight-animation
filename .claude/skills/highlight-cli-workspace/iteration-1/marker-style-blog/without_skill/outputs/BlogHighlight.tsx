import React from "react";
import {
  AbsoluteFill,
  Img,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from "remotion";

/**
 * BlogHighlight - Yellow marker-style highlight animation on blog-screenshot.png
 *
 * Highlights lines 13-16 of the detected text with a yellow marker/highlighter
 * style (semi-transparent yellow, like a real highlighter pen).
 *
 * Image dimensions: 634 x 739
 * Lines 13-16 correspond to (counting non-blank text lines):
 *   13: "— that is, whether there is something new in the environment to observe or"
 *   14: "whether the output is the direct text from the agent, or whether the judgment"
 *   15: "is made based on text written to a scoreable location."
 *   16: "An evaluation harness is the infrastructure that runs eval end-to-end. It"
 */

// Image natural dimensions
const IMG_WIDTH = 634;
const IMG_HEIGHT = 739;

// Bounding boxes for lines 13-16 (estimated from visual inspection)
// Format: { x, y, width, height } in image-native pixels
const LINE_HIGHLIGHTS = [
  {
    // Line 13: "— that is, whether there is something new in the environment to observe or"
    x: 8,
    y: 445,
    width: 610,
    height: 20,
  },
  {
    // Line 14: "whether the output is the direct text from the agent, or whether the judgment"
    x: 8,
    y: 467,
    width: 615,
    height: 20,
  },
  {
    // Line 15: "is made based on text written to a scoreable location."
    x: 8,
    y: 489,
    width: 378,
    height: 20,
  },
  {
    // Line 16: "An evaluation harness is the infrastructure that runs eval end-to-end. It"
    x: 8,
    y: 522,
    width: 585,
    height: 20,
  },
];

// Marker style constants
const MARKER_COLOR = "rgba(255, 230, 0, 0.45)"; // Semi-transparent yellow
const MARKER_HEIGHT_SCALE = 1.3; // Slightly taller than text for realistic marker feel

export const BlogHighlight: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scale factor to fit image into the composition
  const COMP_WIDTH = 1920;
  const COMP_HEIGHT = 1080;
  const scale = Math.min(COMP_WIDTH / IMG_WIDTH, COMP_HEIGHT / IMG_HEIGHT);
  const offsetX = (COMP_WIDTH - IMG_WIDTH * scale) / 2;
  const offsetY = (COMP_HEIGHT - IMG_HEIGHT * scale) / 2;

  return (
    <AbsoluteFill style={{ backgroundColor: "#f5f5f0" }}>
      {/* Blog screenshot image, centered */}
      <div
        style={{
          position: "absolute",
          left: offsetX,
          top: offsetY,
          width: IMG_WIDTH * scale,
          height: IMG_HEIGHT * scale,
        }}
      >
        <Img
          src={staticFile("blog-screenshot.png")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "contain",
          }}
        />

        {/* Yellow marker highlight overlays */}
        {LINE_HIGHLIGHTS.map((line, index) => {
          // Stagger each line's animation by 8 frames
          const delay = index * 8;
          const startFrame = 15 + delay;

          // Animate the width of the highlight like a marker being drawn
          const progress = spring({
            frame: frame - startFrame,
            fps,
            config: {
              damping: 50,
              stiffness: 80,
              mass: 0.5,
            },
          });

          // Only render if animation has started
          if (frame < startFrame) return null;

          const highlightHeight = line.height * MARKER_HEIGHT_SCALE;
          const yOffset = (highlightHeight - line.height) / 2;

          return (
            <div
              key={index}
              style={{
                position: "absolute",
                left: line.x * scale,
                top: (line.y - yOffset) * scale,
                width: line.width * scale * progress,
                height: highlightHeight * scale,
                backgroundColor: MARKER_COLOR,
                borderRadius: 3 * scale,
                // Slight rotation for hand-drawn feel
                transform: `rotate(${-0.3 + index * 0.15}deg)`,
                // Marker texture: slightly uneven edges
                clipPath:
                  "polygon(0% 8%, 2% 0%, 98% 2%, 100% 10%, 100% 88%, 97% 100%, 3% 98%, 0% 92%)",
                pointerEvents: "none",
              }}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
