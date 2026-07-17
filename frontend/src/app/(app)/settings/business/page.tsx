"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FormField, FormInput, FormTextarea } from "@/components/ui/form-field";
import { useAuth } from "@/hooks/use-auth";
import { showError, showSuccess } from "@/lib/toast";
import { configClient } from "@/lib/config-client";
import { ApiError } from "@/lib/api-client";
import type { InstanceProfile, InstanceProfileUpdate } from "@/types";

// ─── Editable fields ──────────────────────────────────────────────────────────
// Terminology/benchmarks/colors are JSONB blobs — deferred to a later phase
// with a dedicated key/value or JSON editor. This form covers every scalar
// field on the profile.

type EditableField = keyof Omit<
  InstanceProfile,
  "exists" | "terminology" | "benchmarks" | "colors"
>;

const FIELD_ORDER: EditableField[] = [
  "business_name",
  "vertical",
  "business_description",
  "target_audience",
  "brand_voice",
  "app_name",
  "tagline",
  "logo_url",
  "currency_code",
  "currency_symbol",
  "timezone",
  "locale",
];

type FormState = Record<EditableField, string>;

function emptyForm(): FormState {
  return {
    business_name: "",
    vertical: "",
    business_description: "",
    target_audience: "",
    brand_voice: "",
    app_name: "",
    tagline: "",
    logo_url: "",
    currency_code: "",
    currency_symbol: "",
    timezone: "",
    locale: "",
  };
}

/** Profile fields come back as `string | null` (except app_name/currency_code/
 * currency_symbol/timezone/locale, which are always strings) — normalize to
 * "" for form inputs, which don't accept null. */
function toFormState(profile: InstanceProfile): FormState {
  const state = emptyForm();
  for (const key of FIELD_ORDER) {
    const value = profile[key];
    state[key] = value ?? "";
  }
  return state;
}

export default function BusinessSettingsPage() {
  const { isLoading: authLoading } = useAuth();

  const [profile, setProfile] = useState<InstanceProfile | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const data = await configClient.getProfile();
      setProfile(data);
      setForm(toFormState(data));
    } catch (err) {
      setLoadError(
        err instanceof Error ? err.message : "Failed to load business settings.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  function setField(key: EditableField, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!profile) return;
    setIsSaving(true);
    try {
      // Only send fields that actually changed, per the PUT contract.
      const changed: InstanceProfileUpdate = {};
      for (const key of FIELD_ORDER) {
        const original = profile[key] ?? "";
        if (form[key] !== original) {
          changed[key] = form[key];
        }
      }

      if (Object.keys(changed).length === 0) {
        showSuccess("Nothing to save — no fields changed.");
        return;
      }

      const updated = await configClient.updateProfile(changed);
      setProfile(updated);
      setForm(toFormState(updated));
      showSuccess("Business settings saved.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        showError("Admin access is required to change business settings.");
      } else {
        showError(err instanceof Error ? err.message : "Failed to save business settings.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <>
        <Header title="Business Settings" />
        <main className="flex-1 overflow-y-auto p-7">
          <p className="text-sm text-gray-400">Loading…</p>
        </main>
      </>
    );
  }

  if (loadError || !profile) {
    return (
      <>
        <Header title="Business Settings" />
        <main className="flex-1 overflow-y-auto p-7">
          <p className="text-sm text-red-700">{loadError ?? "Business profile not found."}</p>
        </main>
      </>
    );
  }

  return (
    <>
      <Header title="Business Settings" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6 max-w-3xl">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Business Settings</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Configure how this instance describes your business and how it
            presents itself — app name, branding, and locale. Admin access
            required to save changes.
          </p>
        </div>

        <Card>
          <CardHeader title="Business profile" />
          <CardBody className="space-y-4">
            <FormField label="Business name" htmlFor="biz-business_name">
              <FormInput
                id="biz-business_name"
                value={form.business_name}
                onChange={(e) => setField("business_name", e.target.value)}
                placeholder="Acme Fitness Coaching"
              />
            </FormField>

            <FormField label="Vertical" htmlFor="biz-vertical">
              <FormInput
                id="biz-vertical"
                value={form.vertical}
                onChange={(e) => setField("vertical", e.target.value)}
                placeholder="e.g. fitness coaching, real estate, SaaS"
              />
            </FormField>

            <FormField label="Business description" htmlFor="biz-business_description">
              <FormTextarea
                id="biz-business_description"
                rows={4}
                value={form.business_description}
                onChange={(e) => setField("business_description", e.target.value)}
                placeholder="What does this business do, for whom, and how?"
              />
            </FormField>

            <FormField label="Target audience" htmlFor="biz-target_audience">
              <FormTextarea
                id="biz-target_audience"
                rows={3}
                value={form.target_audience}
                onChange={(e) => setField("target_audience", e.target.value)}
                placeholder="Who are your ideal customers?"
              />
            </FormField>

            <FormField label="Brand voice" htmlFor="biz-brand_voice">
              <FormTextarea
                id="biz-brand_voice"
                rows={3}
                value={form.brand_voice}
                onChange={(e) => setField("brand_voice", e.target.value)}
                placeholder="Tone and style AI-generated content should use"
              />
            </FormField>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="App branding" />
          <CardBody className="space-y-4">
            <FormField label="App name" htmlFor="biz-app_name">
              <FormInput
                id="biz-app_name"
                value={form.app_name}
                onChange={(e) => setField("app_name", e.target.value)}
                placeholder="Central Intelligence"
              />
            </FormField>

            <FormField label="Tagline" htmlFor="biz-tagline">
              <FormInput
                id="biz-tagline"
                value={form.tagline}
                onChange={(e) => setField("tagline", e.target.value)}
                placeholder="AI Command Center"
              />
            </FormField>

            <FormField label="Logo URL" htmlFor="biz-logo_url">
              <FormInput
                id="biz-logo_url"
                value={form.logo_url}
                onChange={(e) => setField("logo_url", e.target.value)}
                placeholder="https://example.com/logo.png"
              />
              <p className="text-[11px] text-gray-500 mt-1">
                Shown in the sidebar and on the login page in place of the default icon.
              </p>
            </FormField>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Locale & currency" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Currency code" htmlFor="biz-currency_code">
                <FormInput
                  id="biz-currency_code"
                  value={form.currency_code}
                  onChange={(e) => setField("currency_code", e.target.value)}
                  placeholder="USD"
                />
              </FormField>

              <FormField label="Currency symbol" htmlFor="biz-currency_symbol">
                <FormInput
                  id="biz-currency_symbol"
                  value={form.currency_symbol}
                  onChange={(e) => setField("currency_symbol", e.target.value)}
                  placeholder="$"
                />
              </FormField>

              <FormField label="Timezone" htmlFor="biz-timezone">
                <FormInput
                  id="biz-timezone"
                  value={form.timezone}
                  onChange={(e) => setField("timezone", e.target.value)}
                  placeholder="America/New_York"
                />
              </FormField>

              <FormField label="Locale" htmlFor="biz-locale">
                <FormInput
                  id="biz-locale"
                  value={form.locale}
                  onChange={(e) => setField("locale", e.target.value)}
                  placeholder="en-US"
                />
              </FormField>
            </div>
          </CardBody>
        </Card>

        <div className="flex items-center gap-2">
          <Button onClick={() => void handleSave()} disabled={isSaving}>
            {isSaving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </main>
    </>
  );
}
