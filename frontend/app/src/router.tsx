/**
 * @fileoverview 라우터. base(/wlkies) 처리는 TanStack Router 의 `basepath` 에 맡긴다.
 *
 * 예전에는 createBrowserHistory 의 parseLocation/createHref 를 직접 구현해 base 를 붙였다 벗겼다
 * 했는데, 그 시그니처가 라이브러리 타입과 맞지 않아(location 객체가 아니라 string 을 받는다)
 * 관리자 링크 URL 이 `/wlkiesundefinedfunction search()...` 처럼 깨져 나왔다.
 * `basepath` 를 쓰면 Link/navigate 가 알아서 base 를 붙이고 벗긴다.
 */
import { routeTree } from '@/routeTree.gen';
import { BASE_PATH } from '@/constants';
import { createRouter } from '@tanstack/react-router';

export const router = createRouter({
  routeTree,
  basepath: BASE_PATH,
  defaultPendingComponent: () => (
    <div className="flex items-center justify-center h-screen">로딩 중...</div>
  ),
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
