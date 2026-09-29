"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

type Patient = {
  id: string;
  display_name: string;
};

type Medicine = {
  id: string;
  patient_id: string;
  name: string;
  generic_name: string | null;
  form: string | null;
  strength: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export default function MedicinesPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [items, setItems] = useState<Medicine[]>([]);
  const [form, setForm] = useState<Record<string, string>>({
    name: "",
    generic_name: "",
    form: "",
    strength: "",
    notes: "",
  });

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

      const list = await apiFetch<Medicine[]>(
        `/api/medicines?patient_id=${me.id}`
      );
      setItems(list);
    } catch (err: any) {
      setError(err.message || "Impossibile caricare i medicinali.");
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

    const name = form.name.trim();
    if (!name) {
      setError("Il nome del medicinale e' obbligatorio.");
      return;
    }

    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const payload = {
        patient_id: patient.id,
        name,
        generic_name: form.generic_name.trim() || null,
        form: form.form.trim() || null,
        strength: form.strength.trim() || null,
        notes: form.notes.trim() || null,
      };

      const created = await apiFetch<Medicine>("/api/medicines", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setItems((prev) =>
        [...prev, created].sort((a, b) => a.name.localeCompare(b.name))
      );

      setForm({
        name: "",
        generic_name: "",
        form: "",
        strength: "",
        notes: "",
      });

      setMessage(`Medicinale creato: ${created.name}`);
    } catch (err: any) {
      setError(err.message || "Creazione medicinale fallita.");
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(item: Medicine) {
    if (!window.confirm(`Eliminare il medicinale "${item.name}"?`)) return;

    setBusyId(item.id);
    setError(null);
    setMessage(null);

    try {
      await apiFetch<{ detail: string }>(`/api/medicines/${item.id}`, {
        method: "DELETE",
      });

      setItems((prev) => prev.filter((x) => x.id !== item.id));
      setMessage("Medicinale eliminato.");
    } catch (err: any) {
      setError(err.message || "Eliminazione fallita.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <main className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-blue-700 hover:underline"
            >
              &larr; Torna alla dashboard
            </Link>
            <h1 className="text-2xl font-bold mt-1">Medicinali</h1>
            <p className="text-sm text-slate-600">
              Elenco farmaci disponibili per {patient?.display_name || "..."}.
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
          <h2 className="text-lg font-semibold mb-4">Nuovo medicinale</h2>

          <form onSubmit={onCreate} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Nome *</label>
              <input
                value={form.name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, name: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="Es. Paracetamolo 500 mg"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">
                Principio attivo
              </label>
              <input
                value={form.generic_name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, generic_name: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="Es. Paracetamolo"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Forma</label>
              <input
                value={form.form}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, form: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="compressa, sciroppo, gocce..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Dosaggio</label>
              <input
                value={form.strength}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, strength: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="500 mg, 1 ml..."
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium mb-1">Note</label>
              <textarea
                value={form.notes}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, notes: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-[90px]"
                placeholder="Note sintetiche, non dati reali sensibili."
              />
            </div>

            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={saving || !form.name.trim()}
                className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-60"
              >
                {saving ? "Creazione..." : "Crea medicinale"}
              </button>
            </div>
          </form>
        </section>

        <section className="bg-white rounded-2xl shadow overflow-hidden">
          <div className="p-6 border-b border-slate-200">
            <h2 className="text-lg font-semibold">Elenco medicinali</h2>
          </div>

          {loading ? (
            <div className="p-6 text-sm text-slate-600">Caricamento...</div>
          ) : items.length === 0 ? (
            <div className="p-6 text-sm text-slate-600">
              Nessun medicinale presente.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Nome</th>
                    <th className="px-4 py-3">Principio attivo</th>
                    <th className="px-4 py-3">Forma</th>
                    <th className="px-4 py-3">Dosaggio</th>
                    <th className="px-4 py-3">Note</th>
                    <th className="px-4 py-3">Aggiornato</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-4 py-3 font-medium">{item.name}</td>
                      <td className="px-4 py-3 text-slate-600">
                        {item.generic_name || "-"}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {item.form || "-"}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {item.strength || "-"}
                      </td>
                      <td className="px-4 py-3 text-slate-600 max-w-xs truncate">
                        {item.notes || "-"}
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-500 whitespace-nowrap">
                        {formatDateTime(item.updated_at)}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => void onDelete(item)}
                          disabled={busyId === item.id}
                          className="rounded-lg border border-red-200 px-3 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          {busyId === item.id ? "..." : "Elimina"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. I dati farmaci/terapie sono inseriti
          dall&apos;utente e non sostituiscono il parere medico.
        </footer>
      </div>
    </main>
  );
}