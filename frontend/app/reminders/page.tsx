"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";
import {
  formatDateTime,
  humanReminderStatus,
  humanReminderType,
  isoFromLocalInput,
  reminderStatusClass,
  reminderTypeClass,
  toLocalInputValue,
} from "@/lib/format";

type Patient = {
  id: string;
  display_name: string;
};

type TherapyOption = {
  id: string;
  medicine?: {
    name: string;
  } | null;
  dose?: string | null;
  frequency?: string;
};

type Reminder = {
  id: string;
  patient_id: string;
  therapy_id: string | null;
  title: string;
  reminder_type: string;
  scheduled_at: string;
  status: string;
  recurrence_rule: string | null;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export default function RemindersPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [therapies, setTherapies] = useState<TherapyOption[]>([]);
  const [items, setItems] = useState<Reminder[]>([]);
  const [filter, setFilter] = useState("");
  const [notifiedIds, setNotifiedIds] = useState<Set<string>>(new Set());

  const [form, setForm] = useState<Record<string, string>>(() => ({
    title: "",
    reminder_type: "medication",
    scheduled_at: toLocalInputValue(new Date(Date.now() + 60 * 60 * 1000)),
    therapy_id: "",
    notes: "",
  }));

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const me = await apiFetch<Patient>("/api/patients/me");
      setPatient(me);

      const qs = filter ? `&status=${encodeURIComponent(filter)}` : "";

      const [therapyList, reminderList, notifiedList] = await Promise.all([
        apiFetch<TherapyOption[]>(`/api/therapies?patient_id=${me.id}`),
        apiFetch<Reminder[]>(`/api/reminders?patient_id=${me.id}${qs}`),
        apiFetch<string[]>(`/api/notifications/reminders-status?patient_id=${me.id}`).catch(() => []),
      ]);

      setTherapies(therapyList);
      setItems(reminderList);
      setNotifiedIds(new Set(notifiedList));
    } catch (err: any) {
      setError(err.message || "Impossibile caricare i promemoria.");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!patient) return;

    const title = form.title.trim();
    if (!title) {
      setError("Il titolo del promemoria e' obbligatorio.");
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const scheduledIso = isoFromLocalInput(form.scheduled_at);

      const payload = {
        patient_id: patient.id,
        therapy_id: form.therapy_id || null,
        title,
        reminder_type: form.reminder_type,
        scheduled_at: scheduledIso,
        status: "pending",
        notes: form.notes.trim() || null,
      };

      await apiFetch<Reminder>("/api/reminders", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setForm((prev) => ({
        ...prev,
        title: "",
        notes: "",
        therapy_id: "",
        scheduled_at: toLocalInputValue(
          new Date(Date.now() + 60 * 60 * 1000)
        ),
      }));

      setMessage("Promemoria creato.");
      await load();
    } catch (err: any) {
      setError(err.message || "Creazione promemoria fallita.");
    } finally {
      setSaving(false);
    }
  }

  async function updateReminder(
    id: string,
    payload: Record<string, unknown>,
    success: string
  ) {
    setBusyId(id);
    setError(null);
    setMessage(null);

    try {
      await apiFetch<Reminder>(`/api/reminders/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });

      setMessage(success);
      await load();
    } catch (err: any) {
      setError(err.message || "Aggiornamento promemoria fallito.");
    } finally {
      setBusyId(null);
    }
  }

  function therapyLabel(therapy: TherapyOption): string {
    return therapy.medicine?.name || "Terapia";
  }

  const now = new Date();

  return (
    <main className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-blue-700 hover:underline"
            >
              &larr; Torna alla dashboard
            </Link>
            <h1 className="text-2xl font-bold mt-1">Promemoria</h1>
            <p className="text-sm text-slate-600">
              Promemoria per {patient?.display_name || "..."}.
            </p>
          </div>

          <button
            onClick={() => void load()}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100 disabled:opacity-60"
          >
            {loading ? "Caricamento..." : "Ricarica"}
          </button>
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

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Nuovo promemoria</h2>

          <form onSubmit={onCreate} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-1">
                Titolo *
              </label>
              <input
                value={form.title}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, title: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="Es. Assunzione sera"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Tipo</label>
              <select
                value={form.reminder_type}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    reminder_type: e.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
              >
                <option value="medication">farmaco</option>
                <option value="appointment">visita/controllo</option>
                <option value="refill">rinnovo ricetta</option>
                <option value="measurement">misurazione</option>
                <option value="other">altro</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Data e ora *
              </label>
              <input
                type="datetime-local"
                value={form.scheduled_at}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    scheduled_at: e.target.value,
                  }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Terapia collegata
              </label>
              <select
                value={form.therapy_id}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, therapy_id: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
              >
                <option value="">Nessuna</option>
                {therapies.map((t) => (
                  <option key={t.id} value={t.id}>
                    {therapyLabel(t)}
                    {t.dose ? ` - ${t.dose}` : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-3">
              <label className="block text-sm font-medium mb-1">Note</label>
              <textarea
                value={form.notes}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, notes: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-[80px]"
                placeholder="Note sintetiche, non dati reali sensibili."
              />
            </div>

            <div className="md:col-span-3">
              <button
                type="submit"
                disabled={saving || !form.title.trim()}
                className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-60"
              >
                {saving ? "Creazione..." : "Crea promemoria"}
              </button>
            </div>
          </form>
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
            <h2 className="text-lg font-semibold">Elenco promemoria</h2>

            <div className="w-full md:w-64">
              <label className="block text-sm font-medium mb-1">Filtro stato</label>
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
              >
                <option value="">Tutti</option>
                <option value="pending">da fare</option>
                <option value="snoozed">posticipati</option>
                <option value="done">fatti</option>
                <option value="cancelled">annullati</option>
              </select>
            </div>
          </div>
        </section>

        {loading ? (
          <div className="bg-white rounded-2xl shadow p-6 text-sm text-slate-600">
            Caricamento...
          </div>
        ) : items.length === 0 ? (
          <div className="bg-white rounded-2xl shadow p-6 text-sm text-slate-600">
            Nessun promemoria trovato.
          </div>
        ) : (
          <section className="space-y-4">
            {items.map((r) => {
              const scheduled = new Date(r.scheduled_at);
              const isOverdue =
                r.status === "pending" && scheduled.getTime() < now.getTime();

              return (
                <article
                  key={r.id}
                  className="bg-white rounded-2xl shadow p-6 space-y-4"
                >
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold">{r.title}</h3>
                      <p className="text-sm text-slate-600">
                        {formatDateTime(r.scheduled_at)}
                      </p>
                      {isOverdue && (
                        <p className="text-xs text-red-700 mt-1">
                          scaduto
                        </p>
                      )}
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <span
                        className={`inline-block px-3 py-1 rounded-full border text-xs font-medium ${reminderTypeClass(
                          r.reminder_type
                        )}`}
                      >
                        {humanReminderType(r.reminder_type)}
                      </span>

                      <span
                        className={`inline-block px-3 py-1 rounded-full border text-xs font-medium ${reminderStatusClass(
                          r.status
                        )}`}
                      >
                        {humanReminderStatus(r.status)}
                      </span>

                      {notifiedIds.has(r.id) && (
                        <span className="inline-block px-3 py-1 rounded-full border border-emerald-200 bg-emerald-50 text-xs font-medium text-emerald-700">
                          Notificato
                        </span>
                      )}
                    </div>
                  </div>

                  {r.notes && (
                    <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3">
                      {r.notes}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() =>
                        void updateReminder(
                          r.id,
                          { status: "done" },
                          "Promemoria segnato come fatto."
                        )
                      }
                      disabled={busyId === r.id || r.status === "done"}
                      className="rounded-lg border border-green-200 px-3 py-1 text-xs text-green-800 hover:bg-green-50 disabled:opacity-50"
                    >
                      Fatto
                    </button>

                    <button
                      onClick={() => {
                        const next = new Date(
                          scheduled.getTime() + 60 * 60 * 1000
                        );
                        void updateReminder(
                          r.id,
                          {
                            scheduled_at: next.toISOString(),
                            status: "snoozed",
                          },
                          "Promemoria posticipato di 1 ora."
                        );
                      }}
                      disabled={busyId === r.id || r.status === "cancelled"}
                      className="rounded-lg border border-amber-200 px-3 py-1 text-xs text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                    >
                      Posticipa 1h
                    </button>

                    <button
                      onClick={() =>
                        void updateReminder(
                          r.id,
                          { status: "pending" },
                          "Promemoria ripristinato."
                        )
                      }
                      disabled={busyId === r.id || r.status === "pending"}
                      className="rounded-lg border border-blue-200 px-3 py-1 text-xs text-blue-800 hover:bg-blue-50 disabled:opacity-50"
                    >
                      Ripristina
                    </button>

                    <button
                      onClick={() =>
                        void updateReminder(
                          r.id,
                          { status: "cancelled" },
                          "Promemoria annullato."
                        )
                      }
                      disabled={busyId === r.id || r.status === "cancelled"}
                      className="rounded-lg border border-red-200 px-3 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      Annulla
                    </button>
                  </div>
                </article>
              );
            })}
          </section>
        )}

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. I promemoria non sostituiscono prescrizioni,
          controlli medici o parere professionale.
        </footer>
      </div>
    </main>
  );
}