import "./index.css";
import { Composition } from "remotion";
import { BlogScreenshotHighlight } from "./text-highlights/BlogScreenshotHighlight";

// Each <Composition> is an entry in the sidebar!

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="BlogScreenshotHighlight"
        component={BlogScreenshotHighlight}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1080}
      />
    </>
  );
};
