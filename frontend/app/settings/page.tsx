"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Alert, Button, Card, Input } from "@/components/ui";

type Settings = {
  user_id: string;
  notification_channel: "console" | "smtp";
  notifications_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_user: string | null;
  smtp_from: string | null;
  smtp_use_tls: boolean;
  has_smtp_password: boolean;
  updated_at: string | null;
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [form, setForm] = useState<Record<string, string>>({
    notification_channel: "console",
    notifications_enabled: "true",
    smtp_host: "",
    smtp_port: "",
    smtp_user: "",
    smtp_password: "",
    smtp_from: "",
    smtp_use_tls: "true",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<Settings>("/api/settings");
        setSettings(data);
        setForm({
          notification_channel: data.notification_channel,
          notifications_enabled: data.notifications_enabled ? "true" : "false",
          smtp_host: data.smtp_host || "",
          smtp_port: data.smtp_port ? String(data.smtp_port) : "",
          smtp_user: data.smtp_user || "",
          smtp_password: "",
          smtp_from: data.smtp_from || "",
          smtp_use_tls: data.smtp_use_tls ? "true" : "false",
        });
      } catch (err: any) {
        setError(err.message || "Impossibile caricare le impostazioni.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function onSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const payload: Record<string, unknown> = {
        notification_channel: form.notification_channel,
        notifications_enabled: form.notifications_enabled === "true",
        smtp_host: form.smtp_host || null,
        smtp_port: form.smtp_port ? Number(form.smtp_port) : null,
        smtp_user: form.smtp_user || null,
        smtp_from: form.smtp_from || null,
        smtp_use_tls: form.smtp_use_tls === "true",
      };

      // Invia password solo se compilata
      if (form.smtp_password) {
        payload.smtp_password = form.smtp_password;
      }

      const data = await apiFetch<Settings>("/api/settings", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setSettings(data);
      setForm((prev) => ({ ...prev, smtp_password: "" }));
      setMessage("Impostazioni salvate.");
    } catch (err: any) {
      setError(err.message || "Salvataggio fallito.");
    } finally {
      setSaving(false);
    }
  }

  async function onTestEmail() {
    setTesting(true);
    setError(null);
    setMessage(null);

    try {
      const result = await apiFetch<{
        ok: boolean;
        message: string;
        recipient: string;
      }>("/api/settings/test-email", { method: "POST" });
      setMessage(`Email di prova inviata a ${result.recipient}.`);
    } catch (err: any) {
      setError(err.message || "Test email fallito.");
    } finally {
      setTesting(false);
    }
  }

  return (
    <main className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <Link
            href="/dashboard"
            className="text-sm text-blue-700 hover:underline"
          >
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2 text-slate-900">
            Impostazioni notifiche
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Configura il canale preferito per le notifiche dei promemoria.
          </p>
        </header>

        {error && <Alert variant="error">{error}</Alert>}
        {message && <Alert variant="success">{message}</Alert>}

        {loading ? (
          <Card>
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
            </div>
          </Card>
        ) : (
          <form onSubmit={onSave} className="space-y-6">
            <Card>
              <h2 className="text-lg font-semibold mb-4">Generale</h2>

              <div className="space-y-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={form.notifications_enabled === "true"}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        notifications_enabled: e.target.checked
                          ? "true"
                          : "false",
                      }))
                    }
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  <span className="text-sm">
                    Abilita le notifiche dei promemoria
                  </span>
                </label>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Canale preferito
                  </label>
                  <select
                    value={form.notification_channel}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        notification_channel: e.target.value,
                      }))
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white text-sm"
                  >
                    <option value="console">
                      Console (solo log, nessuna email)
                    </option>
                    <option value="smtp">Email via SMTP</option>
                  </select>
                  <p className="text-xs text-slate-500 mt-1">
                    &quot;Console&quot; e&apos; il default sicuro: le notifiche
                    appaiono solo nei log del server.
                  </p>
                </div>
              </div>
            </Card>

            {form.notification_channel === "smtp" && (
              <Card>
                <h2 className="text-lg font-semibold mb-4">
                  Configurazione SMTP
                </h2>

                <Alert variant="warning" title="Avviso sicurezza">
                  La password SMTP viene salvata <strong>cifrata</strong> nel
                  database (Fernet). Usa comunque un account SMTP dedicato e
                  non riutilizzare password sensibili. Questo portale e&apos;
                  pensato per uso personale/familiare.
                </Alert>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <Input
                    label="Host SMTP *"
                    type="text"
                    value={form.smtp_host}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, smtp_host: e.target.value }))
                    }
                    placeholder="smtp.example.com"
                  />
                  <Input
                    label="Porta"
                    type="number"
                    value={form.smtp_port}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, smtp_port: e.target.value }))
                    }
                    placeholder="587"
                  />
                  <Input
                    label="Utente SMTP"
                    type="text"
                    value={form.smtp_user}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, smtp_user: e.target.value }))
                    }
                  />
                  <Input
                    label="Password SMTP"
                    type="password"
                    value={form.smtp_password}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        smtp_password: e.target.value,
                      }))
                    }
                    placeholder="Lascia vuoto per non modificare"
                    hint={
                      settings?.has_smtp_password
                        ? "Gia' configurata: lascia vuoto per mantenerla."
                        : undefined
                    }
                  />
                  <div className="md:col-span-2">
                    <Input
                      label="Mittente (From)"
                      type="email"
                      value={form.smtp_from}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, smtp_from: e.target.value }))
                      }
                      placeholder="noreply@example.com"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={form.smtp_use_tls === "true"}
                        onChange={(e) =>
                          setForm((p) => ({
                            ...p,
                            smtp_use_tls: e.target.checked ? "true" : "false",
                          }))
                        }
                        className="h-4 w-4 rounded border-slate-300"
                      />
                      <span className="text-sm">Usa STARTTLS</span>
                    </label>
                  </div>
                </div>

                <div className="mt-4">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={onTestEmail}
                    disabled={testing || !form.smtp_host}
                    loading={testing}
                  >
                    {testing ? "Invio in corso..." : "Invia email di prova"}
                  </Button>
                </div>
              </Card>
            )}

            <Card>
              <Button type="submit" disabled={saving} loading={saving}>
                {saving ? "Salvataggio..." : "Salva impostazioni"}
              </Button>
            </Card>
          </form>
        )}

        <footer className="text-xs text-slate-500 pt-2">
          Il canale &quot;console&quot; e&apos; il default sicuro. Per ricevere
          email reali configura un server SMTP valido e premi &quot;Invia email
          di prova&quot; prima di abilitare lo scheduler.
        </footer>
      </div>
    </main>
  );
}