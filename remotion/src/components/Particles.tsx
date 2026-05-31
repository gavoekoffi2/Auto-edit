import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/**
 * Particle system that renders floating shapes (circles, squares, triangles)
 * drifting and fading across the screen. Each particle follows a unique
 * trajectory based on its index, using sine/cosine for organic movement.
 */

type ParticleShape = "circle" | "square" | "triangle";

interface ParticlesProps {
  count: number;
  color: string;
  size: number;
  shapes?: ParticleShape[];
  direction?: "up" | "down";
  opacity?: number;
}

/** Deterministic pseudo-random based on seed (no external deps). */
const seededRandom = (seed: number): number => {
  const x = Math.sin(seed * 9301 + 49297) * 49297;
  return x - Math.floor(x);
};

const Triangle: React.FC<{ size: number; color: string }> = ({
  size,
  color,
}) => (
  <svg width={size} height={size} viewBox="0 0 20 20">
    <polygon points="10,2 18,18 2,18" fill={color} />
  </svg>
);

const ShapeRenderer: React.FC<{
  shape: ParticleShape;
  size: number;
  color: string;
}> = ({ shape, size, color }) => {
  if (shape === "triangle") {
    return <Triangle size={size} color={color} />;
  }
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: shape === "circle" ? "50%" : size * 0.15,
        backgroundColor: color,
      }}
    />
  );
};

const SingleParticle: React.FC<{
  index: number;
  count: number;
  color: string;
  size: number;
  shape: ParticleShape;
  direction: "up" | "down";
  baseOpacity: number;
}> = ({ index, count, color, size, shape, direction, baseOpacity }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();

  const r = seededRandom;
  const seed = index * 137;

  // Each particle gets unique properties derived from its index.
  const startX = r(seed + 1) * width;
  const startY = direction === "up" ? height + size * 2 : -size * 2;
  const speed = 0.4 + r(seed + 2) * 0.8;
  const wobbleFreq = 0.02 + r(seed + 3) * 0.04;
  const wobbleAmp = 20 + r(seed + 4) * 60;
  const particleSize = size * (0.5 + r(seed + 5) * 1.0);
  const phaseOffset = r(seed + 6) * Math.PI * 2;
  const delayFrames = r(seed + 7) * durationInFrames * 0.5;
  const rotation = r(seed + 8) * 360;
  const rotSpeed = (r(seed + 9) - 0.5) * 3;

  const progress = Math.max(0, frame - delayFrames);
  const travelDistance = direction === "up" ? -(height + size * 4) : height + size * 4;
  const y = startY + progress * speed * (travelDistance / durationInFrames) * 2;
  const x = startX + Math.sin(progress * wobbleFreq + phaseOffset) * wobbleAmp;
  const currentRotation = rotation + progress * rotSpeed;

  // Fade in at start, fade out near end or when leaving screen.
  const fadeIn = interpolate(progress, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 20, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const particleOpacity = fadeIn * fadeOut * baseOpacity * (0.3 + r(seed + 10) * 0.7);

  if (particleOpacity <= 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        opacity: particleOpacity,
        transform: `rotate(${currentRotation}deg)`,
        willChange: "transform, opacity",
        pointerEvents: "none",
      }}
    >
      <ShapeRenderer shape={shape} size={particleSize} color={color} />
    </div>
  );
};

export const Particles: React.FC<ParticlesProps> = ({
  count,
  color,
  size,
  shapes = ["circle", "square", "triangle"],
  direction = "up",
  opacity = 0.6,
}) => {
  const clampedCount = Math.min(30, Math.max(1, count));

  return (
    <AbsoluteFill style={{ overflow: "hidden", pointerEvents: "none" }}>
      {Array.from({ length: clampedCount }).map((_, i) => (
        <SingleParticle
          key={i}
          index={i}
          count={clampedCount}
          color={color}
          size={size}
          shape={shapes[i % shapes.length]}
          direction={direction}
          baseOpacity={opacity}
        />
      ))}
    </AbsoluteFill>
  );
};
