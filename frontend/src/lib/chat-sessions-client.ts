// Thin wrapper around the chat-session CRUD endpoints.
//
// The streaming chat itself lives in use-chat.ts (WebSocket) and api-
// client.chatStream (SSE). This file is the read/edit/delete side:
// list past sessions, load a transcript, rename, delete.

import { apiClient } from "@/lib/api-client";
import type {
  ChatSessionListResponse,
  ChatSessionDetailResponse,
  ChatSessionRow,
} from "@/types";

export const chatSessionsClient = {
  /** GET /api/v1/chat/sessions — current user's sessions newest-first.
   *
   * Pass `agentSlug` to scope to one surface: omit for Central Intelligence,
   * or a director slug (e.g. "marketing-director") for that director only.
   */
  list(agentSlug?: string): Promise<ChatSessionListResponse> {
    const qs = agentSlug
      ? `?agent_slug=${encodeURIComponent(agentSlug)}`
      : "";
    return apiClient.get<ChatSessionListResponse>(`/chat/sessions${qs}`, {
      silent: true,
    });
  },

  /** GET /api/v1/chat/sessions/{id} — session row + full transcript. */
  get(sessionId: string): Promise<ChatSessionDetailResponse> {
    return apiClient.get<ChatSessionDetailResponse>(
      `/chat/sessions/${sessionId}`,
      { silent: true },
    );
  },

  /** PATCH /api/v1/chat/sessions/{id} — rename. */
  rename(sessionId: string, title: string): Promise<ChatSessionRow> {
    return apiClient.patch<ChatSessionRow>(
      `/chat/sessions/${sessionId}`,
      { title },
    );
  },

  /** DELETE /api/v1/chat/sessions/{id} — hard delete (CASCADEs messages). */
  remove(sessionId: string): Promise<void> {
    return apiClient.delete<void>(`/chat/sessions/${sessionId}`);
  },
};
