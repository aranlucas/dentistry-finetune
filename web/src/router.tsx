import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { z } from "zod";
import { Folder } from "./components/folder";
import { Development } from "./pages/development";
import { Pilot } from "./pages/pilot";
import { Qa } from "./pages/qa";

// The run each sheet shows lives in the URL, so a view can be reloaded or linked.
const rootRoute = createRootRoute({ component: Folder });

const pilotRun = z.enum(["original", "replay"]);

const qaRun = z.enum(["long", "short"]);

const developmentRun = z.string().max(80);

type PilotSearch = { run?: z.infer<typeof pilotRun> };

type QaSearch = { run?: z.infer<typeof qaRun> };

type DevelopmentSearch = { run?: z.infer<typeof developmentRun> };

const routes = [
  createRoute({
    getParentRoute: () => rootRoute,
    path: "/",
    component: Pilot,
    validateSearch: (search): PilotSearch => ({
      run: pilotRun.safeParse(search.run).data,
    }),
  }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: "/qa",
    component: Qa,
    validateSearch: (search): QaSearch => ({
      run: qaRun.safeParse(search.run).data,
    }),
  }),
  createRoute({
    getParentRoute: () => rootRoute,
    path: "/development",
    component: Development,
    validateSearch: (search): DevelopmentSearch => ({
      run: developmentRun.safeParse(search.run).data,
    }),
  }),
];

export const router = createRouter({
  routeTree: rootRoute.addChildren(routes),
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
