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
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
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
  try {
    response = await fetch(targetUrl, fetchOptions);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new NetworkError("Network request failed or unknown outcome");
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
