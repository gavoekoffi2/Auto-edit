import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AnimatedWord } from "../components/AnimatedWord";
import { FONT_FAMILY, IntroProps } from "../theme";

/**
 * Branded animated intro: a gradient backdrop that drifts, a logo dot that
 * springs in, the title revealing word-by-word, and a subtitle that wipes up.
 * Ends with a clean fade so it concatenates seamlessly with the main footage.
 */
export const Intro: React.FC<IntroProps> = ({
  title,
  subtitle,
  primaryColor,
  accentColor,
  textColor,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width } = useVideoConfig();

  const bgShift = interpolate(frame, [0, durationInFrames], [0, 30]);

  const dot = spring({ frame, fps, config: { damping: 12, stiffness: 90 } });
  const dotScale = interpolate(dot, [0, 1], [0, 1]);

  // Fade the whole intro out over the last 12 frames.
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const words = title.split(" ").filter(Boolean);
  const titleSize = Math.round(width * 0.07);

  const subtitleReveal = spring({
    frame: frame - 18,
    fps,
    config: { damping: 16, stiffness: 80 },
  });

  return (
    <AbsoluteFill
      style={{
        opacity: fadeOut,
        fontFamily: FONT_FAMILY,
        background: `linear-gradient(${120 + bgShift}deg, ${primaryColor} 0%, #0f0f1a 55%, ${accentColor} 130%)`,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: Math.round(width * 0.04),
          height: Math.round(width * 0.04),
          borderRadius: "50%",
          marginBottom: 36,
          background: accentColor,
          transform: `scale(${dotScale})`,
          boxShadow: `0 0 ${width * 0.03}px ${accentColor}`,
        }}
      />
      <div
        style={{
          fontSize: titleSize,
          fontWeight: 800,
          color: textColor,
          letterSpacing: "-0.02em",
          textAlign: "center",
          maxWidth: "84%",
          lineHeight: 1.05,
        }}
      >
        {words.map((word, i) => (
          <AnimatedWord key={i} frame={frame} delay={i * 4} color={textColor}>
            {word}
          </AnimatedWord>
        ))}
      </div>
      {subtitle ? (
        <div
          style={{
            marginTop: 24,
            fontSize: Math.round(titleSize * 0.34),
            fontWeight: 500,
            color: textColor,
            opacity: interpolate(subtitleReveal, [0, 1], [0, 0.85]),
            transform: `translateY(${interpolate(subtitleReveal, [0, 1], [20, 0])}px)`,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          {subtitle}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
