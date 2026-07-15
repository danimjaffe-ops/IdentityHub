const API_BASE = "/api";

export class ApiRequestError extends Error {
  status: number;
  error: string;
  details?: Record<string, string[]>;

  constructor(status: number, error: string, message: string, details?: Record<string, string[]>) {
    super(message);
    this.status = status;
    this.error = error;
    this.details = details;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: "unknown", message: res.statusText }));
    // Any 401 (including an expired session) means the client-side auth state
    // is stale — signal listeners so the SPA can drop the user to /login.
    if (res.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("auth:unauthorized", { detail: body.error }));
    }
    throw new ApiRequestError(res.status, body.error || "unknown", body.message || res.statusText, body.details);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
