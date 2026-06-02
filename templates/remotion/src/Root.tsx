import { Composition } from "remotion";
import { IntroCard } from "./IntroCard";

const FPS = 30;
const VERTICAL = { width: 1080, height: 1920 };
const HORIZONTAL = { width: 1920, height: 1080 };

export const Root = () => {
  return (
    <>
      <Composition
        id="IntroCardVertical"
        component={IntroCard}
        durationInFrames={FPS * 2}
        fps={FPS}
        width={VERTICAL.width}
        height={VERTICAL.height}
        defaultProps={{
          title: "Lance ton business",
          subtitle: "AutoEdit",
        }}
      />
      <Composition
        id="IntroCardHorizontal"
        component={IntroCard}
        durationInFrames={FPS * 2}
        fps={FPS}
        width={HORIZONTAL.width}
        height={HORIZONTAL.height}
        defaultProps={{
          title: "Lance ton business",
          subtitle: "AutoEdit",
        }}
      />
    </>
  );
};
