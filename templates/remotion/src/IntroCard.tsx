import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export interface IntroCardProps {
  title: string;
  subtitle?: string;
}

export const IntroCard: React.FC<IntroCardProps> = ({ title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const opacity = interpolate(frame, [0, fps * 0.3, fps * 1.7, fps * 2], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateY = interpolate(frame, [0, fps * 0.5], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background:
          "radial-gradient(ellipse at center, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.95) 80%)",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Inter, system-ui, -apple-system, sans-serif",
        color: "white",
        textAlign: "center",
        padding: 80,
      }}
    >
      <div style={{ opacity, transform: `translateY(${translateY}px)` }}>
        <h1
          style={{
            fontSize: 110,
            fontWeight: 800,
            lineHeight: 1.05,
            margin: 0,
            letterSpacing: -2,
          }}
        >
          {title}
        </h1>
        {subtitle ? (
          <p
            style={{
              fontSize: 44,
              opacity: 0.85,
              marginTop: 32,
              fontWeight: 500,
            }}
          >
            {subtitle}
          </p>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
