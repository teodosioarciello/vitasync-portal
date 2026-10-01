"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

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
      const result = await apiFetch<{ ok: boolean; message: string; recipient: string }>(
        "/api/settings/test-email",
        { method: "POST" }
      );
      setMessage(`Email di prova inviata a ${result.recipient}.`);
    } catch (err: any) {
      setError(err.message || "Test email fallito.");
    } finally {
      setTesting(false);
    }
  }

  return (
    <main className="min-h-screen p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <Link href="/dashboard" className="text-sm text-blue-700 hover:underline">
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2">Impostazioni notifiche</h1>
          <p className="text-sm text-slate-600 mt-1">
            Configura il canale preferito per le notifiche dei promemoria.
          </p>
        </header>

        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {error}
          </div>
        )}
        {message && (
          <div className="text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg p-3">
            {message}
          </div>
        )}

        {loading ? (
          <div className="bg-white rounded-2xl shadow p-6 text-sm text-slate-600">
            Caricamento...
          </div>
        ) : (
          <form onSubmit={onSave} className="bg-white rounded-2xl shadow p-6 space-y-5">
            <section className="space-y-3">
              <h2 className="text-lg font-semibold">Generale</h2>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.notifications_enabled === "true"}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      notifications_enabled: e.target.checked ? "true" : "false",
                    }))
                  }
                />
                <span className="text-sm">Abilita le notifiche dei promemoria</span>
              </label>

              <div>
                <label className="block text-sm font-medium mb-1">Canale preferito</label>
                <select
                  value={form.notification_channel}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, notification_channel: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
                >
                  <option value="console">Console (solo log, nessuna email)</option>
                  <option value="smtp">Email via SMTP</option>
                </select>
                <p className="text-xs text-slate-500 mt-1">
                  "Console" e' il default sicuro: le notifiche appaiono solo nei log del server.
                </p>
              </div>
            </section>

            {form.notification_channel === "smtp" && (
              <section className="space-y-3 border-t pt-4">
                <h2 className="text-lg font-semibold">Configurazione SMTP</h2>

                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900">
                  <strong>Avviso sicurezza:</strong> la password SMTP viene salvata in chiaro
                  nel database. Usa un account SMTP dedicato e non riutilizzare password
                  sensibili. Questo portale e' pensato per uso personale/familiare.
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Host SMTP *</label>
                    <input
                      type="text"
                      value={form.smtp_host}
                      onChange={(e) => setForm((p) => ({ ...p, smtp_host: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      placeholder="smtp.example.com"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Porta</label>
                    <input
                      type="number"
                      value={form.smtp_port}
                      onChange={(e) => setForm((p) => ({ ...p, smtp_port: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      placeholder="587"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Utente SMTP</label>
                    <input
                      type="text"
                      value={form.smtp_user}
                      onChange={(e) => setForm((p) => ({ ...p, smtp_user: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Password SMTP
                      {settings?.has_smtp_password && (
                        <span className="text-xs text-slate-500 ml-2">(gia' configurata)</span>
                      )}
                    </label>
                    <input
                      type="password"
                      value={form.smtp_password}
                      onChange={(e) => setForm((p) => ({ ...p, smtp_password: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      placeholder="Lascia vuoto per non modificare"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium mb-1">Mittente (From)</label>
                    <input
                      type="email"
                      value={form.smtp_from}
                      onChange={(e) => setForm((p) => ({ ...p, smtp_from: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
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
                      />
                      <span className="text-sm">Usa STARTTLS</span>
                    </label>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={onTestEmail}
                  disabled={testing || !form.smtp_host}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-50"
                >
                  {testing ? "Invio in corso..." : "Invia email di prova"}
                </button>
              </section>
            )}

            <div className="border-t pt-4">
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-slate-900 text-white px-6 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-60"
              >
                {saving ? "Salvataggio..." : "Salva impostazioni"}
              </button>
            </div>
          </form>
        )}

        <footer className="text-xs text-slate-500">
          Il canale "console" e' il default sicuro. Per ricevere email reali configura
          un server SMTP valido e premi "Invia email di prova" prima di abilitare lo scheduler.
        </footer>
      </div>
    </main>
  );
}