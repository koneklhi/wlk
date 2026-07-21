import { routeTree } from '@/routeTree.gen';
import { createBrowserHistory, createRouter } from '@tanstack/react-router';

const BASE = '/wlkies';

export const router = createRouter({
  routeTree,
  defaultPendingComponent: () => <div className="flex items-center justify-center h-screen">로딩 중...</div>,
  history: createBrowserHistory({
    parseLocation: () => {
      const path = window.location.pathname;
      const stripped = path.startsWith(BASE) ? path.slice(BASE.length) || '/' : path;
      return {
        href: window.location.href,
        pathname: stripped,
        search: window.location.search,
        hash: window.location.hash,
        state: window.history.state,
      };
    },
    createHref: (location) => {
      const { pathname, search, hash } = location;
      const suffix = search + hash;
      return BASE + pathname + suffix;
    },
  }),
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
