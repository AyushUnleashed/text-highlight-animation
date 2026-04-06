import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  spring,
  staticFile,
  Img,
  AbsoluteFill,
} from "remotion";

/**
 * Highlights lines 5-8 of the blog screenshot (public/blog-screenshot.png).
 *
 * The image is 634x739. Lines 5-8 correspond to the "transcript" definition
 * paragraph:
 *   Line 5: "A transcript (also known as a trajectory) is the complete record of a trial"
 *   Line 6: "including outputs, tool calls, reasoning, intermediate results, and any other"
 *   Line 7: "relevant data. A transcript is often more than just the final answer—it's the"
 *   Line 8: "end-to-end run: containing all the calls to the API and all of the returned"
 *
 * Bounding boxes were estimated from the image layout.
 */

const IMAGE_WIDTH = 634;
const IMAGE_HEIGHT = 739;

interface HighlightLine {
  x: number;
  y: number;
  width: number;
  height: number;
}

// Bounding boxes for lines 5-8 of text in blog-screenshot.png
// These correspond to the 4 lines of the "transcript" definition paragraph
const highlightLines: HighlightLine[] = [
  // Line 5: "A transcript (also known as a trajectory) is the complete record of a trial"
  { x: 8, y: 228, width: 618, height: 18 },
  // Line 6: "including outputs, tool calls, reasoning, intermediate results, and any other"
  { x: 8, y: 248, width: 618, height: 18 },
  // Line 7: "relevant data. A transcript is often more than just the final answer—it's the"
  { x: 8, y: 268, width: 618, height: 18 },
  // Line 8: "end-to-end run: containing all the calls to the API and all of the returned"
  { x: 8, y: 288, width: 618, height: 18 },
];

const HIGHLIGHT_COLOR = "rgba(255, 230, 0, 0.35)";
const STAGGER_DELAY = 5; // frames between each line animation

export const BlogScreenshotHighlight: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#ffffff",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          position: "relative",
          width: IMAGE_WIDTH,
          height: IMAGE_HEIGHT,
        }}
      >
        <Img
          src={staticFile("blog-screenshot.png")}
          style={{
            width: IMAGE_WIDTH,
            height: IMAGE_HEIGHT,
            position: "absolute",
            top: 0,
            left: 0,
          }}
        />

        {/* Highlight overlays with animated wipe effect */}
        {highlightLines.map((line, index) => {
          const delay = index * STAGGER_DELAY;
          const progress = spring({
            frame: frame - delay,
            fps,
            config: {
              damping: 20,
              stiffness: 80,
              mass: 0.5,
            },
          });

          return (
            <div
              key={index}
              style={{
                position: "absolute",
                left: line.x,
                top: line.y,
                width: line.width,
                height: line.height,
                backgroundColor: HIGHLIGHT_COLOR,
                borderRadius: 2,
                // Wipe effect: clip from left to right
                clipPath: `inset(0 ${(1 - progress) * 100}% 0 0)`,
                pointerEvents: "none",
              }}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
