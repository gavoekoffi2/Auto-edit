import { Config } from "@remotion/cli/config";

// Rendering configuration for AutoEdit motion-design compositions.
// Overrides can be passed per-render on the CLI by the backend.
Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
Config.setConcurrency(2);

// Chromium runs headless inside the worker container. These flags make it
// reliable in a sandboxed/containerized environment without a GPU.
Config.setChromiumDisableWebSecurity(false);
Config.setChromiumHeadlessMode(true);
