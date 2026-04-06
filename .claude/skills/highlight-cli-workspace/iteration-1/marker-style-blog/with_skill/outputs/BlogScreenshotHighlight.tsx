import React from 'react';
import {
  AbsoluteFill, Img, spring, useCurrentFrame, useVideoConfig, staticFile,
} from 'remotion';

const HIGHLIGHT_COLOR = '#FFE066';
const HIGHLIGHT_OPACITY = 0.5;
const BLEND_MODE = 'normal' as const;
const HIGHLIGHT_START_FRAME = 20;

interface HighlightLine {
  top: number;
  left: number;
  width: number;
  height: number;
  delay: number;
}

const HIGHLIGHT_LINES: HighlightLine[] = [
  { top: 53.09, left: 3.19, width: 92.21, height: 5.33, delay: 0 },
  { top: 56.33, left: 3.34, width: 97.26, height: 5.33, delay: 64 },
  { top: 60.93, left: 3.34, width: 81.01, height: 3.17, delay: 120 },
  { top: 64.18, left: 3.34, width: 37.48, height: 3.03, delay: 164 },
];

const AnimatedHighlight: React.FC<{
  line: HighlightLine;
  globalDelay: number;
}> = ({line, globalDelay}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const scaleX = spring({
    fps,
    frame,
    config: {damping: 200},
    delay: globalDelay + line.delay,
    durationInFrames: 14,
  });

  return (
    <div
      style={{
        position: 'absolute',
        top: `${line.top}%`,
        left: `${line.left}%`,
        width: `${line.width}%`,
        height: `${line.height}%`,
        backgroundColor: HIGHLIGHT_COLOR,
        opacity: HIGHLIGHT_OPACITY,
        borderRadius: 3,
        transform: `scaleX(${Math.min(1, scaleX)})`,
        transformOrigin: 'left center',
        mixBlendMode: BLEND_MODE,
      }}
    />
  );
};

export const BlogScreenshotHighlight: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#f5f5f5',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div style={{
        position: 'relative',
        width: '90%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <Img
          src={staticFile('blog-screenshot.png')}
          style={{ width: '100%', borderRadius: 16 }}
        />
        {HIGHLIGHT_LINES.map((line, i) => (
          <AnimatedHighlight
            key={i}
            line={line}
            globalDelay={HIGHLIGHT_START_FRAME}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};
