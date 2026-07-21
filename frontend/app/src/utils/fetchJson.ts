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
            const err = new Error(body?.error?.message ?? `HTTP ${res.status}`);
            (err as Error & { status: number }).status = res.status;
            throw err;
        }
        return res.json();
    } finally {
        clearTimeout(id);
    }
}
