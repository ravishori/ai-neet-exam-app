const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  fieldErrors: Record<string, string>;
  requestId: string | null;
  errorId: string | null;

  constructor(
    message: string,
    code: string,
    status: number,
    fieldErrors: Record<string, string> = {},
    requestId: string | null = null,
    errorId: string | null = null,
  ) {
    super(message);
    this.code = code;
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.requestId = requestId;
    this.errorId = errorId;
  }
}

type Envelope<T> = {
  success: boolean;
  data: T | null;
  meta: Record<string, unknown>;
  errors: { code: string; message: string; field?: string; errorId?: string }[];
  traceId?: string | null;
};

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

function newRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `REQ-${crypto.randomUUID().replace(/-/g, "").slice(0, 12).toUpperCase()}`;
  }
  return `REQ-${Date.now().toString(36).toUpperCase()}`;
}

async function request<T>(path: string, options: RequestInit = {}, _retried = false): Promise<Envelope<T>> {
  const method = (options.method ?? "GET").toUpperCase();
  const isMutating = method !== "GET" && method !== "HEAD";
  const headers = new Headers(options.headers);
  const requestId = headers.get("X-Request-Id") ?? newRequestId();
  headers.set("X-Request-Id", requestId);
  // FormData must NOT get an explicit Content-Type — the browser sets
  // multipart/form-data with the correct boundary itself; overriding it
  // (as every other mutating request does for its JSON body) breaks upload.
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (isMutating) {
    const csrf = readCookie("csrf_token");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      method,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_URL}. Check that the backend is running and NEXT_PUBLIC_API_URL is correct.`,
      "NETWORK_ERROR",
      0,
      {},
      requestId,
      null,
    );
  }

  const responseRequestId =
    response.headers.get("X-Request-Id") ?? response.headers.get("X-Trace-Id") ?? requestId;

  // Access token expired mid-session — refresh once, then retry the call.
  if (response.status === 401 && !_retried && path !== "/api/v1/auth/refresh" && path !== "/api/v1/auth/login") {
    const refreshed = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "X-Request-Id": requestId },
    });
    if (refreshed.ok) {
      return request<T>(path, options, true);
    }
  }

  let body: Envelope<T>;
  try {
    body = await response.json();
  } catch {
    throw new ApiError(
      `API returned a non-JSON response (${response.status}). Check NEXT_PUBLIC_API_URL (${API_URL}).`,
      "INVALID_RESPONSE",
      response.status,
      {},
      responseRequestId,
      response.headers.get("X-Error-Id"),
    );
  }
  if (!body.success) {
    const first = body.errors[0];
    const fieldErrors = Object.fromEntries(
      body.errors.filter((e) => e.field).map((e) => [e.field as string, e.message]),
    );
    const errorId =
      first?.errorId ??
      (typeof body.meta?.errorId === "string" ? body.meta.errorId : null) ??
      response.headers.get("X-Error-Id");
    throw new ApiError(
      first?.message ?? "Request failed",
      first?.code ?? "UNKNOWN_ERROR",
      response.status,
      fieldErrors,
      body.traceId ?? responseRequestId,
      errorId,
    );
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
