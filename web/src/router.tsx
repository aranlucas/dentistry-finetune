import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router';
import { z } from 'zod';
import { Folder } from './components/Folder';
import { Development } from './pages/Development';
import { Pilot } from './pages/Pilot';
import { Qa } from './pages/Qa';

// The run each sheet shows lives in the URL, so a view can be reloaded or linked.
const rootRoute = createRootRoute({ component: Folder });
const routes = [
  createRoute({ getParentRoute: () => rootRoute, path: '/', component: Pilot,
                validateSearch: z.object({ run: z.enum(['original', 'replay']).optional().catch(undefined) }) }),
  createRoute({ getParentRoute: () => rootRoute, path: '/qa', component: Qa,
                validateSearch: z.object({ run: z.enum(['long', 'short']).optional().catch(undefined) }) }),
  createRoute({ getParentRoute: () => rootRoute, path: '/development', component: Development,
                validateSearch: z.object({ run: z.string().max(80).optional().catch(undefined) }) }),
];

export const router = createRouter({ routeTree: rootRoute.addChildren(routes), scrollRestoration: true });

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}
