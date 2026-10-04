"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { API_BASE, apiFetch } from "@/lib/api";
import { Alert, Button, Card } from "@/components/ui";

type Patient = {
  id: string;
  display_name: string;
};

export default function ReportPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [exporting, setExporting] = useState<"" | "named" | "anon">("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    apiFetch<Patient>("/api/patients/me")
      .then(setPatient)
      .catch(() => setPatient(null));
  }, []);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    setSuccess(false);
    try {
      const response = await fetch(`${API_BASE}/api/reports/medical-summary.pdf`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/pdf" },
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Errore ${response.status}: ${text || response.statusText}`);
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `vitasync-riepilogo-esami-${new Date().toISOString().slice(0, 10)}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Impossibile scaricare il report.");
    } finally {
      setDownloading(false);
    }
  }

  async function handleExport(anonymize: boolean) {
    if (!patient) return;
    setExporting(anonymize ? "anon" : "named");
    setError(null);
    setSuccess(false);
    try {
      const url = `${API_BASE}/api/exports/health-summary.md?patient_id=${patient.id}&anonymize=${anonymize}`;
      const response = await fetch(url, { credentials: "include" });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Errore ${response.status}: ${text || response.statusText}`);
      }
      const blob = await response.blob();
      const disp = response.headers.get("Content-Disposition") || "";
      const m = disp.match(/filename="([^"]+)"/);
      const filename = m
        ? m[1]
        : anonymize
          ? "vitasync-export-pseudonimizzato.md"
          : "vitasync-export.md";
      const a = document.createElement("a");
      a.href = window.URL.createObjectURL(blob);
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(a.href);
      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "Export fallito.");
    } finally {
      setExporting("");
    }
  }

  return (
    <main id="main-content" className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <Link href="/dashboard" className="text-sm text-blue-700 hover:underline">
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2 text-slate-900">
            Report ed export per consulto
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Genera il riepilogo PDF o l&apos;export unico da portare al medico o
            allegare a un assistente AI esterno.
          </p>
        </header>

        <Alert variant="warning" title="Avviso Importante">
          <p>
            Questi file sono <strong>strumenti organizzativi personali</strong>.
            Non formulano diagnosi, non sostituiscono il parere del medico e non
            devono essere usati come unica fonte per decisioni cliniche.
          </p>
          <p className="mt-2">
            Includono <strong>solo i valori confermati</strong> da te e
            provenienti da <strong>documenti attivi</strong>.
          </p>
        </Alert>

        {error && <Alert variant="error">{error}</Alert>}
        {success && (
          <Alert variant="success">
            Download avviato. Controlla la cartella dei download del browser.
          </Alert>
        )}

        <Card>
          <h2 className="text-lg font-semibold mb-3">Report PDF per il medico</h2>
          <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
            <li>Elenco degli esami confermati, raggruppati per tipologia.</li>
            <li>Storico dei valori nel tempo con date gg/mm/aaaa.</li>
            <li>Range di riferimento, flag e documento sorgente.</li>
            <li>Watermark &quot;bozza personale - verificare con medico&quot;.</li>
          </ul>
          <div className="pt-4">
            <Button onClick={handleDownload} disabled={downloading} loading={downloading}>
              {downloading ? "Generazione in corso..." : "Scarica Riepilogo PDF"}
            </Button>
          </div>
        </Card>

        <Card>
          <h2 className="text-lg font-semibold mb-3">
            Export unico (Markdown) per medico o AI esterne
          </h2>
          <p className="text-sm text-slate-700">
            Un solo file con profilo, misure, terapie, storico esami, segnali
            deterministici e note di contesto. Generato senza AI: puoi
            allegarlo tu, a mano, a qualsiasi LLM esterno.
          </p>
          <div className="pt-4 flex flex-col sm:flex-row gap-3">
            <Button
              onClick={() => handleExport(false)}
              disabled={exporting !== "" || !patient}
              loading={exporting === "named"}
            >
              {exporting === "named" ? "Generazione..." : "Scarica export nominativo"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => handleExport(true)}
              disabled={exporting !== "" || !patient}
              loading={exporting === "anon"}
            >
              {exporting === "anon" ? "Generazione..." : "Scarica export pseudonimizzato"}
            </Button>
          </div>
          <p className="text-xs text-slate-500 mt-3">
            La versione pseudonimizzata sostituisce nome e titoli dei documenti
            con etichette generiche: preferiscila se alleghi il file a servizi
            AI pubblici o cloud. Tratta comunque il file come dato sensibile.
          </p>
        </Card>

        <footer className="text-xs text-slate-500 pt-2">
          I file vengono generati al momento e scaricati sul tuo dispositivo.
          Nessun dato viene salvato sul server oltre i tuoi documenti.
        </footer>
      </div>
    </main>
  );
}