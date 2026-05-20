import type { ApiErrorResponse, ChatChunk, RequestOptions } from "@/types";
import { showApiError } from "@/lib/toast";

// ─── Constants ─────────────────────────────────────────────────────────────────

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const DEFAULT_TIMEOUT_MS = 30_000;
const MAX_ATTEMPTS = 3;

// ─── Error ─────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly field?: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function generateRequestId(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Parse the standard API error envelope `{ error: { code, message, ... } }`
 * or fall back to legacy flat shapes `{ code?, message?, detail? }`.
 */
function parseErrorBody(
  body: unknown,
  fallbackStatus: number,
): ApiError {
  if (
    body !== null &&
    typeof body === "object" &&
    "error" in body &&
    typeof (body as ApiErrorResponse).error === "object"
  ) {
    const envelope = (body as ApiErrorResponse).error;
    return new ApiError(
      fallbackStatus,
      envelope.code ?? "HTTP_ERROR",
      envelope.message ?? `Request failed with status ${fallbackStatus}`,
      envelope.field,
      envelope.requestId,
    );
  }

  // Legacy / non-envelope shape
  const flat = body as { code?: string; message?: string; detail?: string } | null;
  const code = flat?.code ?? "HTTP_ERROR";
  const message =
    flat?.message ?? flat?.detail ?? `Request failed with status ${fallbackStatus}`;

  return new ApiError(fallbackStatus, code, message);
}

// ─── Client ────────────────────────────────────────────────────────────────────

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl = API_BASE) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string): void {
    this.token = token;
  }

  clearToken(): void {
    this.token = null;
  }

  /** Returns the currently stored JWT, or null if unauthenticated. */
  getToken(): string | null {
    return this.token;
  }

  private buildHeaders(extra: HeadersInit = {}): Headers {
    const headers = new Headers({
      "Content-Type": "application/json",
      "X-Request-Id": generateRequestId(),
      ...extra,
    });

    if (this.token !== null) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    return headers;
  }

  private async request<T>(
    path: string,
    fetchOptions: RequestInit = {},
    clientOptions: RequestOptions = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const timeoutMs = clientOptions.timeout ?? DEFAULT_TIMEOUT_MS;
    const maxAttempts = clientOptions.retries !== undefined
      ? clientOptions.retries + 1
      : MAX_ATTEMPTS;
    const silent = clientOptions.silent ?? false;

    const retryDelaysMs = [1000, 2000];

    let lastError: ApiError | null = null;

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      // Exponential backoff — sleep before every retry (not the first attempt).
      if (attempt > 0) {
        await sleep(retryDelaysMs[attempt - 1] ?? 2000);
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

      const mergedOptions: RequestInit = {
        ...fetchOptions,
        headers: this.buildHeaders(fetchOptions.headers as HeadersInit | undefined),
        signal: controller.signal,
      };

      let response: Response;
      try {
        response = await fetch(url, mergedOptions);
      } catch (cause) {
        clearTimeout(timeoutId);

        // AbortError means the timeout fired — do not retry.
        if (cause instanceof DOMException && cause.name === "AbortError") {
          const err = new ApiError(0, "TIMEOUT", "Request timed out");
          if (!silent) showApiError(err);
          throw err;
        }

        // Network error — eligible for retry.
        lastError = new ApiError(
          0,
          "NETWORK_ERROR",
          `Network request failed: ${String(cause)}`,
        );
        continue;
      } finally {
        clearTimeout(timeoutId);
      }

      if (!response.ok) {
        // Parse the error body regardless of whether we will retry.
        let parsedBody: unknown = null;
        try {
          parsedBody = await response.json();
        } catch {
          // Non-JSON body — parsedBody stays null.
        }

        // 401: clear token — redirect to login unless the caller opted out via silent.
        if (response.status === 401) {
          this.clearToken();
          if (!silent && typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
            showApiError("Session expired. Please sign in again.");
            window.location.href = "/login";
          }
          throw new ApiError(401, "UNAUTHORIZED", "Session expired. Please sign in again.");
        }

        const apiError = parseErrorBody(parsedBody, response.status);

        // 4xx (non-401): client error — do not retry.
        if (response.status >= 400 && response.status < 500) {
          if (!silent) showApiError(apiError);
          throw apiError;
        }

        // 5xx: server error — eligible for retry.
        lastError = apiError;
        continue;
      }

      // 204 No Content
      if (response.status === 204) {
        return undefined as T;
      }

      return response.json() as Promise<T>;
    }

    // All attempts exhausted.
    const finalError =
      lastError ?? new ApiError(0, "UNKNOWN_ERROR", "Request failed after retries");

    if (!silent) showApiError(finalError);
    throw finalError;
  }

  // ─── SSE streaming chat ──────────────────────────────────────────────────────
  // No retry logic here — SSE has its own reconnection semantics.

  async *chatStream(
    message: string,
    sessionId?: string,
  ): AsyncGenerator<ChatChunk> {
    const url = `${this.baseUrl}/central-intelligence/chat`;

    const headers = this.buildHeaders({ Accept: "text/event-stream" });
    // Override Content-Type already set; redundant but explicit.
    headers.set("Content-Type", "application/json");

    const body: Record<string, unknown> = { message };
    if (sessionId !== undefined) {
      body["session_id"] = sessionId;
    }

    let response: Response;
    try {
      response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
    } catch (cause) {
      throw new ApiError(0, "NETWORK_ERROR", `Network request failed: ${String(cause)}`);
    }

    if (!response.ok) {
      let code = "HTTP_ERROR";
      let errorMessage = `Chat stream failed with status ${response.status}`;

      try {
        const errBody = (await response.json()) as { code?: string; message?: string };
        if (errBody.code) code = errBody.code;
        if (errBody.message) errorMessage = errBody.message;
      } catch {
        // Non-JSON error body — use defaults.
      }

      throw new ApiError(response.status, code, errorMessage);
    }

    if (response.body === null) {
      throw new ApiError(0, "NO_BODY", "Stream response had no body");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by double newline.
        const parts = buffer.split("\n\n");
        // Keep the last (possibly incomplete) chunk in the buffer.
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const lines = part.split("\n");
          let dataLine: string | undefined;

          for (const line of lines) {
            if (line.startsWith("data:")) {
              dataLine = line.slice(5).trim();
            }
          }

          if (dataLine === undefined || dataLine === "") continue;

          // Signal that the stream has ended without a JSON payload.
          if (dataLine === "[DONE]") return;

          try {
            const chunk = JSON.parse(dataLine) as ChatChunk;
            yield chunk;
            if (chunk.done === true) return;
          } catch {
            // Malformed JSON in a single chunk — skip and continue.
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  // ─── Convenience methods ─────────────────────────────────────────────────────

  get = <T>(path: string, options?: RequestOptions): Promise<T> =>
    this.request<T>(path, {}, options);

  post = <T>(path: string, body: unknown, options?: RequestOptions): Promise<T> =>
    this.request<T>(path, { method: "POST", body: JSON.stringify(body) }, options);

  put = <T>(path: string, body: unknown, options?: RequestOptions): Promise<T> =>
    this.request<T>(path, { method: "PUT", body: JSON.stringify(body) }, options);

  patch = <T>(path: string, body: unknown, options?: RequestOptions): Promise<T> =>
    this.request<T>(path, { method: "PATCH", body: JSON.stringify(body) }, options);

  delete = <T>(path: string, options?: RequestOptions): Promise<T> =>
    this.request<T>(path, { method: "DELETE" }, options);
}

// ─── Singleton ─────────────────────────────────────────────────────────────────

export const apiClient = new ApiClient();
