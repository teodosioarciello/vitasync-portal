"use client";

import Link from "next/link";
import { useState } from "react";
import { API_BASE } from "@/lib/api";
import { Alert, Button, Card } from "@/components/ui";

export default function ReportPage() {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await fetch(`${API_BASE}/api/reports/medical-summary.pdf`, {
        method: "GET",
        credentials: "include",
        headers: {
          "Accept": "application/pdf",
        },
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Errore ${response.status}: ${text || response.statusText}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;

      const filename = `vitasync-riepilogo-esami-${new Date().toISOString().slice(0, 10)}.pdf`;
      a.download = filename;
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

  return (
    <main id="main-content" className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <Link
            href="/dashboard"
            className="text-sm text-blue-700 hover:underline"
          >
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2 text-slate-900">
            Report Esami per Consulto Medico
          </h1>
          <p className="text-sm text-slate-600 mt-1">
            Genera un riepilogo stampabile dei tuoi valori di laboratorio
            confermati.
          </p>
        </header>

        <Alert variant="warning" title="Avviso Importante">
          <p>
            Questo report e&apos; uno{" "}
            <strong>strumento organizzativo personale</strong>. Non formula
            diagnosi, non sostituisce il parere del medico e non deve essere
            usato come unica fonte per decisioni cliniche.
          </p>
          <p className="mt-2">
            Il PDF include <strong>solo i valori confermati</strong> da te e
            provenienti da <strong>documenti attivi</strong> (non nel
            cestino).
          </p>
        </Alert>

        {error && <Alert variant="error">{error}</Alert>}

        {success && (
          <Alert variant="success">
            Download avviato. Controlla la cartella dei download del tuo
            browser.
          </Alert>
        )}

        <Card>
          <h2 className="text-lg font-semibold mb-3">
            Cosa contiene il report?
          </h2>
          <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
            <li>Elenco degli esami confermati, raggruppati per tipologia.</li>
            <li>Storico dei valori nel tempo con date in formato gg/mm/aaaa.</li>
            <li>Range di riferimento e flag (es. normale, alto, basso).</li>
            <li>Riferimento al documento sorgente.</li>
          </ul>

          <div className="pt-4">
            <Button
              onClick={handleDownload}
              disabled={downloading}
              loading={downloading}
            >
              {downloading ? "Generazione in corso..." : "Scarica Riepilogo PDF"}
            </Button>
          </div>
        </Card>

        <footer className="text-xs text-slate-500 pt-2">
          Il file PDF viene generato al momento e scaricato sul tuo
          dispositivo. Nessun dato viene salvato sul server. Tratta il file
          come dato sensibile.
        </footer>
      </div>
    </main>
  );
}