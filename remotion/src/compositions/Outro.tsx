import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { FONT_FAMILY, OutroProps } from "../theme";

/**
 * End screen: title fades up, an animated pill-shaped call-to-action button
 * springs in and pulses, with an optional social handle underneath.
 */
export const Outro: React.FC<OutroProps> = ({
  title,
  callToAction,
  handle,
  primaryColor,
  accentColor,
  textColor,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();

  const titleSpring = spring({ frame, fps, config: { damping: 18 } });
  const titleOpacity = interpolate(titleSpring, [0, 1], [0, 1]);
  const titleY = interpolate(titleSpring, [0, 1], [40, 0]);

  const ctaSpring = spring({
    frame: frame - 14,
    fps,
    config: { damping: 11, stiffness: 110 },
  });
  const ctaScale = interpolate(ctaSpring, [0, 1], [0, 1]);

  // Subtle continuous pulse on the CTA.
  const pulse = 1 + 0.03 * Math.sin((frame / fps) * Math.PI * 2);

  const titleSize = Math.round(width * 0.055);

  return (
    <AbsoluteFill
      style={{
        fontFamily: FONT_FAMILY,
        background: `radial-gradient(circle at 50% 40%, #14142a 0%, #08080f 100%)`,
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontSize: titleSize,
          fontWeight: 800,
          color: textColor,
          opacity: titleOpacity,
          transform: `translateY(${titleY}px)`,
          textAlign: "center",
          maxWidth: "82%",
        }}
      >
        {title}
      </div>
      <div
        style={{
          marginTop: 40,
          transform: `scale(${ctaScale * pulse})`,
          padding: `${Math.round(titleSize * 0.32)}px ${Math.round(titleSize * 0.8)}px`,
          borderRadius: 9999,
          background: `linear-gradient(90deg, ${primaryColor}, ${accentColor})`,
          color: textColor,
          fontSize: Math.round(titleSize * 0.5),
          fontWeight: 700,
          boxShadow: `0 12px 40px ${accentColor}55`,
        }}
      >
        {callToAction}
      </div>
      {handle ? (
        <div
          style={{
            marginTop: 28,
            fontSize: Math.round(titleSize * 0.32),
            color: textColor,
            opacity: interpolate(frame, [24, 40], [0, 0.7], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            letterSpacing: "0.05em",
          }}
        >
          {handle}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
