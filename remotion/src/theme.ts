import { z } from "zod";

/**
 * Shared visual theme + zod schemas for all AutoEdit compositions.
 * Every composition derives its dimensions and duration from the input props
 * (via calculateMetadata) so the backend can render motion graphics that match
 * any source video — vertical (TikTok), horizontal (YouTube), or square.
 */

export const FONT_FAMILY =
  "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif";

// Brand palette — overridable per render through props.
export const DEFAULT_PRIMARY = "#6366f1";
export const DEFAULT_ACCENT = "#ec4899";
export const DEFAULT_TEXT = "#ffffff";

export const fontFamilySchema = z
  .enum(["Inter", "Montserrat", "Poppins", "Oswald", "Bebas Neue", "Bangers"])
  .default("Inter");

export const captionStyleSchema = z
  .enum(["classic", "karaoke", "bounce", "glow", "boxed", "typewriter"])
  .default("karaoke");

export const animationIntensitySchema = z
  .enum(["subtle", "normal", "intense"])
  .default("normal");

export const particlesSchema = z.object({
  count: z.number().int().min(5).max(30).default(15),
  color: z.string().default(DEFAULT_ACCENT),
  size: z.number().positive().default(8),
});

export const dimensionsSchema = z.object({
  width: z.number().int().positive().default(1920),
  height: z.number().int().positive().default(1080),
  fps: z.number().positive().default(30),
});

export const brandSchema = z.object({
  primaryColor: z.string().default(DEFAULT_PRIMARY),
  accentColor: z.string().default(DEFAULT_ACCENT),
  textColor: z.string().default(DEFAULT_TEXT),
});

export const captionSegmentSchema = z.object({
  start: z.number(),
  end: z.number(),
  text: z.string(),
});

export type CaptionSegment = z.infer<typeof captionSegmentSchema>;

export const introSchema = dimensionsSchema.merge(brandSchema).extend({
  title: z.string().default("AutoEdit"),
  subtitle: z.string().default(""),
  durationInFrames: z.number().int().positive().default(75),
  fontFamily: fontFamilySchema,
  animationIntensity: animationIntensitySchema,
  particles: particlesSchema.default({}),
});

export const outroSchema = dimensionsSchema.merge(brandSchema).extend({
  title: z.string().default("Thanks for watching"),
  callToAction: z.string().default("Subscribe"),
  handle: z.string().default(""),
  durationInFrames: z.number().int().positive().default(90),
  fontFamily: fontFamilySchema,
  animationIntensity: animationIntensitySchema,
  particles: particlesSchema.default({}),
});

export const captionsSchema = dimensionsSchema.merge(brandSchema).extend({
  segments: z.array(captionSegmentSchema).default([]),
  position: z.enum(["bottom", "center", "top"]).default("bottom"),
  fontScale: z.number().positive().default(1),
  durationInFrames: z.number().int().positive().default(300),
  fontFamily: fontFamilySchema,
  captionStyle: captionStyleSchema,
  animationIntensity: animationIntensitySchema,
});

export const lowerThirdSchema = dimensionsSchema.merge(brandSchema).extend({
  name: z.string().default(""),
  role: z.string().default(""),
  appearAtFrame: z.number().int().nonnegative().default(0),
  durationInFrames: z.number().int().positive().default(150),
  fontFamily: fontFamilySchema,
});

export const transitionStyleSchema = z
  .enum(["swipe-left", "swipe-right", "circle-expand", "blur-fade", "glitch"])
  .default("swipe-left");

export const transitionWipeSchema = dimensionsSchema.merge(brandSchema).extend({
  style: transitionStyleSchema,
  durationInFrames: z.number().int().positive().default(20),
});

export type IntroProps = z.infer<typeof introSchema>;
export type OutroProps = z.infer<typeof outroSchema>;
export type CaptionsProps = z.infer<typeof captionsSchema>;
export type LowerThirdProps = z.infer<typeof lowerThirdSchema>;
export type TransitionWipeProps = z.infer<typeof transitionWipeSchema>;
export type FontFamily = z.infer<typeof fontFamilySchema>;
export type CaptionStyle = z.infer<typeof captionStyleSchema>;
export type AnimationIntensity = z.infer<typeof animationIntensitySchema>;
