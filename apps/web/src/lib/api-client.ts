const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  fieldErrors: Record<string, string>;

  constructor(message: string, code: string, status: number, fieldErrors: Record<string, string> = {}) {
    super(message);
    this.code = code;
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

type Envelope<T> = {
  success: boolean;
  data: T | null;
  meta: Record<string, unknown>;
  errors: { code: string; message: string; field?: string }[];
};

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function request<T>(path: string, options: RequestInit = {}, _retried = false): Promise<Envelope<T>> {
  const method = (options.method ?? "GET").toUpperCase();
  const isMutating = method !== "GET" && method !== "HEAD";
  const headers = new Headers(options.headers);
  // FormData must NOT get an explicit Content-Type — the browser sets
  // multipart/form-data with the correct boundary itself; overriding it
  // (as every other mutating request does for its JSON body) breaks upload.
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (isMutating) {
    const csrf = readCookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });

  // Access token expired mid-session — refresh once, then retry the call.
  if (response.status === 401 && !_retried && path !== "/api/v1/auth/refresh" && path !== "/api/v1/auth/login") {
    const refreshed = await fetch(`${API_URL}/api/v1/auth/refresh`, { method: "POST", credentials: "include" });
    if (refreshed.ok) {
      return request<T>(path, options, true);
    }
  }

  const body: Envelope<T> = await response.json();
  if (!body.success) {
    const first = body.errors[0];
    const fieldErrors = Object.fromEntries(
      body.errors.filter((e) => e.field).map((e) => [e.field as string, e.message])
    );
    throw new ApiError(first?.message ?? "Request failed", first?.code ?? "UNKNOWN_ERROR", response.status, fieldErrors);
  }
  return body;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path).then((body) => body.data as T),
  getFull: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data ? JSON.stringify(data) : undefined }).then((body) => body.data as T),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }).then((body) => body.data as T),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: data ? JSON.stringify(data) : undefined }).then((body) => body.data as T),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: data ? JSON.stringify(data) : undefined }).then((body) => body.data as T),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }).then((body) => body.data as T),
};
