import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Particles } from "../components/Particles";
import { GlowText } from "../components/GlowText";
import { OutroProps } from "../theme";

/**
 * Professional end screen with:
 * - Particle effects in background
 * - Animated gradient background that shifts
 * - Title with glow effect
 * - CTA button with shine/shimmer animation
 * - Social handle slides in with spring
 * - Floating decorative elements
 */

const FONT_MAP: Record<string, string> = {
  Inter: "Inter, 'Helvetica Neue', Arial, sans-serif",
  Montserrat: "Montserrat, 'Helvetica Neue', Arial, sans-serif",
  Poppins: "Poppins, sans-serif",
  Oswald: "Oswald, sans-serif",
  "Bebas Neue": "'Bebas Neue', Impact, sans-serif",
  Bangers: "Bangers, cursive, sans-serif",
};

const intensityMap = { subtle: 0.5, normal: 1, intense: 1.6 } as const;

/** Animated floating decorative shape. */
const FloatingShape: React.FC<{
  x: number;
  y: number;
  size: number;
  color: string;
  frame: number;
  index: number;
  shape: "circle" | "square" | "diamond";
}> = ({ x, y, size, color, frame, index, shape }) => {
  const wobble = Math.sin(frame * 0.04 + index * 2.1) * 12;
  const floatY = Math.cos(frame * 0.03 + index * 1.7) * 8;
  const rotation = frame * (0.3 + index * 0.2);
  const pulse = 0.8 + 0.2 * Math.sin(frame * 0.08 + index);

  const opacity = interpolate(frame, [0, 20], [0, 0.2], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const borderRadius =
    shape === "circle" ? "50%" : shape === "diamond" ? "4px" : "3px";
  const extraRotation = shape === "diamond" ? 45 : 0;

  return (
    <div
      style={{
        position: "absolute",
        left: x + wobble,
        top: y + floatY,
        width: size * pulse,
        height: size * pulse,
        borderRadius,
        border: `1.5px solid ${color}`,
        opacity,
        transform: `rotate(${rotation + extraRotation}deg)`,
        pointerEvents: "none",
      }}
    />
  );
};

export const Outro: React.FC<OutroProps> = ({
  title,
  callToAction,
  handle,
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
  const titleSize = Math.round(width * 0.055);

  // --- Animated gradient background ---
  const gradAngle = interpolate(frame, [0, durationInFrames], [160, 220]);
  const gradShift = interpolate(frame, [0, durationInFrames], [0, 25]);

  // --- Fade out ---
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 15, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // --- CTA button ---
  const ctaSpring = spring({
    frame: frame - 14,
    fps,
    config: { damping: 10, stiffness: 110 * intensity, mass: 0.7 },
  });
  const ctaScale = interpolate(ctaSpring, [0, 1], [0, 1]);
  const pulse = 1 + 0.03 * Math.sin((frame / fps) * Math.PI * 2);

  // Shimmer sweep across CTA button.
  const shimmerX = interpolate(
    frame % Math.round(fps * 2.5),
    [0, Math.round(fps * 2.5)],
    [-150, 350]
  );

  // --- Handle spring ---
  const handleSpring = spring({
    frame: frame - 24,
    fps,
    config: { damping: 14, stiffness: 80 * intensity },
  });
  const handleOpacity = interpolate(handleSpring, [0, 1], [0, 0.8], {
    extrapolateRight: "clamp",
  });
  const handleY = interpolate(handleSpring, [0, 1], [30, 0]);

  // --- Floating decorative shapes ---
  const shapes: Array<{
    x: number;
    y: number;
    size: number;
    shape: "circle" | "square" | "diamond";
  }> = [
    { x: width * 0.08, y: height * 0.12, size: 40, shape: "circle" },
    { x: width * 0.85, y: height * 0.18, size: 28, shape: "diamond" },
    { x: width * 0.12, y: height * 0.78, size: 35, shape: "square" },
    { x: width * 0.9, y: height * 0.72, size: 22, shape: "circle" },
    { x: width * 0.5, y: height * 0.08, size: 18, shape: "diamond" },
    { x: width * 0.75, y: height * 0.85, size: 30, shape: "square" },
  ];

  return (
    <AbsoluteFill
      style={{
        fontFamily: fontStack,
        background: `linear-gradient(${gradAngle}deg, #0a0a18 ${gradShift}%, #14142a 50%, #0a0a18 ${100 - gradShift}%)`,
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeOut,
        overflow: "hidden",
      }}
    >
      {/* Background particles */}
      <Particles
        count={particles.count}
        color={particles.color}
        size={particles.size}
        direction="up"
        opacity={0.3}
      />

      {/* Floating decorative shapes */}
      {shapes.map((s, i) => (
        <FloatingShape
          key={i}
          x={s.x}
          y={s.y}
          size={s.size}
          color={i % 2 === 0 ? accentColor : primaryColor}
          frame={frame}
          index={i}
          shape={s.shape}
        />
      ))}

      {/* Ambient glow behind title */}
      <div
        style={{
          position: "absolute",
          width: width * 0.5,
          height: width * 0.5,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${primaryColor}22 0%, transparent 70%)`,
          pointerEvents: "none",
        }}
      />

      {/* Title with glow */}
      <GlowText
        text={title}
        fontSize={titleSize}
        color={textColor}
        glowColor={accentColor}
        fontFamily={fontStack}
        fontWeight={800}
        delay={0}
        glowIntensity={intensity * 0.7}
      />

      {/* CTA button with shimmer */}
      <div
        style={{
          marginTop: 40,
          transform: `scale(${ctaScale * pulse})`,
          position: "relative",
          overflow: "hidden",
          padding: `${Math.round(titleSize * 0.32)}px ${Math.round(titleSize * 0.8)}px`,
          borderRadius: 9999,
          background: `linear-gradient(90deg, ${primaryColor}, ${accentColor})`,
          color: textColor,
          fontSize: Math.round(titleSize * 0.5),
          fontWeight: 700,
          boxShadow: `0 12px 40px ${accentColor}55, 0 0 30px ${primaryColor}33`,
        }}
      >
        {callToAction}
        {/* Shimmer overlay */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: `linear-gradient(105deg, transparent 30%, rgba(255,255,255,0.25) 50%, transparent 70%)`,
            transform: `translateX(${shimmerX}%)`,
            pointerEvents: "none",
          }}
        />
      </div>

      {/* Social handle */}
      {handle ? (
        <div
          style={{
            marginTop: 28,
            fontSize: Math.round(titleSize * 0.32),
            color: textColor,
            opacity: handleOpacity,
            transform: `translateY(${handleY}px)`,
            letterSpacing: "0.05em",
            textShadow: `0 0 8px ${primaryColor}66`,
            willChange: "transform, opacity",
          }}
        >
          {handle}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
