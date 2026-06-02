import type { FontFamily } from "./theme";

/**
 * Font loading for AutoEdit compositions.
 *
 * CRITICAL: in a headless Remotion render (Chromium under Node) the host has
 * NO system fonts beyond a default sans-serif. A bare CSS font string like
 * "Bangers, cursive" therefore silently falls back to the default — the user's
 * font choice would do nothing in the final video.
 *
 * We bundle the woff2 files in `public/fonts/` and register them with
 * `@remotion/fonts`, which holds the render (delayRender) until each font is
 * ready. Because the files are LOCAL (staticFile), rendering never depends on
 * reaching an external CDN — a network blip can't strip the motion design.
 */

type WeightFile = { weight: string; file: string };

const FONT_FILES: Record<FontFamily, WeightFile[]> = {
  Inter: [
    { weight: "400", file: "Inter-400.woff2" },
    { weight: "700", file: "Inter-700.woff2" },
    { weight: "800", file: "Inter-800.woff2" },
  ],
  Montserrat: [
    { weight: "500", file: "Montserrat-500.woff2" },
    { weight: "700", file: "Montserrat-700.woff2" },
    { weight: "800", file: "Montserrat-800.woff2" },
  ],
  Poppins: [
    { weight: "500", file: "Poppins-500.woff2" },
    { weight: "700", file: "Poppins-700.woff2" },
    { weight: "800", file: "Poppins-800.woff2" },
  ],
  Oswald: [
    { weight: "500", file: "Oswald-500.woff2" },
    { weight: "700", file: "Oswald-700.woff2" },
  ],
  "Bebas Neue": [{ weight: "400", file: "BebasNeue-400.woff2" }],
  Bangers: [{ weight: "400", file: "Bangers-400.woff2" }],
};

export const FONT_FACE_CSS = Object.entries(FONT_FILES)
  .flatMap(([family, weights]) =>
    weights.map(
      ({ weight, file }) => `
@font-face {
  font-family: '${family}';
  src: url('/fonts/${file}') format('woff2');
  font-weight: ${weight};
  font-style: normal;
  font-display: swap;
}`
    )
  )
  .join("\n");

const GENERIC_FALLBACK = "'Helvetica Neue', Arial, sans-serif";

/**
 * Resolve a font name (from composition props) to a render-safe CSS
 * font-family string. Falls back to Inter for unknown names.
 */
export const getFontFamily = (name?: string | null): string => {
  if (name && name in FONT_FILES) {
    return `'${name}', ${GENERIC_FALLBACK}`;
  }
  return `'Inter', ${GENERIC_FALLBACK}`;
};

/** Display fonts (Bangers, Bebas Neue) look best uppercased for impact captions. */
export const isDisplayFont = (name?: string | null): boolean =>
  name === "Bangers" || name === "Bebas Neue";
