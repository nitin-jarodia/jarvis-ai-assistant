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

export class StreamAbortError extends Error {
  constructor() {
    super("Streaming request aborted.");
    this.name = "StreamAbortError";
  }
}

export type RequestOptions = {
  token?: string | null;
  rawPath?: boolean;
  headers?: Record<string, string>;
};

type StreamHandlers<TStart, TChunk, TFinal> = {
  onStart?: (payload: TStart) => void;
  onChunk?: (payload: TChunk) => void;
  onFinal?: (payload: TFinal) => void;
  signal?: AbortSignal;
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

function parseSseBlock(rawBlock: string): { event: string; data: string } | null {
  const block = rawBlock.replace(/\r/g, "").trim();
  if (!block) return null;
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  return { event, data: dataLines.join("\n") };
}

export async function apiStream<TStart, TChunk, TFinal>(
  path: string,
  body: unknown,
  token: string | null,
  handlers: StreamHandlers<TStart, TChunk, TFinal>
): Promise<TFinal> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal: handlers.signal,
    });
  } catch (e) {
    if ((e instanceof DOMException && e.name === "AbortError") || handlers.signal?.aborted) {
      throw new StreamAbortError();
    }
    if (e instanceof TypeError) {
      throw new ApiError("Cannot reach the server. Is the backend running?");
    }
    throw e;
  }
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  if (!res.body) throw new ApiError("Streaming is not supported by this browser.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalPayload: TFinal | undefined;

  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const normalized = buffer.replace(/\r\n/g, "\n");
      buffer = normalized;

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawBlock = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseSseBlock(rawBlock);
        if (parsed?.data) {
          const payload = JSON.parse(parsed.data) as TStart | TChunk | TFinal;
          if (parsed.event === "start") handlers.onStart?.(payload as TStart);
          else if (parsed.event === "chunk") handlers.onChunk?.(payload as TChunk);
          else if (parsed.event === "final") finalPayload = payload as TFinal;
        }
        boundary = buffer.indexOf("\n\n");
      }

      if (done) break;
    }
  } catch (e) {
    if ((e instanceof DOMException && e.name === "AbortError") || handlers.signal?.aborted) {
      throw new StreamAbortError();
    }
    throw e;
  }

  if (finalPayload === undefined) {
    throw new ApiError("The server ended the stream before sending a final response.");
  }
  handlers.onFinal?.(finalPayload);
  return finalPayload;
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
  stream: apiStream,
};
