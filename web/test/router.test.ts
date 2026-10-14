import { createMemoryHistory } from "@tanstack/react-router";
import { describe, expect, it } from "vitest";
import { router } from "@/router";

const routes = [
  { label: "pilot", path: "/", allowed: ["original", "replay"] },
  { label: "QA", path: "/qa", allowed: ["long", "short"] },
  { label: "development", path: "/development", allowed: ["reviewed-run", ""] },
];

const invalidRuns = ["42", "null", "true", '%5B"unexpected"%5D', "x".repeat(81)];

describe("route search validation", () => {
  for (const route of routes) {
    it.each(route.allowed)(`${route.label} preserves the allowed run %j`, (run) => {
      router.update({
        history: createMemoryHistory({
          initialEntries: [`${route.path}?run=${encodeURIComponent(run)}`],
        }),
      });

      const page = router.matchRoutes(router.latestLocation).at(-1);

      expect(page?.search).toHaveProperty("run", run);
    });

    it.each(invalidRuns)(`${route.label} clears invalid run %s after router merging`, (run) => {
      router.update({
        history: createMemoryHistory({ initialEntries: [`${route.path}?run=${run}`] }),
      });

      const page = router.matchRoutes(router.latestLocation).at(-1);

      expect(page?.search).toHaveProperty("run");
      expect(page?.search).toMatchObject({ run: undefined });
    });

    it(`${route.label} keeps the default run optional`, () => {
      router.update({ history: createMemoryHistory({ initialEntries: [route.path] }) });

      const page = router.matchRoutes(router.latestLocation).at(-1);

      expect(page?.search).toHaveProperty("run");
      expect(page?.search).toMatchObject({ run: undefined });
    });
  }

  it.each(["/", "/qa"])("clears an unknown named run on %s", (path) => {
    router.update({ history: createMemoryHistory({ initialEntries: [`${path}?run=bogus`] }) });

    const page = router.matchRoutes(router.latestLocation).at(-1);

    expect(page?.search).toHaveProperty("run");
    expect(page?.search).toMatchObject({ run: undefined });
  });
});
