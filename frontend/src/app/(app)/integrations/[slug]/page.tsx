"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  CopyButton,
  FormField,
  FormInput,
  FormTextarea,
  StatusBadge,
} from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showError, showSuccess } from "@/lib/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type {
  IntegrationDetail,
  TestIntegrationResponse,
} from "@/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function isMaskedValue(value: string): boolean {
  return value.startsWith("********");
}

// ─── Connected-users payload (per-user OAuth) ────────────────────────────────

interface ConnectedUser {
  user_id: string;
  connected_email: string | null;
  last_synced_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
}

interface ConnectedUsersResponse {
  users: ConnectedUser[];
}

// ─── Google Workspace connect card ────────────────────────────────────────────
//
// Replaces the credentials form for slug='google_workspace'. Each staff
// member runs their own OAuth round-trip:
//   1. Click "Connect Gmail" → POST /oauth/start → get the Google
//      consent URL → window.location to it.
//   2. After consent, Google redirects to /oauth/callback (handled by
//      the backend, which stores the encrypted refresh token), then
//      303s back here with ?connected=ok|err.
//   3. The page re-fetches the connected-users list to show the new row.

function GoogleWorkspaceConnectCard() {
  const [users, setUsers] = useState<ConnectedUser[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  // Setup-steps panel: expanded by default for first-time visitors so
  // the OAuth client setup is discoverable; collapses once at least
  // one user is connected (the steps stop being relevant). Manual
  // Show/Hide toggle overrides the heuristic.
  const [showSetupSteps, setShowSetupSteps] = useState(true);

  const loadConnected = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await apiClient.get<ConnectedUsersResponse>(
        "/integrations/google_workspace/oauth/connected-users",
        { silent: true },
      );
      const fetched = data.users ?? [];
      setUsers(fetched);
      // Once someone has connected, the steps are no longer the
      // primary content — collapse them so the connected-users list
      // gets the visual focus.
      if (fetched.length > 0) {
        setShowSetupSteps(false);
      }
    } catch {
      setUsers([]);
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void loadConnected();
    // If we just came back from the OAuth callback, surface the result
    // as a toast and clean the URL.
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const connected = params.get("connected");
      const errParam = params.get("error");
      if (connected === "ok") {
        showSuccess("Gmail connected. Threads will sync on the next run.");
        window.history.replaceState(
          {}, "", window.location.pathname,
        );
      } else if (connected === "err") {
        showError(
          errParam
            ? `Google OAuth failed: ${errParam}`
            : "Google OAuth was cancelled or failed.",
        );
        window.history.replaceState(
          {}, "", window.location.pathname,
        );
      }
    }
  }, [loadConnected]);

  async function handleConnect() {
    setIsConnecting(true);
    try {
      const data = await apiClient.get<{ redirect_url: string }>(
        "/integrations/google_workspace/oauth/start",
        { silent: true },
      );
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      } else {
        showError("Backend didn't return a Google consent URL.");
        setIsConnecting(false);
      }
    } catch (err) {
      showError(
        err instanceof Error
          ? err.message
          : "Failed to start the Google OAuth flow.",
      );
      setIsConnecting(false);
    }
  }

  async function handleDisconnect() {
    setIsDisconnecting(true);
    try {
      await apiClient.delete(
        "/integrations/google_workspace/oauth/disconnect",
        { silent: true },
      );
      showSuccess("Disconnected. Future syncs will skip your mailbox.");
      await loadConnected();
    } catch (err) {
      showError(
        err instanceof Error ? err.message : "Failed to disconnect.",
      );
    } finally {
      setIsDisconnecting(false);
    }
  }

  return (
    <div className="space-y-6">
    <Card>
      <CardHeader
        title="Setup steps"
        action={
          <button
            type="button"
            onClick={() => setShowSetupSteps((v) => !v)}
            className="text-[12px] font-medium text-indigo-600 hover:text-indigo-700"
          >
            {showSetupSteps ? "Hide" : "Show"}
          </button>
        }
      />
      {showSetupSteps && (
        <CardBody className="space-y-4">
          <div className="space-y-2">
            <h3 className="text-[12px] font-bold uppercase tracking-wider text-gray-500">
              One-time: admin sets up the OAuth client
            </h3>
            <ol className="list-decimal list-inside space-y-2 text-[13px] text-gray-700">
              <li>
                Open{" "}
                <a
                  href="https://console.cloud.google.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                >
                  Google Cloud Console
                </a>{" "}
                → create or pick a project, then enable the{" "}
                <a
                  href="https://console.cloud.google.com/apis/library/gmail.googleapis.com"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                >
                  Gmail API
                </a>
                .
              </li>
              <li>
                APIs &amp; Services →{" "}
                <a
                  href="https://console.cloud.google.com/apis/credentials/consent"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                >
                  OAuth consent screen
                </a>{" "}
                → configure (External or Internal depending on Workspace).
                Add scopes:{" "}
                <code className="font-mono text-[11px] bg-gray-100 px-1 rounded whitespace-nowrap">
                  gmail.readonly
                </code>
                ,{" "}
                <code className="font-mono text-[11px] bg-gray-100 px-1 rounded">openid</code>
                ,{" "}
                <code className="font-mono text-[11px] bg-gray-100 px-1 rounded">email</code>
                . If your project is in <em>Testing</em> mode, add yourself + every
                staff member who&apos;ll connect as a test user.
              </li>
              <li>
                APIs &amp; Services →{" "}
                <a
                  href="https://console.cloud.google.com/apis/credentials"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                >
                  Credentials
                </a>{" "}
                → Create Credentials → <strong>OAuth 2.0 Client ID</strong> →
                Application type: <strong>Web application</strong>.
                Add this <strong>Authorized redirect URI</strong>:
              </li>
            </ol>
            <div className="flex items-center gap-2 ml-6">
              <code
                className="flex-1 min-w-0 text-[11px] font-mono bg-gray-50 border border-gray-200 rounded-md px-3 py-2 overflow-x-auto whitespace-nowrap text-gray-800"
                aria-label="Authorized redirect URI"
              >
                http://localhost:8000/api/v1/integrations/google_workspace/oauth/callback
              </code>
              <CopyButton
                text="http://localhost:8000/api/v1/integrations/google_workspace/oauth/callback"
                label="Copy"
              />
            </div>
            <ol
              className="list-decimal list-inside space-y-2 text-[13px] text-gray-700"
              start={4}
            >
              <li>
                Copy the client ID + client secret. Add them to{" "}
                <code className="font-mono text-[11px]">backend/.env</code>:
              </li>
            </ol>
            <pre className="ml-6 text-[11px] font-mono bg-gray-50 border border-gray-200 rounded-md px-3 py-2 overflow-x-auto text-gray-800">
{`GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/integrations/google_workspace/oauth/callback`}
            </pre>
            <ol
              className="list-decimal list-inside space-y-2 text-[13px] text-gray-700"
              start={5}
            >
              <li>
                <strong>Restart the backend</strong> so the new env vars are
                loaded. Then come back here.
              </li>
            </ol>
          </div>

          <div className="border-t border-gray-100 pt-4 space-y-2">
            <h3 className="text-[12px] font-bold uppercase tracking-wider text-gray-500">
              Each staff member, once
            </h3>
            <ol className="list-decimal list-inside space-y-1.5 text-[13px] text-gray-700">
              <li>Sign in to CI as that user.</li>
              <li>
                Come to this page and click <strong>Connect Gmail</strong> below.
              </li>
              <li>
                Google redirects to its consent screen. Grant{" "}
                <code className="font-mono text-[11px]">gmail.readonly</code> for
                your account.
              </li>
              <li>
                You&apos;ll land back here with your row in <em>Connected users</em>.
                Email threads start appearing on lead detail pages on the next
                sync (nightly 02:45 UTC or via the per-lead Sync button).
              </li>
            </ol>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-[11px] text-amber-800">
            <strong>Read-only.</strong> We only request{" "}
            <code className="font-mono text-[10px]">gmail.readonly</code>.
            CI never sends mail and never touches anything else in your account.
            You can revoke anytime at{" "}
            <a
              href="https://myaccount.google.com/permissions"
              target="_blank"
              rel="noopener noreferrer"
              className="underline underline-offset-2"
            >
              myaccount.google.com/permissions
            </a>
            .
          </div>
        </CardBody>
      )}
    </Card>

    <Card>
      <CardHeader title="Connect your Google account" />
      <CardBody className="space-y-4">
        <p className="text-[13px] text-gray-700">
          Each staff member connects their own Google account. We read
          Gmail (read-only) and pull threads where a lead&apos;s email
          appears as From / To / Cc. We never send mail and never touch
          anything else in your account.
        </p>

        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            onClick={() => void handleConnect()}
            disabled={isConnecting}
          >
            {isConnecting ? "Redirecting to Google…" : "Connect Gmail"}
          </Button>
          {users.length > 0 && (
            <Button
              variant="ghost"
              onClick={() => void handleDisconnect()}
              disabled={isDisconnecting}
            >
              {isDisconnecting ? "Disconnecting…" : "Disconnect my account"}
            </Button>
          )}
        </div>

        <div>
          <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
            Connected users
          </div>
          {loadingList ? (
            <p className="text-[12px] text-gray-400 italic">Loading…</p>
          ) : users.length === 0 ? (
            <p className="text-[12px] text-gray-400 italic">
              No one has connected yet. Click <b>Connect Gmail</b> above to be the first.
            </p>
          ) : (
            <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
              {users.map((u) => (
                <li
                  key={u.user_id}
                  className="px-3 py-2 flex items-center gap-3 text-[13px]"
                >
                  <span className="text-gray-700 truncate flex-1">
                    {u.connected_email ?? "(unknown email)"}
                  </span>
                  {u.last_sync_status === "error" ? (
                    <span className="text-[11px] text-red-700 font-semibold">
                      Reconnect needed
                    </span>
                  ) : u.last_synced_at ? (
                    <span className="text-[11px] text-gray-400">
                      synced {new Date(u.last_synced_at).toLocaleString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                  ) : (
                    <span className="text-[11px] text-gray-400 italic">
                      not synced yet
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardBody>
    </Card>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IntegrationDetailPage({ params }: { params: { slug: string } }) {
  const { isLoading: authLoading } = useAuth();
  const slug = params.slug;

  const [detail, setDetail] = useState<IntegrationDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state: per-field input value. Pre-filled from detail.values for
  // non-secret fields; left empty for secret fields (the mask is shown as a
  // placeholder hint instead so the user knows there's a stored value).
  const [form, setForm] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const [savedFlash, setSavedFlash] = useState(false);
  const [testResult, setTestResult] = useState<TestIntegrationResponse | null>(null);
  // Confirm-dialog state for Disconnect — replaces window.confirm()
  // (CLAUDE.md rule: never use native popups).
  const [isDisconnectConfirmOpen, setIsDisconnectConfirmOpen] = useState(false);
  // Setup-steps panel: collapsed by default once connected so the page
  // stays tidy; expanded by default for first-time onboarding. Toggle
  // applies only to the Google Workspace provider (the only one with
  // a multi-step service-account dance to walk through).
  const [showSetupSteps, setShowSetupSteps] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await apiClient.get<IntegrationDetail>(`/integrations/${slug}`, { silent: true });
      setDetail(data);
      // Seed form: non-secret fields get their stored value; secret fields stay empty.
      const seeded: Record<string, string> = {};
      for (const field of data.fields) {
        if (field.secret) {
          seeded[field.key] = "";
        } else {
          seeded[field.key] = data.values[field.key] ?? "";
        }
      }
      setForm(seeded);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integration.");
    } finally {
      setIsLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  // For Google Workspace: expand setup steps by default while not yet
  // connected (first-time onboarding); collapse once connected so the
  // page stays tidy.
  useEffect(() => {
    if (slug === "google_workspace" && detail !== null) {
      setShowSetupSteps(!detail.connected);
    }
  }, [slug, detail]);

  async function handleSave() {
    if (!detail) return;
    setIsSaving(true);
    setTestResult(null);
    try {
      const updated = await apiClient.post<IntegrationDetail>(
        `/integrations/${slug}`,
        { values: form },
        { silent: true },
      );
      setDetail(updated);
      // Re-seed the form so any cleared secret inputs reset to empty
      // (the masked stored value is shown as a hint, not in the input).
      const seeded: Record<string, string> = {};
      for (const field of updated.fields) {
        seeded[field.key] = field.secret ? "" : (updated.values[field.key] ?? "");
      }
      setForm(seeded);
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2500);
      // Toast wording depends on what the user just did. Webhook-only
      // providers don't trigger a sync — they hand back a URL the user
      // pastes into the upstream tool. The credential-style providers
      // (Mailchimp) DO trigger a sync, hence the dashboard refresh note.
      if (updated.webhook_only) {
        showSuccess(
          detail.connected
            ? "Secret rotated — old URL no longer works."
            : "Webhook URL generated. Copy it into your provider's webhook config.",
        );
      } else {
        showSuccess("Saved — dashboard will refresh in ~30 seconds.");
      }
    } catch (err) {
      showError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleTest() {
    setIsTesting(true);
    setTestResult(null);
    try {
      const result = await apiClient.post<TestIntegrationResponse>(
        `/integrations/${slug}/test`,
        {},
        { silent: true },
      );
      setTestResult(result);
    } catch (err) {
      setTestResult({
        ok: false,
        message: err instanceof Error ? err.message : "Test failed.",
      });
    } finally {
      setIsTesting(false);
    }
  }

  async function handleSync() {
    setIsSyncing(true);
    setTestResult(null);
    try {
      const result = await apiClient.post<TestIntegrationResponse>(
        `/integrations/${slug}/sync`,
        {},
        { silent: true },
      );
      setTestResult(result);
      if (result.ok) {
        showSuccess(result.message);
      } else {
        showError(result.message);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Sync failed to start.";
      setTestResult({ ok: false, message: msg });
      showError(msg);
    } finally {
      setIsSyncing(false);
    }
  }

  function handleDisconnect() {
    if (!detail) return;
    setIsDisconnectConfirmOpen(true);
  }

  async function confirmDisconnect() {
    if (!detail) return;
    setIsDisconnecting(true);
    try {
      await apiClient.delete(`/integrations/${slug}`, { silent: true });
      await load();
      setTestResult(null);
      showSuccess(`${detail.name} disconnected.`);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Disconnect failed.");
    } finally {
      setIsDisconnecting(false);
      setIsDisconnectConfirmOpen(false);
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <>
        <Header title="Integration" />
        <main className="flex-1 overflow-y-auto p-7">
          <p className="text-sm text-gray-400">Loading…</p>
        </main>
      </>
    );
  }

  if (error || !detail) {
    return (
      <>
        <Header title="Integration" />
        <main className="flex-1 overflow-y-auto p-7 space-y-4">
          <Link href="/integrations" className="text-sm text-indigo-600 hover:text-indigo-700 underline underline-offset-2">
            ← Back to integrations
          </Link>
          <p className="text-sm text-red-700">{error ?? "Integration not found."}</p>
        </main>
      </>
    );
  }

  // Special-case: Google Calendar (OAuth flow not yet wired).
  const isOauthPending = detail.oauth_pending;
  // Special-case: webhook-receive providers like GHL — no credentials form;
  // we show the generated webhook URL the user pastes into the upstream
  // tool, plus Rotate Secret / Disconnect actions.
  const isWebhookOnly = detail.webhook_only;

  return (
    <>
      <Header title={detail.name} />

      <main className="flex-1 overflow-y-auto p-7 space-y-6 max-w-3xl">
        <Link
          href="/integrations"
          className="inline-block text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
        >
          ← Back to integrations
        </Link>

        {/* Heading */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <span className="text-3xl leading-none" aria-hidden>{detail.icon || "🔌"}</span>
            <div className="min-w-0">
              <h1 className="text-xl font-bold text-gray-900">{detail.name}</h1>
              <p className="text-xs text-gray-500 mt-0.5">{detail.description}</p>
            </div>
          </div>
          {detail.connected ? (
            <StatusBadge status="active" />
          ) : (
            <StatusBadge status={isOauthPending ? "archived" : "draft"} />
          )}
        </div>

        {/* Last-sync error banner */}
        {detail.last_sync_error && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3">
            <p className="text-xs text-red-800">
              <span className="font-semibold">Last sync error:</span> {detail.last_sync_error}
            </p>
          </div>
        )}

        {/* OAuth-pending placeholder body */}
        {isOauthPending ? (
          <Card>
            <CardBody className="space-y-3">
              <p className="text-sm text-gray-700">
                Google Calendar uses OAuth, and the connect flow is not wired yet.
                Save the slug here once the OAuth round-trip ships in a follow-up.
              </p>
              <Button variant="primary" disabled>
                Connect with Google (coming soon)
              </Button>
            </CardBody>
          </Card>
        ) : isWebhookOnly ? (
          // Webhook-receive providers (GHL today, Stripe/Calendly later).
          // No credentials form — we generate a token server-side and the
          // user pastes the URL into the upstream tool's webhook config.
          <Card>
            <CardHeader title="Webhook URL" />
            <CardBody className="space-y-4">
              {!detail.connected ? (
                <>
                  <p className="text-sm text-gray-700">
                    Generate a unique webhook URL for this integration. You&apos;ll
                    copy it into {detail.name}&apos;s Custom Webhook workflow action.
                  </p>
                  <Button onClick={handleSave} disabled={isSaving}>
                    {isSaving ? "Generating…" : "Generate webhook URL"}
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-[13px] text-gray-700">
                    Paste this URL into the URL field of {detail.name}&apos;s
                    Custom Webhook workflow action. Set the method to{" "}
                    <span className="font-mono">POST</span>, payload to{" "}
                    <span className="font-mono">JSON</span>, and map the
                    contact fields you want to push.
                  </p>
                  <div className="flex items-center gap-2">
                    <code
                      className="flex-1 min-w-0 text-[12px] font-mono bg-gray-50 border border-gray-200 rounded-md px-3 py-2 overflow-x-auto whitespace-nowrap text-gray-800"
                      aria-label="Webhook URL"
                    >
                      {detail.values.webhook_url ?? "(no URL)"}
                    </code>
                    <CopyButton
                      text={detail.values.webhook_url ?? ""}
                      label="Copy"
                    />
                  </div>
                  <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-[12px] text-amber-800">
                    <strong>Heads up:</strong> the URL contains a secret token.
                    Treat it like a password. If it leaks, click{" "}
                    <strong>Rotate Secret</strong> below — the old URL stops
                    working immediately.
                  </div>
                  <div className="flex items-center gap-2 pt-2">
                    <Button
                      variant="ghost"
                      onClick={handleSave}
                      disabled={isSaving}
                    >
                      {isSaving ? "Rotating…" : "Rotate Secret"}
                    </Button>
                    <Button
                      variant="danger"
                      onClick={handleDisconnect}
                      disabled={isDisconnecting}
                      className="ml-auto"
                    >
                      {isDisconnecting ? "Disconnecting…" : "Disconnect"}
                    </Button>
                  </div>
                </>
              )}
            </CardBody>
          </Card>
        ) : (
          // Credentials form
          <>
          {slug === "google_workspace" && detail.oauth_per_user && (
            <GoogleWorkspaceConnectCard />
          )}
          {slug === "ghl" && detail.values.webhook_url && (
            <Card>
              <CardHeader title="Webhook URL" />
              <CardBody className="space-y-3">
                <p className="text-[13px] text-gray-700">
                  Paste this URL into a GHL Custom Webhook workflow action to
                  receive contact pushes (form-fill, tag-added, etc.). The
                  nightly contact sync below handles everything else.
                </p>
                <div className="flex items-center gap-2">
                  <code
                    className="flex-1 min-w-0 text-[12px] font-mono bg-gray-50 border border-gray-200 rounded-md px-3 py-2 overflow-x-auto whitespace-nowrap text-gray-800"
                    aria-label="Webhook URL"
                  >
                    {detail.values.webhook_url}
                  </code>
                  <CopyButton text={detail.values.webhook_url} label="Copy" />
                </div>
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 text-[11px] text-amber-800">
                  The URL contains a secret token — treat like a password.
                </div>
              </CardBody>
            </Card>
          )}
          <Card>
            <CardHeader title="Credentials" />
            <CardBody className="space-y-4">
              {detail.fields.length === 0 && (
                <p className="text-sm text-gray-500">This integration doesn&apos;t need any credentials yet.</p>
              )}

              {detail.fields.map((field) => {
                const storedMasked = detail.values[field.key] ?? "";
                const showSecretHint = field.secret && detail.connected && isMaskedValue(storedMasked);
                const placeholder = showSecretHint
                  ? `Stored: ${storedMasked} — leave blank to keep`
                  : field.placeholder;
                return (
                  <FormField key={field.key} label={field.label} htmlFor={`int-${field.key}`}>
                    {field.type === "textarea" ? (
                      <FormTextarea
                        id={`int-${field.key}`}
                        rows={10}
                        value={form[field.key] ?? ""}
                        placeholder={placeholder}
                        onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                        className="font-mono text-[11px]"
                      />
                    ) : (
                      <FormInput
                        id={`int-${field.key}`}
                        type={field.type === "password" ? "password" : "text"}
                        value={form[field.key] ?? ""}
                        placeholder={placeholder}
                        onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                      />
                    )}
                    {field.help && (
                      <p className="text-[11px] text-gray-500 mt-1">{field.help}</p>
                    )}
                  </FormField>
                );
              })}

              {/* Test result */}
              {testResult && (
                <div
                  className={`rounded-lg px-3 py-2 text-xs ${
                    testResult.ok
                      ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                      : "bg-red-50 text-red-800 border border-red-200"
                  }`}
                >
                  {testResult.ok ? "✓ " : "✗ "}
                  {testResult.message}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2 pt-2">
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? "Saving…" : savedFlash ? "Saved ✓" : detail.connected ? "Update" : "Save & Connect"}
                </Button>
                {detail.connected && (
                  <Button variant="ghost" onClick={handleTest} disabled={isTesting}>
                    {isTesting ? "Testing…" : "Test"}
                  </Button>
                )}
                {detail.connected && slug === "ghl" && (
                  <Button variant="ghost" onClick={handleSync} disabled={isSyncing}>
                    {isSyncing ? "Queueing…" : "Sync contacts now"}
                  </Button>
                )}
                {detail.connected && (
                  <Button variant="danger" onClick={handleDisconnect} disabled={isDisconnecting} className="ml-auto">
                    {isDisconnecting ? "Disconnecting…" : "Disconnect"}
                  </Button>
                )}
              </div>
            </CardBody>
          </Card>
          </>
        )}
      </main>

      <ConfirmDialog
        open={isDisconnectConfirmOpen}
        onClose={() => setIsDisconnectConfirmOpen(false)}
        onConfirm={() => void confirmDisconnect()}
        title={detail ? `Disconnect ${detail.name}?` : "Disconnect?"}
        description="Stored credentials will be deleted from this app. The connection on the provider's side is not affected."
        confirmLabel="Disconnect"
        variant="danger"
        loading={isDisconnecting}
      />
    </>
  );
}
