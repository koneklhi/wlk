/**
 * @fileoverview JSON API 요청 — GET/POST/DELETE (5초 timeout)
 */
export async function fetchJson<T>(url: string, init?: RequestInit, timeoutMs = 5000): Promise<T> {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const res = await fetch(url, {
            headers: { 'Content-Type': 'application/json', ...init?.headers },
            ...init,
            signal: controller.signal,
        });
        if (!res.ok) {
            const body = await res.json().catch(() => null);
            // FastAPI HTTPException 은 `{detail: "..."}` 로 온다 — 이걸 안 읽으면 서버가
            // 정성껏 쓴 한국어 안내가 전부 `HTTP 503` 으로만 보인다.
            const err = new Error(body?.error?.message ?? body?.detail ?? `HTTP ${res.status}`);
            (err as Error & { status: number }).status = res.status;
            throw err;
        }
        return res.json();
    } finally {
        clearTimeout(id);
    }
}
