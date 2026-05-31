import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Particles } from "../components/Particles";
import { IntroProps } from "../theme";

/**
 * Professional animated intro with:
 * - Background particles drifting upward
 * - Animated gradient that shifts colors over time
 * - Kinetic typography with per-letter animation
 * - Glowing sweep line
 * - Brand dot with overshoot bounce
 * - Subtitle with motion blur slide-in
 * - Fade-in from black / fade-out to seamless transition
 */

const FONT_MAP: Record<string, string> = {
  Inter: "Inter, 'Helvetica Neue', Arial, sans-serif",
  Montserrat: "Montserrat, 'Helvetica Neue', Arial, sans-serif",
  Poppins: "Poppins, sans-serif",
  Oswald: "Oswald, sans-serif",
  "Bebas Neue": "'Bebas Neue', Impact, sans-serif",
  Bangers: "Bangers, cursive, sans-serif",
};

/** Intensity multiplier for animation parameters. */
const intensityMap = { subtle: 0.5, normal: 1, intense: 1.6 } as const;

const KineticLetter: React.FC<{
  char: string;
  index: number;
  totalLetters: number;
  frame: number;
  fps: number;
  fontSize: number;
  color: string;
  accentColor: string;
  intensity: number;
}> = ({ char, index, frame, fps, fontSize, color, accentColor, intensity }) => {
  const delay = index * Math.max(1, Math.round(2 / intensity));

  const enter = spring({
    frame: frame - delay,
    fps,
    config: {
      damping: 10 + 4 * (1 - intensity * 0.3),
      stiffness: 140 * intensity,
      mass: 0.5,
    },
  });

  const translateY = interpolate(enter, [0, 1], [60 * intensity, 0]);
  const opacity = interpolate(enter, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(enter, [0, 1], [0.3, 1]);
  const rotateZ = interpolate(enter, [0, 1], [15 * intensity, 0]);

  // Subtle color flash on entry.
  const colorFlash = interpolate(enter, [0.5, 0.8, 1], [0, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const letterColor =
    colorFlash > 0.3 ? accentColor : color;

  if (char === " ") {
    return (
      <span style={{ display: "inline-block", width: fontSize * 0.3 }} />
    );
  }

  return (
    <span
      style={{
        display: "inline-block",
        fontSize,
        fontWeight: 900,
        color: letterColor,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale}) rotate(${rotateZ}deg)`,
        willChange: "transform, opacity",
        textShadow: `0 0 ${fontSize * 0.15}px ${accentColor}66`,
      }}
    >
      {char}
    </span>
  );
};

const SweepLine: React.FC<{
  frame: number;
  fps: number;
  width: number;
  height: number;
  accentColor: string;
  intensity: number;
}> = ({ frame, fps, width, height, accentColor, intensity }) => {
  const sweep = spring({
    frame: frame - 8,
    fps,
    config: { damping: 20, stiffness: 60 * intensity, mass: 1 },
  });

  const lineX = interpolate(sweep, [0, 1], [-width * 0.2, width * 1.2]);
  const lineOpacity = interpolate(
    sweep,
    [0, 0.2, 0.8, 1],
    [0, 0.9, 0.9, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        top: height * 0.48,
        left: lineX,
        width: width * 0.15,
        height: 3,
        background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)`,
        opacity: lineOpacity,
        boxShadow: `0 0 20px ${accentColor}, 0 0 60px ${accentColor}66`,
        pointerEvents: "none",
      }}
    />
  );
};

export const Intro: React.FC<IntroProps> = ({
  title,
  subtitle,
  primaryColor,
  accentColor,
  textColor,
  fontFamily,
  animationIntensity,
  particles,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const intensity = intensityMap[animationIntensity];
  const fontStack = FONT_MAP[fontFamily] || FONT_MAP.Inter;

  // --- Fade in from black ---
  const fadeIn = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // --- Fade out over the last 15 frames ---
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const masterOpacity = fadeIn * fadeOut;

  // --- Animated gradient background ---
  const gradAngle = interpolate(frame, [0, durationInFrames], [120, 200]);
  const gradShift = interpolate(frame, [0, durationInFrames], [0, 40]);

  // --- Brand dot with overshoot bounce ---
  const dotSpring = spring({
    frame: frame - 4,
    fps,
    config: { damping: 8, stiffness: 120 * intensity, mass: 0.6, overshootClamping: false },
  });
  const dotScale = interpolate(dotSpring, [0, 1], [0, 1]);
  const dotSize = Math.round(width * 0.04);
  const dotGlow = dotSize * (0.6 + 0.2 * Math.sin(frame * 0.15));

  // --- Title ---
  const titleSize = Math.round(width * 0.07);
  const letters = title.split("");

  // --- Subtitle ---
  const subtitleDelay = Math.min(
    letters.length * 2 + 10,
    durationInFrames - 20
  );
  const subtitleSpring = spring({
    frame: frame - subtitleDelay,
    fps,
    config: { damping: 14, stiffness: 80 * intensity },
  });
  const subtitleOpacity = interpolate(subtitleSpring, [0, 1], [0, 0.9], {
    extrapolateRight: "clamp",
  });
  const subtitleY = interpolate(subtitleSpring, [0, 1], [40 * intensity, 0]);
  const subtitleBlur = interpolate(subtitleSpring, [0, 1], [8, 0], {
    extrapolateRight: "clamp",
  });

  // --- Floating decorative shapes ---
  const decorOp = interpolate(frame, [10, 25], [0, 0.15], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        opacity: masterOpacity,
        fontFamily: fontStack,
        background: `linear-gradient(${gradAngle}deg, ${primaryColor} ${-10 + gradShift}%, #0f0f1a 55%, ${accentColor} ${130 - gradShift}%)`,
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      {/* Background particles */}
      <Particles
        count={particles.count}
        color={particles.color}
        size={particles.size}
        direction="up"
        opacity={0.4}
      />

      {/* Sweep line */}
      <SweepLine
        frame={frame}
        fps={fps}
        width={width}
        height={height}
        accentColor={accentColor}
        intensity={intensity}
      />

      {/* Floating decorative rings */}
      <div
        style={{
          position: "absolute",
          top: height * 0.15,
          right: width * 0.1,
          width: width * 0.12,
          height: width * 0.12,
          borderRadius: "50%",
          border: `2px solid ${accentColor}`,
          opacity: decorOp * fadeOut,
          transform: `scale(${0.8 + 0.2 * Math.sin(frame * 0.05)}) rotate(${frame * 0.5}deg)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: height * 0.2,
          left: width * 0.08,
          width: width * 0.06,
          height: width * 0.06,
          borderRadius: "50%",
          border: `2px solid ${primaryColor}`,
          opacity: decorOp * fadeOut * 0.7,
          transform: `scale(${0.9 + 0.1 * Math.cos(frame * 0.07)})`,
        }}
      />

      {/* Brand dot with overshoot */}
      <div
        style={{
          width: dotSize,
          height: dotSize,
          borderRadius: "50%",
          marginBottom: 36,
          background: `radial-gradient(circle at 35% 35%, ${accentColor}, ${primaryColor})`,
          transform: `scale(${dotScale})`,
          boxShadow: `0 0 ${dotGlow}px ${accentColor}, 0 0 ${dotGlow * 2}px ${accentColor}55`,
        }}
      />

      {/* Title with kinetic per-letter animation */}
      <div
        style={{
          textAlign: "center",
          maxWidth: "84%",
          lineHeight: 1.1,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
        }}
      >
        {letters.map((char, i) => (
          <KineticLetter
            key={i}
            char={char}
            index={i}
            totalLetters={letters.length}
            frame={frame}
            fps={fps}
            fontSize={titleSize}
            color={textColor}
            accentColor={accentColor}
            intensity={intensity}
          />
        ))}
      </div>

      {/* Subtitle with motion blur slide-in */}
      {subtitle ? (
        <div
          style={{
            marginTop: 24,
            fontSize: Math.round(titleSize * 0.34),
            fontWeight: 500,
            color: textColor,
            opacity: subtitleOpacity,
            transform: `translateY(${subtitleY}px)`,
            filter: `blur(${subtitleBlur}px)`,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            textShadow: `0 0 12px ${primaryColor}88`,
            willChange: "transform, opacity, filter",
          }}
        >
          {subtitle}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
