import type { components } from "./generated";

export type ErrorResponse = components["schemas"]["ErrorResponse"];
export type ErrorDetails = components["schemas"]["ErrorDetails"];

export class ApiError extends Error {
  public code: string;
  public details?: ErrorDetails;
  public requestId: string;
  public status: number;

  constructor(status: number, errorPayload: ErrorResponse["error"]) {
    super(errorPayload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = errorPayload.code;
    this.details = errorPayload.details;
    this.requestId = errorPayload.requestId;
  }
}

export class NetworkError extends Error {
  public method: string;
  public url: string;

  constructor(message: string, method: string, url: string) {
    super(message);
    this.name = "NetworkError";
    this.method = method;
    this.url = url;
  }
}

export class MutationUnknownError extends NetworkError {
  public idempotencyKey?: string;
  public operationId?: string;

  constructor(message: string, method: string, url: string, idempotencyKey?: string, operationId?: string) {
    super(message, method, url);
    this.name = "MutationUnknownError";
    this.idempotencyKey = idempotencyKey;
    this.operationId = operationId;
  }
}

export interface FetchOptions extends RequestInit {
  params?: Record<string, string>;
}

export async function apiClient<T>(url: string, options: FetchOptions = {}): Promise<T> {
  const { params, ...init } = options;
  
  let targetUrl = url;
  if (params) {
    const searchParams = new URLSearchParams(params);
    targetUrl += `?${searchParams.toString()}`;
  }

  const fetchOptions: RequestInit = {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers || {})
    },
    credentials: "same-origin",
  };

  if (fetchOptions.method === "DELETE" || !fetchOptions.body) {
    const headers = new Headers(fetchOptions.headers);
    headers.delete("Content-Type");
    fetchOptions.headers = headers;
  }

  let response: Response;
  const method = (fetchOptions.method || "GET").toUpperCase();
  
  try {
    response = await fetch(targetUrl, fetchOptions);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    
    // For reads (GET, HEAD, OPTIONS), outcome is safely known as failed.
    if (method === "GET" || method === "HEAD" || method === "OPTIONS") {
      throw new NetworkError("Network request failed", method, targetUrl);
    }
    
    // For mutations, the outcome is unknown (could be committed on server).
    // Extract metadata for reconciliation.
    const headers = new Headers(fetchOptions.headers);
    const idempotencyKey = headers.get("Idempotency-Key") || undefined;
    
    // Try to extract operationId from the URL if it's a known pattern, e.g. /operations/{operationId}
    // But usually operationId is something we get in response. If the client sent one, we might not have it.
    // The prompt says: "known operationId if one already exists... Do not invent an operation ID."
    // Let's just leave it optional; the caller or specific wrapper can attach it if known.
    let operationId: string | undefined = undefined;
    const opMatch = targetUrl.match(/\/operations\/([a-zA-Z0-9_-]+)/);
    if (opMatch) {
      operationId = opMatch[1];
    }
    
    throw new MutationUnknownError("Mutation network outcome unknown", method, targetUrl, idempotencyKey, operationId);
  }

  if (response.ok) {
    if (response.status === 204) {
      return null as unknown as T;
    }
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      const data = await response.json();
      const etag = response.headers.get("etag");
      if (etag && data && typeof data === "object") {
        Object.defineProperty(data, "_etag", { value: etag, enumerable: false });
      }
      return data as T;
    }
    return null as unknown as T;
  }

  let errorPayload: ErrorResponse["error"];
  try {
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      const parsed = await response.json();
      if (parsed && parsed.error && parsed.error.code) {
        errorPayload = parsed.error;
      } else {
        throw new Error("Malformed JSON or missing error code");
      }
    } else {
      throw new Error("Not JSON");
    }
  } catch {
    errorPayload = {
      code: response.status >= 500 ? "INTERNAL_ERROR" : "MALFORMED_JSON",
      message: response.status >= 500 ? "Internal Server Error" : "Invalid error payload from server",
      requestId: response.headers.get("x-request-id") || "req_unknown",
    };
  }

  throw new ApiError(response.status, errorPayload);
}

export function getETag(obj: unknown): string | undefined {
  return (obj as { _etag?: string })?._etag;
}
