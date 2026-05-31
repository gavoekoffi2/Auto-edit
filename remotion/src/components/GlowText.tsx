import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

/**
 * Animated text with a pulsing glow effect. The glow color matches the accent
 * color. Text fades in with a combined scale + blur effect using spring
 * animation for organic, polished motion.
 */
interface GlowTextProps {
  text: string;
  fontSize: number;
  color: string;
  glowColor: string;
  delay?: number;
  fontFamily?: string;
  fontWeight?: number;
  /** Intensity of the glow pulse (0-1 range). */
  glowIntensity?: number;
}

export const GlowText: React.FC<GlowTextProps> = ({
  text,
  fontSize,
  color,
  glowColor,
  delay = 0,
  fontFamily = "Inter, sans-serif",
  fontWeight = 800,
  glowIntensity = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enter = spring({
    frame: frame - delay,
    fps,
    config: { damping: 12, stiffness: 100, mass: 0.8 },
  });

  const opacity = interpolate(enter, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(enter, [0, 1], [0.6, 1]);
  const blur = interpolate(enter, [0, 1], [12, 0], {
    extrapolateRight: "clamp",
  });

  // Continuous glow pulse after the element has entered.
  const pulsePhase = Math.max(0, frame - delay - 10);
  const glowPulse =
    1 + 0.3 * glowIntensity * Math.sin(pulsePhase * 0.12);
  const glowRadius = fontSize * 0.4 * glowPulse * glowIntensity;
  const outerGlow = fontSize * 0.8 * glowPulse * glowIntensity;

  return (
    <div
      style={{
        display: "inline-block",
        fontSize,
        fontFamily,
        fontWeight,
        color,
        opacity,
        transform: `scale(${scale})`,
        filter: `blur(${blur}px)`,
        textShadow: [
          `0 0 ${glowRadius}px ${glowColor}`,
          `0 0 ${outerGlow}px ${glowColor}88`,
          `0 0 ${outerGlow * 1.5}px ${glowColor}44`,
        ].join(", "),
        willChange: "transform, opacity, filter",
      }}
    >
      {text}
    </div>
  );
};
