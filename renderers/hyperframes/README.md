# AutoEdit HyperFrames renderer

This directory contains the HyperFrames integration blueprint for AutoEdit's premium motion-design renderer.

HyperFrames: https://github.com/heygen-com/hyperframes

## Why

Claude wants Captions.ai-like motion design: mixed B-roll appearances, light leaks, camera shutter effects, kinetic captions, and explanatory motion cards. FFmpeg stays as the robust production renderer, while HyperFrames gives us HTML/GSAP-based motion templates for richer versions.

## Local commands

```bash
node --version        # must be >= 22
npx hyperframes --help
npx hyperframes lint renderers/hyperframes/autoedit-premium
npx hyperframes render renderers/hyperframes/autoedit-premium -o /tmp/autoedit_hyperframes_test.mp4 --fps 30 --quality draft
```

## Integration strategy

1. Pipeline V2 continues to produce:
   - `premium_captions.ass`
   - B-roll cue timestamps
   - overlay cue timestamps
   - shutter/light timestamps
2. HyperFrames template consumes those cues as variables/assets.
3. HyperFrames renders a premium motion layer or complete motion composition.
4. FFmpeg composites the layer with the source video/audio until the full HyperFrames path is production-stable.

The current production code already mirrors this style in FFmpeg:
- 3 B-roll appearance styles: bottom slide, bottom pop, full-screen takeover;
- shutter SFX;
- flash + light leak overlays synced to the shutter events.
