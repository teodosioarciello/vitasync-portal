"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Alert, Badge, Button, Card, EmptyState } from "@/components/ui";

type Patient = {
  id: string;
  display_name: string;
  is_minor: boolean;
};

type WeightMeasurement = {
  id: string;
  patient_id: string;
  measured_at: string;
  weight_kg: number;
  source: string;
  notes: string | null;
  created_at: string;
};

type BmiResult = {
  patient_id: string;
  bmi: number | null;
  category: string | null;
  category_it: string | null;
  is_minor: boolean;
  has_sufficient_data: boolean;
  note: string | null;
  weight_kg: number | null;
  height_cm: number | null;
  age_years: number | null;
};

function bmiVariant(category: string | null): "default" | "success" | "warning" | "danger" | "info" {
  switch (category) {
    case "normal":
      return "success";
    case "overweight":
      return "warning";
    case "obese":
      return "danger";
    case "underweight":
      return "info";
    default:
      return "default";
  }
}

export default function MeasurementsPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [bmi, setBmi] = useState<BmiResult | null>(null);
  const [height, setHeight] = useState<string>("");
  const [weights, setWeights] = useState<WeightMeasurement[]>([]);
  const [weightForm, setWeightForm] = useState({
    measured_at: new Date().toISOString().slice(0, 10),
    weight_kg: "",
    notes: "",
  });
  const [loading, setLoading] = useState(true);
  const [savingHeight, setSavingHeight] = useState(false);
  const [savingWeight, setSavingWeight] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadAll(patientId: string) {
    const [bmiData, heightData, weightsData] = await Promise.all([
      apiFetch<BmiResult>(`/api/measurements/bmi?patient_id=${patientId}`),
      apiFetch<{ patient_id: string; height_cm: number | null }>(
        `/api/measurements/height?patient_id=${patientId}`
      ),
      apiFetch<WeightMeasurement[]>(
        `/api/measurements/weight?patient_id=${patientId}&limit=50`
      ),
    ]);
    setBmi(bmiData);
    setHeight(heightData.height_cm != null ? String(heightData.height_cm) : "");
    setWeights(weightsData);
  }

  useEffect(() => {
    async function init() {
      try {
        const me = await apiFetch<Patient>("/api/patients/me");
        setPatient(me);
        await loadAll(me.id);
      } catch (err: any) {
        setError(err.message || "Impossibile caricare le misure.");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  async function onSaveHeight(e: React.FormEvent) {
    e.preventDefault();
    if (!patient) return;
    setSavingHeight(true);
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/api/measurements/height?patient_id=${patient.id}`, {
        method: "PUT",
        body: JSON.stringify({ height_cm: Number(height) }),
      });
      setMessage("Altezza aggiornata.");
      await loadAll(patient.id);
    } catch (err: any) {
      setError(err.message || "Salvataggio altezza fallito.");
    } finally {
      setSavingHeight(false);
    }
  }

  async function onSaveWeight(e: React.FormEvent) {
    e.preventDefault();
    if (!patient) return;
    setSavingWeight(true);
    setError(null);
    setMessage(null);
    try {
      await apiFetch(`/api/measurements/weight?patient_id=${patient.id}`, {
        method: "POST",
        body: JSON.stringify({
          measured_at: weightForm.measured_at,
          weight_kg: Number(weightForm.weight_kg),
          notes: weightForm.notes || null,
        }),
      });
      setMessage("Misura peso aggiunta.");
      setWeightForm((prev) => ({ ...prev, weight_kg: "", notes: "" }));
      await loadAll(patient.id);
    } catch (err: any) {
      setError(err.message || "Salvataggio peso fallito.");
    } finally {
      setSavingWeight(false);
    }
  }

  return (
    <main id="main-content" className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-4xl mx-auto space-y-6">
        <header>
          <Link
            href="/dashboard"
            className="text-sm text-blue-700 hover:underline"
          >
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2 text-slate-900">
            Misure antropometriche
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Registra peso e altezza per calcolare il BMI e seguire il trend nel tempo.
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
          <>
            <Card>
              <h2 className="text-lg font-semibold mb-4">BMI</h2>

              {bmi?.is_minor ? (
                <Alert variant="info" title="Paziente minorenne">
                  Il BMI adulto non viene calcolato. Per la valutazione della
                  crescita e&apos; necessaria una valutazione pediatrica.
                </Alert>
              ) : bmi?.has_sufficient_data ? (
                <div className="flex items-center gap-4">
                  <span className="text-4xl font-bold text-slate-900">
                    {bmi.bmi}
                  </span>
                  <Badge variant={bmiVariant(bmi.category)}>
                    {bmi.category_it}
                  </Badge>
                </div>
              ) : (
                <Alert variant="warning" title="Dati insufficienti">
                  {bmi?.note ||
                    "Inserisci altezza e peso per calcolare il BMI."}
                </Alert>
              )}

              <p className="text-xs text-slate-500 mt-4">
                Il BMI e&apos; calcolato sui dati inseriti dall&apos;utente e non
                sostituisce una valutazione clinica.
              </p>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <h2 className="text-lg font-semibold mb-4">Altezza</h2>
                <form onSubmit={onSaveHeight} className="space-y-4">
                  <div>
                    <label
                      htmlFor="measurements-height"
                      className="block text-sm font-medium mb-1"
                    >
                      Altezza (cm)
                    </label>
                    <input
                      id="measurements-height"
                      type="number"
                      step="0.1"
                      min="30"
                      max="300"
                      value={height}
                      onChange={(e) => setHeight(e.target.value)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      placeholder="Es. 175"
                      required
                    />
                  </div>
                  <Button type="submit" disabled={savingHeight} loading={savingHeight}>
                    {savingHeight ? "Salvataggio..." : "Salva altezza"}
                  </Button>
                </form>
              </Card>

              <Card>
                <h2 className="text-lg font-semibold mb-4">Aggiungi peso</h2>
                <form onSubmit={onSaveWeight} className="space-y-4">
                  <div>
                    <label
                      htmlFor="measurements-weight-date"
                      className="block text-sm font-medium mb-1"
                    >
                      Data misura
                    </label>
                    <input
                      id="measurements-weight-date"
                      type="date"
                      value={weightForm.measured_at}
                      onChange={(e) =>
                        setWeightForm((prev) => ({
                          ...prev,
                          measured_at: e.target.value,
                        }))
                      }
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      required
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="measurements-weight-kg"
                      className="block text-sm font-medium mb-1"
                    >
                      Peso (kg)
                    </label>
                    <input
                      id="measurements-weight-kg"
                      type="number"
                      step="0.1"
                      min="1"
                      max="500"
                      value={weightForm.weight_kg}
                      onChange={(e) =>
                        setWeightForm((prev) => ({
                          ...prev,
                          weight_kg: e.target.value,
                        }))
                      }
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      placeholder="Es. 72.5"
                      required
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="measurements-weight-notes"
                      className="block text-sm font-medium mb-1"
                    >
                      Note
                    </label>
                    <input
                      id="measurements-weight-notes"
                      type="text"
                      value={weightForm.notes}
                      onChange={(e) =>
                        setWeightForm((prev) => ({
                          ...prev,
                          notes: e.target.value,
                        }))
                      }
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                      placeholder="Opzionale"
                    />
                  </div>
                  <Button type="submit" disabled={savingWeight} loading={savingWeight}>
                    {savingWeight ? "Salvataggio..." : "Aggiungi misura"}
                  </Button>
                </form>
              </Card>
            </div>

            <Card className="space-y-4">
              <h2 className="text-lg font-semibold">Storico peso</h2>

              {weights.length === 0 ? (
                <EmptyState
                  title="Nessuna misura registrata"
                  description="Aggiungi la prima misura di peso per iniziare a seguire il trend."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table
                    className="w-full text-sm"
                    aria-label="Storico misure peso"
                  >
                    <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="px-4 py-3" scope="col">Data</th>
                        <th className="px-4 py-3" scope="col">Peso (kg)</th>
                        <th className="px-4 py-3" scope="col">Note</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {weights.map((w) => (
                        <tr key={w.id}>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {w.measured_at}
                          </td>
                          <td className="px-4 py-3 font-medium">
                            {w.weight_kg}
                          </td>
                          <td className="px-4 py-3 text-slate-600">
                            {w.notes || "-"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </>
        )}

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione personale.
          Il BMI e le misure non sostituiscono il parere medico.
        </footer>
      </div>
    </main>
  );
}