import type { E2EConfig } from "e2e";
import { web } from "@e2e-dev/web";

export default {
  tests: "e2e/**/*.e2e.ts",
  targets: [
    {
      engine: web(),
      app: {
        url: "http://127.0.0.1:8765",
        command: { executable: "python", args: ["../src/server.py"], reuseExisting: false },
      },
    },
  ],
  workers: 1,
  retries: 0,
  trace: "retain-on-failure",
  video: "retain-on-failure",
} satisfies E2EConfig;
