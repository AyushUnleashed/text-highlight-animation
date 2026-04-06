import React from 'react';
import {
  AbsoluteFill, Img, spring, useCurrentFrame, useVideoConfig, staticFile,
} from 'remotion';

const HIGHLIGHT_COLOR = '#FFFFFF';
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

// Second paragraph: "Here's what the same money buys you in AI tools right now:"
// through the bullet list and "That's $80/1000s a month. For all four."
const HIGHLIGHT_LINES: HighlightLine[] = [
  // "Here's what the same money buys you in AI tools right now:"
  { top: 22.5, left: 5.0, width: 88.0, height: 3.2, delay: 0 },
  // "· Claude Pro, $20 a month."
  { top: 28.5, left: 5.0, width: 52.0, height: 3.2, delay: 8 },
  // "· Perplexity Pro, $20 a month."
  { top: 32.0, left: 5.0, width: 56.0, height: 3.2, delay: 16 },
  // "· Cursor, $20 a month."
  { top: 35.5, left: 5.0, width: 44.0, height: 3.2, delay: 24 },
  // "· ChatGPT Plus, $20 a month."
  { top: 39.0, left: 5.0, width: 54.0, height: 3.2, delay: 32 },
  // "That's $80/1000s a month. For all four."
  { top: 44.5, left: 5.0, width: 66.0, height: 3.2, delay: 40 },
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

export const TweetSampleHighlight: React.FC = () => {
  return (
    <AbsoluteFill
      style={{
        backgroundColor: '#000000',
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
          src={staticFile('tweet_sample.png')}
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
