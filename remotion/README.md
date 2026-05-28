# AutoEdit — Remotion Motion Design

React/Remotion compositions that add professional motion graphics to AutoEdit
exports: animated branded **intros**, **outros / end-screens**, word-by-word
**animated captions** (transparent overlay), and **lower-thirds**.

The Python worker (`backend/app/processing/motion.py`) drives these
compositions with `npx remotion render`, passing per-video props as JSON, then
composites the results onto the source footage with ffmpeg.

## Compositions

| ID            | Output             | Purpose                                    |
| ------------- | ------------------ | ------------------------------------------ |
| `Intro`       | opaque mp4         | Branded animated opener                    |
| `Outro`       | opaque mp4         | End-screen with animated call-to-action    |
| `Captions`    | ProRes 4444 (alpha)| Animated subtitle overlay from transcript  |
| `LowerThird`  | ProRes 4444 (alpha)| Name/role banner                           |

All compositions read `width`, `height`, `fps`, and `durationInFrames` from
their input props via `calculateMetadata`, so they automatically match any
source aspect ratio.

## Local development

```bash
cd remotion
npm install
npm run preview      # opens Remotion Studio
```

## Rendering manually

```bash
npx remotion render src/index.ts Intro out/intro.mp4 \
  --props='{"title":"My Channel","width":1080,"height":1920,"fps":30,"durationInFrames":75}'
```

The backend calls this automatically as part of the editing pipeline when
`motion_design` is enabled in the job parameters or mode preset.
