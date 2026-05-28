import React from "react";
import { interpolate, spring, useVideoConfig } from "remotion";

/**
 * A single word that springs up + fades in. Used by captions and titles to
 * create a staggered "pop" reveal that reads as polished motion design rather
 * than a static text dump.
 */
export const AnimatedWord: React.FC<{
  children: React.ReactNode;
  frame: number;
  delay: number;
  color?: string;
}> = ({ children, frame, delay, color }) => {
  const { fps } = useVideoConfig();

  const enter = spring({
    frame: frame - delay,
    fps,
    config: { damping: 14, stiffness: 120, mass: 0.6 },
  });

  const translateY = interpolate(enter, [0, 1], [28, 0]);
  const opacity = interpolate(enter, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(enter, [0, 1], [0.85, 1]);

  return (
    <span
      style={{
        display: "inline-block",
        marginRight: "0.28em",
        color,
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        willChange: "transform, opacity",
      }}
    >
      {children}
    </span>
  );
};
