const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type RequestOptions = {
  token?: string | null;
  rawPath?: boolean;
  headers?: Record<string, string>;
};

async function parseError(res: Response): Promise<string> {
  try {
    const err = (await res.json()) as { detail?: string };
    return err.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function apiRequest<T>(
  method: string,
  path: string,
  body: unknown = null,
  options: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (options.token) headers.Authorization = `Bearer ${options.token}`;

  const url = options.rawPath ? path : `${API_BASE}${path}`;
  const opts: RequestInit = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(url, opts);
    if (!res.ok) throw new ApiError(await parseError(res), res.status);
    if (res.status === 204) return undefined as T;
    return res.json() as Promise<T>;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof TypeError) {
      throw new ApiError("Cannot reach the server. Is the backend running?");
    }
    throw e;
  }
}

export async function apiUpload<T>(
  path: string,
  formData: FormData,
  token: string | null
): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const res = await fetch(`${API_BASE}${path}`, { method: "POST", body: formData, headers });
    if (!res.ok) throw new ApiError(await parseError(res), res.status);
    return res.json() as Promise<T>;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof TypeError) {
      throw new ApiError("Cannot reach the server. Is the backend running?");
    }
    throw e;
  }
}

export const api = {
  get: <T>(path: string, token?: string | null) => apiRequest<T>("GET", path, null, { token }),
  post: <T>(path: string, body: unknown, token?: string | null) =>
    apiRequest<T>("POST", path, body, { token }),
  patch: <T>(path: string, body: unknown, token?: string | null) =>
    apiRequest<T>("PATCH", path, body, { token }),
  delete: <T = void>(path: string, token?: string | null) =>
    apiRequest<T>("DELETE", path, null, { token }),
  postRaw: <T>(path: string, body: unknown, token?: string | null) =>
    apiRequest<T>("POST", path, body, { rawPath: true, token }),
  getRaw: <T>(path: string, token?: string | null) =>
    apiRequest<T>("GET", path, null, { rawPath: true, token }),
  upload: apiUpload,
};
