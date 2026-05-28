import React from "react";
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AnimatedWord } from "../components/AnimatedWord";
import { CaptionsProps, CaptionSegment, FONT_FAMILY } from "../theme";

/**
 * Transparent animated-caption overlay. The backend renders this composition
 * with an alpha-capable codec (ProRes 4444) so it can be composited on top of
 * the user's footage with ffmpeg. Each transcript segment is shown only during
 * its [start, end] window, with words staggering in and a soft slide-out.
 */
const CaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
}> = ({ segment, brand, position, fontSize }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Slide + fade the line out over its final 6 frames.
  const exit = interpolate(
    frame,
    [durationInFrames - 6, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitY = interpolate(exit, [0, 1], [0, -18]);
  const exitOpacity = interpolate(exit, [0, 1], [1, 0]);

  const words = segment.text.split(" ").filter(Boolean);

  const justify =
    position === "top"
      ? "flex-start"
      : position === "center"
        ? "center"
        : "flex-end";

  return (
    <AbsoluteFill
      style={{
        justifyContent: justify,
        alignItems: "center",
        padding: position === "center" ? 0 : "8%",
        opacity: exitOpacity,
      }}
    >
      <div
        style={{
          transform: `translateY(${exitY}px)`,
          maxWidth: "86%",
          textAlign: "center",
          fontFamily: FONT_FAMILY,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.15,
          color: brand.textColor,
          padding: "0.35em 0.7em",
          borderRadius: 18,
          background: "rgba(8, 8, 16, 0.55)",
          backdropFilter: "blur(2px)",
          textShadow: "0 2px 12px rgba(0,0,0,0.6)",
          boxShadow: `0 0 0 3px ${brand.primaryColor}55`,
        }}
      >
        {words.map((word, i) => (
          <AnimatedWord
            key={i}
            frame={frame}
            delay={i * Math.max(1, Math.round(fps / 12))}
            color={i % 7 === 6 ? brand.accentColor : brand.textColor}
          >
            {word}
          </AnimatedWord>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const Captions: React.FC<CaptionsProps> = ({
  segments,
  position,
  fontScale,
  primaryColor,
  accentColor,
  textColor,
}) => {
  const { fps, width } = useVideoConfig();
  const fontSize = Math.round(width * 0.045 * fontScale);
  const brand = { primaryColor, accentColor, textColor };

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {segments.map((segment, i) => {
        const from = Math.max(0, Math.round(segment.start * fps));
        const frames = Math.max(
          1,
          Math.round((segment.end - segment.start) * fps)
        );
        return (
          <Sequence key={i} from={from} durationInFrames={frames}>
            <CaptionLine
              segment={segment}
              brand={brand}
              position={position}
              fontSize={fontSize}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
