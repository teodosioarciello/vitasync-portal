"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";
import {
  formatDate,
  humanFrequency,
  humanTherapyStatus,
  therapyStatusClass,
} from "@/lib/format";

type Patient = {
  id: string;
  display_name: string;
};

type Medicine = {
  id: string;
  name: string;
  strength: string | null;
  form: string | null;
};

type Therapy = {
  id: string;
  patient_id: string;
  medicine_id: string;
  medicine?: Medicine | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  frequency: string;
  dose: string | null;
  route: string | null;
  instructions: string | null;
  prescribed_by: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

const emptyTherapyForm: Record<string, string> = {
  medicine_id: "",
  status: "active",
  frequency: "once_daily",
  dose: "",
  route: "",
  instructions: "",
  prescribed_by: "",
  start_date: "",
  end_date: "",
  notes: "",
};

export default function TherapiesPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [medicines, setMedicines] = useState<Medicine[]>([]);
  const [items, setItems] = useState<Therapy[]>([]);
  const [form, setForm] = useState<Record<string, string>>(emptyTherapyForm);

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

      const [medList, therapyList] = await Promise.all([
        apiFetch<Medicine[]>(`/api/medicines?patient_id=${me.id}`),
        apiFetch<Therapy[]>(`/api/therapies?patient_id=${me.id}`),
      ]);

      setMedicines(medList);
      setItems(therapyList);
    } catch (err: any) {
      setError(err.message || "Impossibile caricare le terapie.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    if (!patient) return;

    if (!form.medicine_id) {
      setError("Seleziona un medicinale.");
      return;
    }

    if (form.start_date && form.end_date && form.end_date < form.start_date) {
      setError("La data di fine non puo' essere precedente alla data di inizio.");
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const payload = {
        patient_id: patient.id,
        medicine_id: form.medicine_id,
        status: form.status,
        frequency: form.frequency,
        dose: form.dose.trim() || null,
        route: form.route.trim() || null,
        instructions: form.instructions.trim() || null,
        prescribed_by: form.prescribed_by.trim() || null,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
        notes: form.notes.trim() || null,
      };

      await apiFetch<Therapy>("/api/therapies", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setForm({ ...emptyTherapyForm });
      setMessage("Terapia creata.");
      await load();
    } catch (err: any) {
      setError(err.message || "Creazione terapia fallita.");
    } finally {
      setSaving(false);
    }
  }

  async function updateStatus(therapy: Therapy, status: string) {
    setBusyId(therapy.id);
    setError(null);
    setMessage(null);

    try {
      const updated = await apiFetch<Therapy>(`/api/therapies/${therapy.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });

      setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      setMessage(`Stato aggiornato: ${humanTherapyStatus(updated.status)}.`);
    } catch (err: any) {
      setError(err.message || "Aggiornamento stato fallito.");
    } finally {
      setBusyId(null);
    }
  }

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
            <h1 className="text-2xl font-bold mt-1">Terapie</h1>
            <p className="text-sm text-slate-600">
              Terapie farmacologiche per {patient?.display_name || "..."}.
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
          <h2 className="text-lg font-semibold mb-4">Nuova terapia</h2>

          {medicines.length === 0 ? (
            <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3">
              Prima di creare una terapia, aggiungi almeno un medicinale nella
              pagina Medicinali.
            </div>
          ) : (
            <form
              onSubmit={onCreate}
              className="grid grid-cols-1 md:grid-cols-3 gap-4"
            >
              <div>
                <label className="block text-sm font-medium mb-1">
                  Medicinale *
                </label>
                <select
                  value={form.medicine_id}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      medicine_id: e.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
                  required
                >
                  <option value="">Seleziona...</option>
                  {medicines.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                      {m.strength ? ` - ${m.strength}` : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Stato</label>
                <select
                  value={form.status}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, status: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
                >
                  <option value="active">attiva</option>
                  <option value="paused">in pausa</option>
                  <option value="completed">completata</option>
                  <option value="cancelled">annullata</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Frequenza
                </label>
                <select
                  value={form.frequency}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, frequency: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white"
                >
                  <option value="once_daily">1 volta al giorno</option>
                  <option value="twice_daily">2 volte al giorno</option>
                  <option value="three_times_daily">3 volte al giorno</option>
                  <option value="four_times_daily">4 volte al giorno</option>
                  <option value="every_other_day">a giorni alterni</option>
                  <option value="weekly">settimanale</option>
                  <option value="as_needed">al bisogno</option>
                  <option value="custom">personalizzata</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Dose</label>
                <input
                  value={form.dose}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, dose: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="1 compressa"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Via</label>
                <input
                  value={form.route}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, route: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="orale, cutanea..."
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Prescritta da
                </label>
                <input
                  value={form.prescribed_by}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      prescribed_by: e.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  placeholder="Medico fixture"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Data inizio
                </label>
                <input
                  type="date"
                  value={form.start_date}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, start_date: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Data fine
                </label>
                <input
                  type="date"
                  value={form.end_date}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, end_date: e.target.value }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </div>

              <div className="md:col-span-3">
                <label className="block text-sm font-medium mb-1">
                  Istruzioni
                </label>
                <textarea
                  value={form.instructions}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      instructions: e.target.value,
                    }))
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-[80px]"
                  placeholder="Es. assumere dopo i pasti"
                />
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
                  disabled={saving || !form.medicine_id}
                  className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-60"
                >
                  {saving ? "Creazione..." : "Crea terapia"}
                </button>
              </div>
            </form>
          )}
        </section>

        <section className="space-y-4">
          <h2 className="text-lg font-semibold">Elenco terapie</h2>

          {loading ? (
            <div className="bg-white rounded-2xl shadow p-6 text-sm text-slate-600">
              Caricamento...
            </div>
          ) : items.length === 0 ? (
            <div className="bg-white rounded-2xl shadow p-6 text-sm text-slate-600">
              Nessuna terapia presente.
            </div>
          ) : (
            items.map((t) => (
              <article
                key={t.id}
                className="bg-white rounded-2xl shadow p-6 space-y-4"
              >
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold">
                      {t.medicine?.name || "Medicinale"}
                    </h3>
                    <p className="text-sm text-slate-600">
                      {humanFrequency(t.frequency)}
                      {t.dose ? ` - ${t.dose}` : ""}
                      {t.route ? ` - ${t.route}` : ""}
                    </p>
                  </div>

                  <span
                    className={`inline-block px-3 py-1 rounded-full border text-xs font-medium ${therapyStatusClass(
                      t.status
                    )}`}
                  >
                    {humanTherapyStatus(t.status)}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
                  <div>
                    <div className="text-xs uppercase text-slate-500">
                      Inizio
                    </div>
                    <div>{formatDate(t.start_date)}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-500">Fine</div>
                    <div>{formatDate(t.end_date)}</div>
                  </div>
                  <div>
                    <div className="text-xs uppercase text-slate-500">
                      Prescritta da
                    </div>
                    <div>{t.prescribed_by || "-"}</div>
                  </div>
                </div>

                {(t.instructions || t.notes) && (
                  <div className="text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
                    {t.instructions && (
                      <p>
                        <span className="font-medium">Istruzioni:</span>{" "}
                        {t.instructions}
                      </p>
                    )}
                    {t.notes && (
                      <p>
                        <span className="font-medium">Note:</span> {t.notes}
                      </p>
                    )}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => void updateStatus(t, "active")}
                    disabled={busyId === t.id || t.status === "active"}
                    className="rounded-lg border border-green-200 px-3 py-1 text-xs text-green-800 hover:bg-green-50 disabled:opacity-50"
                  >
                    Riattiva
                  </button>

                  <button
                    onClick={() => void updateStatus(t, "paused")}
                    disabled={busyId === t.id || t.status === "paused"}
                    className="rounded-lg border border-amber-200 px-3 py-1 text-xs text-amber-800 hover:bg-amber-50 disabled:opacity-50"
                  >
                    Pausa
                  </button>

                  <button
                    onClick={() => void updateStatus(t, "completed")}
                    disabled={
                      busyId === t.id ||
                      t.status === "completed" ||
                      t.status === "cancelled"
                    }
                    className="rounded-lg border border-slate-300 px-3 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50"
                  >
                    Completa
                  </button>

                  <button
                    onClick={() => void updateStatus(t, "cancelled")}
                    disabled={
                      busyId === t.id ||
                      t.status === "completed" ||
                      t.status === "cancelled"
                    }
                    className="rounded-lg border border-red-200 px-3 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Annulla
                  </button>
                </div>
              </article>
            ))
          )}
        </section>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. Le terapie sono gestite dall&apos;utente e non
          sostituiscono la prescrizione o il parere medico.
        </footer>
      </div>
    </main>
  );
}