import React from "react";
import {
  AbsoluteFill,
  Img,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  staticFile,
  Easing,
} from "remotion";

/**
 * Highlight overlay for the second paragraph of tweet_sample.png.
 *
 * The second paragraph is:
 *   "Here's what the same money buys you in AI tools right now:
 *    · Claude Pro, $20 a month.
 *    · Perplexity Pro, $20 a month.
 *    · Cursor, $20 a month.
 *    · ChatGPT Plus, $20 a month.
 *    That's $80/1,000 rupees a month. For all four."
 *
 * Image dimensions: 642 × 693 px
 * We scale the image to fill a 1920×1080 composition while preserving aspect ratio,
 * centering it, then position highlight rectangles relative to the image.
 */

// Bounding boxes for each line in the second paragraph.
// Coordinates are relative to the original 642×693 image.
const HIGHLIGHT_LINES: { x: number; y: number; width: number; height: number }[] = [
  // "Here's what the same money buys you in AI tools right now:"
  { x: 14, y: 152, width: 575, height: 22 },
  // "· Claude Pro, $20 a month."
  { x: 14, y: 184, width: 290, height: 20 },
  // "· Perplexity Pro, $20 a month."
  { x: 14, y: 210, width: 325, height: 20 },
  // "· Cursor, $20 a month."
  { x: 14, y: 236, width: 240, height: 20 },
  // "· ChatGPT Plus, $20 a month."
  { x: 14, y: 262, width: 310, height: 20 },
  // "That's $80/1,000 rupees a month. For all four."
  { x: 14, y: 292, width: 440, height: 22 },
];

const HIGHLIGHT_COLOR = "rgba(255, 230, 0, 0.35)";
const FRAMES_PER_LINE = 8; // stagger between lines
const LINE_ANIM_DURATION = 12; // frames for each line's wipe-in
const START_FRAME = 15; // delay before animation begins

export const TweetHighlight: React.FC = () => {
  const frame = useCurrentFrame();
  const { width: compW, height: compH } = useVideoConfig();

  // Original image size
  const imgW = 642;
  const imgH = 693;

  // Scale to fit composition (contain)
  const scale = Math.min(compW / imgW, compH / imgH);
  const scaledW = imgW * scale;
  const scaledH = imgH * scale;
  const offsetX = (compW - scaledW) / 2;
  const offsetY = (compH - scaledH) / 2;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Background image */}
      <Img
        src={staticFile("tweet_sample.png")}
        style={{
          position: "absolute",
          left: offsetX,
          top: offsetY,
          width: scaledW,
          height: scaledH,
        }}
      />

      {/* Highlight overlays */}
      {HIGHLIGHT_LINES.map((line, i) => {
        const lineStart = START_FRAME + i * FRAMES_PER_LINE;

        // Width progress: 0 → 1 wipe from left to right
        const widthProgress = interpolate(
          frame,
          [lineStart, lineStart + LINE_ANIM_DURATION],
          [0, 1],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.cubic),
          }
        );

        if (widthProgress <= 0) return null;

        // Map image-space coords to composition-space
        const rectX = offsetX + line.x * scale;
        const rectY = offsetY + line.y * scale;
        const rectW = line.width * scale * widthProgress;
        const rectH = line.height * scale;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: rectX,
              top: rectY,
              width: rectW,
              height: rectH,
              backgroundColor: HIGHLIGHT_COLOR,
              borderRadius: 3 * scale,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};
