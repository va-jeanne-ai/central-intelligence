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
                return (
                  <FormField key={field.key} label={field.label} htmlFor={`int-${field.key}`}>
                    <FormInput
                      id={`int-${field.key}`}
                      type={field.type === "password" ? "password" : "text"}
                      value={form[field.key] ?? ""}
                      placeholder={showSecretHint ? `Stored: ${storedMasked} — leave blank to keep` : field.placeholder}
                      onChange={(e) => setForm({ ...form, [field.key]: e.target.value })}
                    />
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
