import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { TransitionWipeProps } from "../theme";

/**
 * Transition overlay rendered with alpha, designed to be inserted between
 * scenes. Supports multiple wipe styles using brand colors.
 *
 * Styles:
 * - swipe-left: Solid color panel sweeps from right to left
 * - swipe-right: Solid color panel sweeps from left to right
 * - circle-expand: Circle expands from center
 * - blur-fade: Fade through blur
 * - glitch: Digital glitch bands
 */

/** Deterministic pseudo-random for glitch bands. */
const seededRandom = (seed: number): number => {
  const x = Math.sin(seed * 9301 + 49297) * 49297;
  return x - Math.floor(x);
};

/* ──────── Swipe Transition ──────── */

const SwipeTransition: React.FC<{
  direction: "left" | "right";
  primaryColor: string;
  accentColor: string;
}> = ({ direction, primaryColor, accentColor }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();

  const mid = durationInFrames / 2;

  // Sweep in then sweep out.
  const enterProgress = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 120, mass: 0.8 },
  });
  const exitProgress = spring({
    frame: frame - mid,
    fps,
    config: { damping: 18, stiffness: 120, mass: 0.8 },
  });

  const sign = direction === "left" ? -1 : 1;
  const enterX = interpolate(enterProgress, [0, 1], [sign * width, 0]);
  const exitX = interpolate(exitProgress, [0, 1], [0, -sign * width]);
  const x = frame < mid ? enterX : exitX;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          background: `linear-gradient(${direction === "left" ? 90 : 270}deg, ${primaryColor}, ${accentColor})`,
          transform: `translateX(${x}px)`,
          willChange: "transform",
        }}
      />
      {/* Leading edge glow */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          width: 40,
          left: direction === "left" ? undefined : 0,
          right: direction === "left" ? 0 : undefined,
          background: `linear-gradient(${direction === "left" ? 270 : 90}deg, transparent, ${accentColor}88)`,
          transform: `translateX(${x}px)`,
          filter: "blur(8px)",
        }}
      />
    </AbsoluteFill>
  );
};

/* ──────── Circle Expand Transition ──────── */

const CircleExpandTransition: React.FC<{
  primaryColor: string;
  accentColor: string;
}> = ({ primaryColor, accentColor }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const mid = durationInFrames / 2;
  const maxRadius = Math.sqrt(width * width + height * height) / 2;

  const enterScale = spring({
    frame,
    fps,
    config: { damping: 14, stiffness: 80, mass: 0.8 },
  });
  const exitScale = spring({
    frame: frame - mid,
    fps,
    config: { damping: 14, stiffness: 80, mass: 0.8 },
  });

  const radius = frame < mid
    ? interpolate(enterScale, [0, 1], [0, maxRadius])
    : maxRadius;

  // For exit: create a growing hole by using a radial-gradient mask.
  const holeRadius = frame >= mid
    ? interpolate(exitScale, [0, 1], [0, maxRadius])
    : 0;

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          width: radius * 2,
          height: radius * 2,
          borderRadius: "50%",
          transform: "translate(-50%, -50%)",
          background: `radial-gradient(circle, ${accentColor} 0%, ${primaryColor} 100%)`,
          WebkitMaskImage:
            holeRadius > 0
              ? `radial-gradient(circle, transparent ${holeRadius}px, black ${holeRadius + 2}px)`
              : undefined,
          maskImage:
            holeRadius > 0
              ? `radial-gradient(circle, transparent ${holeRadius}px, black ${holeRadius + 2}px)`
              : undefined,
        }}
      />
    </AbsoluteFill>
  );
};

/* ──────── Blur Fade Transition ──────── */

const BlurFadeTransition: React.FC<{
  primaryColor: string;
  accentColor: string;
}> = ({ primaryColor, accentColor }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const mid = durationInFrames / 2;

  const opacity = frame < mid
    ? interpolate(frame, [0, mid], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : interpolate(frame, [mid, durationInFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  const blurAmount = frame < mid
    ? interpolate(frame, [0, mid], [0, 20], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : interpolate(frame, [mid, durationInFrames], [20, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(135deg, ${primaryColor}ee, ${accentColor}ee)`,
        opacity,
        backdropFilter: `blur(${blurAmount}px)`,
        filter: `blur(${blurAmount * 0.3}px)`,
      }}
    />
  );
};

/* ──────── Glitch Transition ──────── */

const GlitchTransition: React.FC<{
  primaryColor: string;
  accentColor: string;
}> = ({ primaryColor, accentColor }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, height } = useVideoConfig();

  const mid = durationInFrames / 2;

  // Overall intensity envelope.
  const envelope = frame < mid
    ? interpolate(frame, [0, mid], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : interpolate(frame, [mid, durationInFrames], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  // Generate glitch bands.
  const bandCount = 12;
  const bands = Array.from({ length: bandCount }).map((_, i) => {
    const seed = i * 37 + frame * 7;
    const y = seededRandom(seed) * height;
    const bandHeight = 4 + seededRandom(seed + 1) * 30;
    const offsetX = (seededRandom(seed + 2) - 0.5) * 80;
    const color = i % 2 === 0 ? primaryColor : accentColor;
    const opacity = seededRandom(seed + 3) * envelope;

    return (
      <div
        key={i}
        style={{
          position: "absolute",
          top: y,
          left: 0,
          right: 0,
          height: bandHeight,
          background: color,
          opacity,
          transform: `translateX(${offsetX}px)`,
          mixBlendMode: "screen",
        }}
      />
    );
  });

  // Flash overlay.
  const flash = envelope > 0.8 ? (envelope - 0.8) * 5 : 0;

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {bands}
      <AbsoluteFill
        style={{
          background: "white",
          opacity: flash * 0.3,
          mixBlendMode: "overlay",
        }}
      />
    </AbsoluteFill>
  );
};

/* ──────── Main TransitionWipe ──────── */

export const TransitionWipe: React.FC<TransitionWipeProps> = ({
  style,
  primaryColor,
  accentColor,
}) => {
  switch (style) {
    case "swipe-left":
      return (
        <SwipeTransition
          direction="left"
          primaryColor={primaryColor}
          accentColor={accentColor}
        />
      );
    case "swipe-right":
      return (
        <SwipeTransition
          direction="right"
          primaryColor={primaryColor}
          accentColor={accentColor}
        />
      );
    case "circle-expand":
      return (
        <CircleExpandTransition
          primaryColor={primaryColor}
          accentColor={accentColor}
        />
      );
    case "blur-fade":
      return (
        <BlurFadeTransition
          primaryColor={primaryColor}
          accentColor={accentColor}
        />
      );
    case "glitch":
      return (
        <GlitchTransition
          primaryColor={primaryColor}
          accentColor={accentColor}
        />
      );
    default:
      return (
        <SwipeTransition
          direction="left"
          primaryColor={primaryColor}
          accentColor={accentColor}
        />
      );
  }
};
