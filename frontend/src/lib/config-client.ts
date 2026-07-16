// Thin wrapper around the instance config endpoints (white-label branding +
// full business profile). See src/hooks/use-branding.ts for the React Query
// hook that consumes `getBranding`.

import { apiClient } from "@/lib/api-client";
import type { BrandingConfig, InstanceProfile, InstanceProfileUpdate } from "@/types";

export const configClient = {
  /**
   * Public branding config — no auth token required (and none is sent; this
   * powers the pre-auth /login page as well as the authenticated app shell).
   * `silent: true` because callers fall back to APP_CONFIG on failure rather
   * than surfacing an error toast for what is a cosmetic, best-effort fetch.
   */
  getBranding(): Promise<BrandingConfig> {
    return apiClient.get<BrandingConfig>("/config/branding", { silent: true });
  },

  /**
   * Full instance profile — requires auth. `silent: true` so the caller
   * (Business Settings page) owns the error toast wording instead of getting
   * a duplicate generic one from the api-client's default error handling.
   */
  getProfile(): Promise<InstanceProfile> {
    return apiClient.get<InstanceProfile>("/config/profile", { silent: true });
  },

  /**
   * Partial update — admin-only server-side (403 for non-admins). Send only
   * changed fields. `silent: true` for the same reason as getProfile — the
   * caller distinguishes the 403 case with its own toast message.
   */
  updateProfile(update: InstanceProfileUpdate): Promise<InstanceProfile> {
    return apiClient.put<InstanceProfile>("/config/profile", update, { silent: true });
  },
};
