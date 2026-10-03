"use client";

import Link from "next/link";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Alert, Button, Card, EmptyState } from "@/components/ui";

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
    <main id="main-content" className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-blue-700 hover:underline"
            >
              &larr; Torna alla dashboard
            </Link>
            <h1 className="text-2xl font-bold mt-1 text-slate-900">
              Medicinali
            </h1>
            <p className="text-sm text-slate-600">
              Elenco farmaci disponibili per {patient?.display_name || "..."}.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void load()}
            disabled={loading}
            loading={loading}
          >
            {loading ? "Caricamento..." : "Ricarica"}
          </Button>
        </header>

        {error && <Alert variant="error">{error}</Alert>}

        {message && <Alert variant="success">{message}</Alert>}

        <Card>
          <h2 className="text-lg font-semibold mb-4">Nuovo medicinale</h2>

          <form
            onSubmit={onCreate}
            className="grid grid-cols-1 md:grid-cols-2 gap-4"
          >
            <div>
              <label htmlFor="medicine-name" className="block text-sm font-medium mb-1">Nome *</label>
              <input id="medicine-name"
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
              <label htmlFor="medicine-generic-name" className="block text-sm font-medium mb-1">
                Principio attivo
              </label>
              <input id="medicine-generic-name"
                value={form.generic_name}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, generic_name: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="Es. Paracetamolo"
              />
            </div>

            <div>
              <label htmlFor="medicine-form" className="block text-sm font-medium mb-1">Forma</label>
              <input id="medicine-form"
                value={form.form}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, form: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="compressa, sciroppo, gocce..."
              />
            </div>

            <div>
              <label htmlFor="medicine-strength" className="block text-sm font-medium mb-1">Dosaggio</label>
              <input id="medicine-strength"
                value={form.strength}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, strength: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                placeholder="500 mg, 1 ml..."
              />
            </div>

            <div className="md:col-span-2">
              <label htmlFor="medicine-notes" className="block text-sm font-medium mb-1">Note</label>
              <textarea id="medicine-notes"
                value={form.notes}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, notes: e.target.value }))
                }
                className="w-full rounded-lg border border-slate-300 px-3 py-2 min-h-[90px]"
                placeholder="Note sintetiche, non dati reali sensibili."
              />
            </div>

            <div className="md:col-span-2">
              <Button
                type="submit"
                variant="primary"
                loading={saving}
                disabled={!form.name.trim()}
              >
                {saving ? "Creazione..." : "Crea medicinale"}
              </Button>
            </div>
          </form>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold mb-4">Elenco medicinali</h2>

          {loading ? (
            <p className="text-sm text-slate-600">Caricamento...</p>
          ) : items.length === 0 ? (
            <EmptyState
              title="Nessun medicinale"
              description="Nessun medicinale presente."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label="Elenco medicinali">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3" scope="col">Nome</th>
                    <th className="px-4 py-3" scope="col">Principio attivo</th>
                    <th className="px-4 py-3" scope="col">Forma</th>
                    <th className="px-4 py-3" scope="col">Dosaggio</th>
                    <th className="px-4 py-3" scope="col">Note</th>
                    <th className="px-4 py-3" scope="col">Aggiornato</th>
                    <th className="px-4 py-3" scope="col"><span className="sr-only">Azioni</span></th>
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
                        <Button
                          size="sm"
                          variant="dangerOutline"
                          onClick={() => void onDelete(item)}
                          disabled={busyId === item.id}
                          loading={busyId === item.id}
                        >
                          Elimina
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. I dati farmaci/terapie sono inseriti
          dall&apos;utente e non sostituiscono il parere medico.
        </footer>
      </div>
    </main>
  );
}