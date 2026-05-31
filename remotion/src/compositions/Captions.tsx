import React from "react";
import {
  AbsoluteFill,
  interpolate,
  Sequence,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AnimatedWord } from "../components/AnimatedWord";
import {
  CaptionsProps,
  CaptionSegment,
  CaptionStyle,
} from "../theme";
import { getFontFamily } from "../fonts";

/**
 * Transparent animated-caption overlay supporting multiple caption styles:
 * - classic: word-by-word pop-in with semi-transparent background
 * - karaoke: words appear white, current word highlights in accent (TikTok viral look)
 * - bounce: words bounce in from below with spring physics + rotation
 * - glow: neon glow effect with subtle pulse
 * - boxed: each word in its own colored box that scales in
 * - typewriter: characters appear left-to-right with blinking cursor
 */

const intensityMap = { subtle: 0.5, normal: 1, intense: 1.6 } as const;

/* ──────────────────────── Classic Caption Line ──────────────────────── */

const ClassicCaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
}> = ({ segment, brand, position, fontSize, fontStack }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

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
          fontFamily: fontStack,
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

/* ──────────────────────── Karaoke Caption Line ──────────────────────── */

const KaraokeCaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
  intensity: number;
}> = ({ segment, brand, position, fontSize, fontStack, intensity }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const words = segment.text.split(" ").filter(Boolean);
  const wordCount = words.length;

  // Each word gets an equal slice of the segment duration.
  const framesPerWord =
    wordCount > 0 ? durationInFrames / wordCount : durationInFrames;

  const exit = interpolate(
    frame,
    [durationInFrames - 6, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitOpacity = interpolate(exit, [0, 1], [1, 0]);

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
          maxWidth: "86%",
          textAlign: "center",
          fontFamily: fontStack,
          fontWeight: 900,
          fontSize,
          lineHeight: 1.2,
          padding: "0.3em 0.6em",
          borderRadius: 14,
          background: "rgba(0, 0, 0, 0.5)",
          backdropFilter: "blur(4px)",
        }}
      >
        {words.map((word, i) => {
          const wordStart = i * framesPerWord;
          const wordEnd = (i + 1) * framesPerWord;
          const isCurrentWord = frame >= wordStart && frame < wordEnd;
          const isPastWord = frame >= wordEnd;

          // Scale pop on the currently-spoken word.
          const wordScale = isCurrentWord
            ? 1 + 0.08 * intensity * Math.sin((frame - wordStart) * 0.4)
            : 1;

          const color = isCurrentWord
            ? brand.accentColor
            : isPastWord
              ? brand.accentColor + "aa"
              : brand.textColor;

          const textShadow = isCurrentWord
            ? `0 0 ${fontSize * 0.3}px ${brand.accentColor}88, 0 0 ${fontSize * 0.6}px ${brand.accentColor}44`
            : "0 2px 8px rgba(0,0,0,0.5)";

          // Fade each word in as it appears.
          const wordOpacity = interpolate(
            frame,
            [wordStart - 2, wordStart + 2],
            [0.4, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                marginRight: "0.25em",
                color,
                fontWeight: isCurrentWord ? 900 : 800,
                transform: `scale(${wordScale})`,
                textShadow,
                opacity: wordOpacity,
                willChange: "transform",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ──────────────────────── Bounce Caption Line ──────────────────────── */

const BounceCaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
  intensity: number;
}> = ({ segment, brand, position, fontSize, fontStack, intensity }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const words = segment.text.split(" ").filter(Boolean);

  const exit = interpolate(
    frame,
    [durationInFrames - 6, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitOpacity = interpolate(exit, [0, 1], [1, 0]);

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
          maxWidth: "86%",
          textAlign: "center",
          fontFamily: fontStack,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.3,
        }}
      >
        {words.map((word, i) => {
          const delay = i * Math.max(2, Math.round(4 / intensity));
          const s = spring({
            frame: frame - delay,
            fps,
            config: {
              damping: 8,
              stiffness: 160 * intensity,
              mass: 0.5,
            },
          });

          const translateY = interpolate(s, [0, 1], [80 * intensity, 0]);
          const opacity = interpolate(s, [0, 1], [0, 1], {
            extrapolateRight: "clamp",
          });
          const scale = interpolate(s, [0, 1], [0.5, 1]);
          const rotation = interpolate(s, [0, 1], [
            (i % 2 === 0 ? 12 : -12) * intensity,
            0,
          ]);

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                marginRight: "0.25em",
                color: brand.textColor,
                opacity,
                transform: `translateY(${translateY}px) scale(${scale}) rotate(${rotation}deg)`,
                textShadow: `0 4px 16px rgba(0,0,0,0.5), 0 0 8px ${brand.primaryColor}44`,
                willChange: "transform, opacity",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ──────────────────────── Glow Caption Line ──────────────────────── */

const GlowCaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
  intensity: number;
}> = ({ segment, brand, position, fontSize, fontStack, intensity }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const words = segment.text.split(" ").filter(Boolean);

  const exit = interpolate(
    frame,
    [durationInFrames - 6, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitOpacity = interpolate(exit, [0, 1], [1, 0]);

  const justify =
    position === "top"
      ? "flex-start"
      : position === "center"
        ? "center"
        : "flex-end";

  // Global glow pulse.
  const glowPulse = 1 + 0.25 * intensity * Math.sin(frame * 0.1);

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
          maxWidth: "86%",
          textAlign: "center",
          fontFamily: fontStack,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.2,
        }}
      >
        {words.map((word, i) => {
          const delay = i * Math.max(1, Math.round(3 / intensity));
          const s = spring({
            frame: frame - delay,
            fps,
            config: { damping: 14, stiffness: 100, mass: 0.6 },
          });
          const opacity = interpolate(s, [0, 1], [0, 1], {
            extrapolateRight: "clamp",
          });
          const scale = interpolate(s, [0, 1], [0.7, 1]);
          const blur = interpolate(s, [0, 1], [6, 0], {
            extrapolateRight: "clamp",
          });

          const glowSize = fontSize * 0.3 * glowPulse;

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                marginRight: "0.25em",
                color: brand.textColor,
                opacity,
                transform: `scale(${scale})`,
                filter: `blur(${blur}px)`,
                textShadow: [
                  `0 0 ${glowSize}px ${brand.accentColor}`,
                  `0 0 ${glowSize * 2}px ${brand.accentColor}88`,
                  `0 0 ${glowSize * 3}px ${brand.accentColor}44`,
                ].join(", "),
                willChange: "transform, opacity, filter",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ──────────────────────── Boxed Caption Line ──────────────────────── */

const BoxedCaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
  intensity: number;
}> = ({ segment, brand, position, fontSize, fontStack, intensity }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const words = segment.text.split(" ").filter(Boolean);

  const exit = interpolate(
    frame,
    [durationInFrames - 6, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitOpacity = interpolate(exit, [0, 1], [1, 0]);

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
          maxWidth: "90%",
          textAlign: "center",
          fontFamily: fontStack,
          fontWeight: 800,
          fontSize,
          lineHeight: 1.6,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: 6,
        }}
      >
        {words.map((word, i) => {
          const delay = i * Math.max(2, Math.round(3 / intensity));
          const s = spring({
            frame: frame - delay,
            fps,
            config: { damping: 12, stiffness: 130 * intensity, mass: 0.5 },
          });
          const scale = interpolate(s, [0, 1], [0, 1]);
          const opacity = interpolate(s, [0, 1], [0, 1], {
            extrapolateRight: "clamp",
          });

          const bgColor =
            i % 3 === 0
              ? brand.accentColor
              : i % 3 === 1
                ? brand.primaryColor
                : `${brand.accentColor}cc`;

          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                padding: "0.15em 0.4em",
                borderRadius: 8,
                background: bgColor,
                color: brand.textColor,
                opacity,
                transform: `scale(${scale})`,
                boxShadow: `0 4px 16px ${bgColor}55`,
                willChange: "transform, opacity",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ──────────────────────── Typewriter Caption Line ──────────────────── */

const TypewriterCaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
  intensity: number;
}> = ({ segment, brand, position, fontSize, intensity }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const text = segment.text;
  const totalChars = text.length;

  // Characters appear over most of the segment duration, leaving room for exit.
  const typingDuration = Math.max(1, durationInFrames - 10);
  const charsPerFrame = totalChars / typingDuration;
  const visibleChars = Math.min(
    totalChars,
    Math.floor(frame * charsPerFrame * intensity)
  );
  const visibleText = text.slice(0, visibleChars);

  // Blinking cursor.
  const cursorVisible =
    visibleChars < totalChars
      ? true
      : Math.floor(frame * 0.12) % 2 === 0;

  const exit = interpolate(
    frame,
    [durationInFrames - 6, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const exitOpacity = interpolate(exit, [0, 1], [1, 0]);

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
          maxWidth: "86%",
          textAlign: "center",
          fontFamily: `'Courier New', ui-monospace, monospace`,
          fontWeight: 700,
          fontSize,
          lineHeight: 1.3,
          color: brand.textColor,
          padding: "0.3em 0.6em",
          borderRadius: 12,
          background: "rgba(0, 0, 0, 0.6)",
          textShadow: `0 0 8px ${brand.primaryColor}66`,
        }}
      >
        {visibleText}
        <span
          style={{
            display: "inline-block",
            width: fontSize * 0.06,
            height: fontSize * 0.85,
            marginLeft: 2,
            background: brand.accentColor,
            opacity: cursorVisible ? 1 : 0,
            verticalAlign: "middle",
            boxShadow: `0 0 6px ${brand.accentColor}`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

/* ──────────────────────── Caption Line Router ──────────────────────── */

const CaptionLine: React.FC<{
  segment: CaptionSegment;
  brand: { primaryColor: string; accentColor: string; textColor: string };
  position: "bottom" | "center" | "top";
  fontSize: number;
  fontStack: string;
  captionStyle: CaptionStyle;
  intensity: number;
}> = (props) => {
  switch (props.captionStyle) {
    case "karaoke":
      return <KaraokeCaptionLine {...props} />;
    case "bounce":
      return <BounceCaptionLine {...props} />;
    case "glow":
      return <GlowCaptionLine {...props} />;
    case "boxed":
      return <BoxedCaptionLine {...props} />;
    case "typewriter":
      return <TypewriterCaptionLine {...props} />;
    case "classic":
    default:
      return <ClassicCaptionLine {...props} />;
  }
};

/* ──────────────────────── Main Captions Component ──────────────────── */

export const Captions: React.FC<CaptionsProps> = ({
  segments,
  position,
  fontScale,
  primaryColor,
  accentColor,
  textColor,
  fontFamily,
  captionStyle,
  animationIntensity,
}) => {
  const { fps, width } = useVideoConfig();
  const fontSize = Math.round(width * 0.045 * fontScale);
  const brand = { primaryColor, accentColor, textColor };
  const fontStack = getFontFamily(fontFamily);
  const intensity = intensityMap[animationIntensity];

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
              fontStack={fontStack}
              captionStyle={captionStyle}
              intensity={intensity}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
