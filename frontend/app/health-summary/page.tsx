"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Alert, Badge, Card, EmptyState } from "@/components/ui";

type Patient = { id: string; display_name: string };

type Narrative = {
  patient_id: string;
  status: string;
  generated_at: string;
  overview: string;
  anthropometry: string;
  labs: string;
  therapies: string;
  signals: string[];
  questions_for_doctor: string[];
  disclaimers: string[];
  missing_data: string[];
};

function statusBadge(status: string) {
  switch (status) {
    case "prompt_review":
      return { variant: "danger" as const, label: "consulto consigliato" };
    case "attention":
      return { variant: "warning" as const, label: "attenzione" };
    case "watch":
      return { variant: "info" as const, label: "osservazione" };
    case "no_attention_signals":
      return { variant: "success" as const, label: "nessun segnale" };
    default:
      return { variant: "default" as const, label: "dati insufficienti" };
  }
}

export default function HealthSummaryPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        const me = await apiFetch<Patient>("/api/patients/me");
        setPatient(me);
        const n = await apiFetch<Narrative>(
          `/api/health-summary/narrative?patient_id=${me.id}`
        );
        setNarrative(n);
      } catch (err: any) {
        setError(err.message || "Impossibile caricare la sintesi.");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  const badge = narrative ? statusBadge(narrative.status) : null;

  return (
    <main id="main-content" className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <Link href="/dashboard" className="text-sm text-blue-700 hover:underline">
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2 text-slate-900">
            Sintesi del tuo quadro di salute
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Riepilogo generato da regole deterministiche sui tuoi dati confermati.
            Non e&apos; una diagnosi: e&apos; un punto di partenza per il dialogo col medico.
          </p>
        </header>

        {error && <Alert variant="error">{error}</Alert>}

        {loading ? (
          <Card>
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
            </div>
          </Card>
        ) : !narrative ? (
          <Card>
            <EmptyState
              title="Sintesi non disponibile"
              description="Carica e conferma almeno un referto per costruire il quadro."
            />
          </Card>
        ) : (
          <>
            {badge && (
              <div className="flex items-center gap-3">
                <Badge variant={badge.variant}>{badge.label}</Badge>
                <span className="text-xs text-slate-500">
                  Generato: {new Date(narrative.generated_at).toLocaleString("it-IT")}
                </span>
              </div>
            )}

            <Card>
              <h2 className="text-lg font-semibold mb-2">Quadro generale</h2>
              <p className="text-sm text-slate-700">{narrative.overview}</p>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card>
                <h2 className="text-lg font-semibold mb-2">Antropometria</h2>
                <p className="text-sm text-slate-700">{narrative.anthropometry}</p>
              </Card>
              <Card>
                <h2 className="text-lg font-semibold mb-2">Terapie</h2>
                <p className="text-sm text-slate-700">{narrative.therapies}</p>
              </Card>
            </div>

            <Card>
              <h2 className="text-lg font-semibold mb-2">Laboratorio</h2>
              <p className="text-sm text-slate-700">{narrative.labs}</p>
            </Card>

            {narrative.signals.length > 0 && (
              <Card>
                <h2 className="text-lg font-semibold mb-3">Segnali di attenzione</h2>
                <ul className="space-y-2">
                  {narrative.signals.map((s, i) => (
                    <li key={i} className="text-sm text-slate-700 border-l-4 border-amber-500 pl-3">
                      {s}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <Card>
              <h2 className="text-lg font-semibold mb-3">Domande da portare al medico</h2>
              <ol className="list-decimal list-inside space-y-2">
                {narrative.questions_for_doctor.map((q, i) => (
                  <li key={i} className="text-sm text-slate-800">{q}</li>
                ))}
              </ol>
              <p className="text-xs text-slate-500 mt-3">
                Puoi copiare questo elenco o scaricare l&apos;export dalla pagina Report.
              </p>
            </Card>

            {narrative.missing_data.length > 0 && (
              <Card>
                <h2 className="text-lg font-semibold mb-2">Dati mancanti</h2>
                <ul className="list-disc list-inside text-sm text-slate-600 space-y-1">
                  {narrative.missing_data.map((m, i) => (
                    <li key={i}>{m}</li>
                  ))}
                </ul>
              </Card>
            )}

            <Alert variant="info" title="Limiti di questa sintesi">
              <ul className="list-disc list-inside text-sm space-y-1">
                {narrative.disclaimers.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </Alert>
          </>
        )}

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione personale.
          La sintesi non sostituisce il parere medico.
        </footer>
      </div>
    </main>
  );
}