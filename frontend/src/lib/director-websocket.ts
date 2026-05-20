import type { WebSocketMessage } from "@/types";
import { apiClient } from "@/lib/api-client";
import { showError } from "@/lib/toast";

// ─── Types ──────────────────────────────────────────────────────────────────

type MessageHandler = (data: WebSocketMessage) => void;
type StateChangeHandler = (state: ConnectionState) => void;

type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "closing"
  | "failed";

// ─── DirectorWebSocket ────────────────────────────────────────────────────────
//
// Mirrors CentralIntelligenceWebSocket exactly, but targets the Director endpoints:
//   <wsBase>/<directorSlug>/<sessionId>
// rather than the Central Intelligence endpoint.

export class DirectorWebSocket {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private reconnectAttempts = 0;
  private readonly maxReconnects = 5;
  private readonly messageHandlers: Set<MessageHandler> = new Set();
  private readonly stateHandlers: Set<StateChangeHandler> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private state: ConnectionState = "disconnected";
  private disposed = false;

  constructor(directorSlug: string, sessionId: string) {
    const wsBase =
      process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/v1";
    const baseUrl = `${wsBase}/${directorSlug}/${sessionId}`;

    // Append JWT as a query parameter so the backend can authenticate the
    // WebSocket handshake. In mock mode the token is null so we omit it.
    const token = apiClient.getToken();
    this.url = token ? `${baseUrl}?token=${encodeURIComponent(token)}` : baseUrl;
  }

  // ─── Public API ──────────────────────────────────────────────────────────────

  connect(): void {
    if (this.disposed) return;
    if (this.state === "connecting" || this.state === "connected") return;

    this.setState("connecting");

    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      console.error("[DirectorWebSocket] Failed to construct WebSocket:", err);
      this.setState("disconnected");
      this.handleReconnect();
      return;
    }

    this.ws.onopen = () => {
      if (this.disposed) {
        this.ws?.close(1000);
        return;
      }
      this.setState("connected");
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event: MessageEvent<string>) => {
      if (this.disposed) return;
      try {
        const parsed = JSON.parse(event.data) as WebSocketMessage;
        this.messageHandlers.forEach((handler) => handler(parsed));
      } catch (err) {
        console.warn(
          "[DirectorWebSocket] Could not parse message:",
          event.data,
          err,
        );
      }
    };

    this.ws.onerror = (event) => {
      if (this.disposed) return;
      console.error("[DirectorWebSocket] WebSocket error:", event);
    };

    this.ws.onclose = (event) => {
      if (this.disposed) return;
      this.setState("disconnected");
      this.ws = null;

      // Do not reconnect if we closed intentionally.
      if (event.code === 1000) return;

      this.handleReconnect();
    };
  }

  disconnect(): void {
    this.disposed = true;
    this.cancelReconnect();
    this.reconnectAttempts = 0;

    if (this.ws !== null) {
      // Remove event handlers before closing to prevent onclose from
      // triggering reconnect on a disposed instance.
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onerror = null;
      this.ws.onclose = null;
      this.ws.close(1000, "Client disconnecting");
      this.ws = null;
    }

    this.setState("disconnected");
  }

  send(message: string): void {
    if (this.ws === null || this.state !== "connected") {
      console.warn("[DirectorWebSocket] Cannot send — socket is not connected");
      return;
    }

    this.ws.send(JSON.stringify({ message }));
  }

  /**
   * Register a handler that is called on every incoming message.
   * Returns an unsubscribe function that removes the handler.
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  get connectionState(): ConnectionState {
    return this.state;
  }

  /**
   * Register a handler called whenever connection state changes.
   * Returns an unsubscribe function.
   */
  onStateChange(handler: StateChangeHandler): () => void {
    this.stateHandlers.add(handler);
    return () => {
      this.stateHandlers.delete(handler);
    };
  }

  // ─── Private ─────────────────────────────────────────────────────────────────

  private setState(newState: ConnectionState): void {
    this.state = newState;
    this.stateHandlers.forEach((h) => h(newState));
  }

  private handleReconnect(): void {
    if (this.disposed) return;
    if (this.reconnectAttempts >= this.maxReconnects) {
      console.warn(
        `[DirectorWebSocket] Max reconnect attempts (${this.maxReconnects}) reached. Giving up.`,
      );
      this.setState("failed");
      showError("Connection lost. Please refresh the page to reconnect.");
      return;
    }

    this.reconnectAttempts += 1;

    // Exponential back-off: 500 ms, 1 s, 2 s, 4 s, 8 s (capped at 30 s).
    const delay = Math.min(
      500 * Math.pow(2, this.reconnectAttempts - 1),
      30_000,
    );

    console.info(
      `[DirectorWebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnects})`,
    );

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private cancelReconnect(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
