const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

export async function apiGet<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const url = new URL(BASE_URL + path);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") url.searchParams.set(key, String(value));
  }
  const res = await fetch(url.toString());
  if (!res.ok) {
    if (res.status === 404) return null as T;
    const body = await res.text();
    throw new Error(`API ${res.status} ${path}: ${body}`);
  }
  return res.json();
}
