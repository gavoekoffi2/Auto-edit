import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { LowerThirdProps } from "../theme";
import { getFontFamily } from "../fonts";

/**
 * Transparent lower-third name/role banner that wipes in from the left and
 * retracts at the end. Rendered with alpha and composited by the backend.
 */

export const LowerThird: React.FC<LowerThirdProps> = ({
  name,
  role,
  primaryColor,
  accentColor,
  textColor,
  fontFamily,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const fontStack = getFontFamily(fontFamily);

  const enter = spring({ frame, fps, config: { damping: 16, stiffness: 90 } });
  const exit = spring({
    frame: frame - (durationInFrames - 14),
    fps,
    config: { damping: 18 },
  });
  const reveal = enter - exit;

  const clipWidth = interpolate(reveal, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "flex-start",
        padding: Math.round(height * 0.08),
        fontFamily: fontStack,
      }}
    >
      <div
        style={{
          overflow: "hidden",
          maxWidth: `${clipWidth * 70}%`,
          borderLeft: `${Math.round(width * 0.006)}px solid ${accentColor}`,
        }}
      >
        <div
          style={{
            background: `linear-gradient(90deg, ${primaryColor}ee, ${primaryColor}00)`,
            padding: `${Math.round(height * 0.012)}px ${Math.round(width * 0.03)}px`,
            whiteSpace: "nowrap",
          }}
        >
          <div
            style={{
              fontSize: Math.round(width * 0.028),
              fontWeight: 800,
              color: textColor,
            }}
          >
            {name}
          </div>
          {role ? (
            <div
              style={{
                fontSize: Math.round(width * 0.016),
                fontWeight: 500,
                color: textColor,
                opacity: 0.85,
                letterSpacing: "0.04em",
              }}
            >
              {role}
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
