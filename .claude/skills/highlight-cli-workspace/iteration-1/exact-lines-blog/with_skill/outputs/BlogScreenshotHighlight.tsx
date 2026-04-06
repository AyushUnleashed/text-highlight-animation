import React from 'react';
import {
  AbsoluteFill, Img, spring, useCurrentFrame, useVideoConfig, staticFile,
} from 'remotion';

const HIGHLIGHT_COLOR = '#ffffff';
const HIGHLIGHT_OPACITY = 1.0;
const BLEND_MODE = 'difference' as const;
const HIGHLIGHT_START_FRAME = 20;

interface HighlightLine {
  top: number;
  left: number;
  width: number;
  height: number;
  delay: number;
}

const HIGHLIGHT_LINES: HighlightLine[] = [
  { top: 20.11, left: 3.34, width: 67.6, height: 4.17, delay: 0 },
  { top: 24.71, left: 0.35, width: 97.41, height: 4.44, delay: 56 },
  { top: 28.09, left: 3.34, width: 94.1, height: 4.3, delay: 160 },
  { top: 31.21, left: 3.34, width: 20.0, height: 4.3, delay: 232 },
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
