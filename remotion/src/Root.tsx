import React from "react";
import { Composition } from "remotion";
import { Intro } from "./compositions/Intro";
import { Outro } from "./compositions/Outro";
import { Captions } from "./compositions/Captions";
import { LowerThird } from "./compositions/LowerThird";
import { TransitionWipe } from "./compositions/TransitionWipe";
import {
  captionsSchema,
  introSchema,
  lowerThirdSchema,
  outroSchema,
  transitionWipeSchema,
} from "./theme";

/**
 * All compositions derive width/height/fps/duration from their input props via
 * calculateMetadata, so the backend can render motion graphics that match any
 * source video (vertical, horizontal, square) by passing --props JSON.
 */
export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="Intro"
        component={Intro}
        schema={introSchema}
        defaultProps={introSchema.parse({})}
        durationInFrames={75}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames,
          fps: props.fps,
          width: props.width,
          height: props.height,
        })}
      />
      <Composition
        id="Outro"
        component={Outro}
        schema={outroSchema}
        defaultProps={outroSchema.parse({})}
        durationInFrames={90}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames,
          fps: props.fps,
          width: props.width,
          height: props.height,
        })}
      />
      <Composition
        id="Captions"
        component={Captions}
        schema={captionsSchema}
        defaultProps={captionsSchema.parse({})}
        durationInFrames={300}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames,
          fps: props.fps,
          width: props.width,
          height: props.height,
        })}
      />
      <Composition
        id="LowerThird"
        component={LowerThird}
        schema={lowerThirdSchema}
        defaultProps={lowerThirdSchema.parse({})}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames,
          fps: props.fps,
          width: props.width,
          height: props.height,
        })}
      />
      <Composition
        id="TransitionWipe"
        component={TransitionWipe}
        schema={transitionWipeSchema}
        defaultProps={transitionWipeSchema.parse({})}
        durationInFrames={20}
        fps={30}
        width={1920}
        height={1080}
        calculateMetadata={({ props }) => ({
          durationInFrames: props.durationInFrames,
          fps: props.fps,
          width: props.width,
          height: props.height,
        })}
      />
    </>
  );
};
