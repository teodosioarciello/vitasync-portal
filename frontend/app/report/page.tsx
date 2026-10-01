"use client";

import Link from "next/link";
import { useState } from "react";
import { API_BASE } from "@/lib/api";

export default function ReportPage() {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleDownload() {
    setDownloading(true);
    setError(null);
    setSuccess(false);

    try {
      // Usiamo fetch nativo invece di apiFetch per gestire correttamente i blob
      const response = await fetch(`${API_BASE}/api/reports/medical-summary.pdf`, {
        method: "GET",
        credentials: "include", // Invia i cookie di sessione
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
    <main className="min-h-screen p-6">
      <div className="max-w-3xl mx-auto space-y-6">
        <header>
          <Link
            href="/dashboard"
            className="text-sm text-blue-700 hover:underline"
          >
            &larr; Torna alla dashboard
          </Link>
          <h1 className="text-2xl font-bold mt-2">Report Esami per Consulto Medico</h1>
          <p className="text-sm text-slate-600 mt-1">
            Genera un riepilogo stampabile dei tuoi valori di laboratorio confermati.
          </p>
        </header>

        <section className="bg-amber-50 border border-amber-200 rounded-2xl p-5 text-sm text-amber-900 space-y-2">
          <h2 className="font-semibold text-amber-800">Avviso Importante</h2>
          <p>
            Questo report è uno <strong>strumento organizzativo personale</strong>. 
            Non formula diagnosi, non sostituisce il parere del medico e non deve 
            essere usato come unica fonte per decisioni cliniche.
          </p>
          <p>
            Il PDF include <strong>solo i valori confermati</strong> da te e 
            provenienti da <strong>documenti attivi</strong> (non nel cestino).
          </p>
        </section>

        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {error}
          </div>
        )}

        {success && (
          <div className="text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg p-3">
            Download avviato. Controlla la cartella dei download del tuo browser.
          </div>
        )}

        <section className="bg-white rounded-2xl shadow p-6 space-y-4">
          <h2 className="text-lg font-semibold">Cosa contiene il report?</h2>
          <ul className="list-disc list-inside text-sm text-slate-700 space-y-1">
            <li>Elenco degli esami confermati, raggruppati per tipologia.</li>
            <li>Storico dei valori nel tempo con date di estrazione.</li>
            <li>Range di riferimento e flag (es. normale, alto, basso).</li>
            <li>Riferimento al documento sorgente.</li>
          </ul>

          <div className="pt-4">
            <button
              onClick={handleDownload}
              disabled={downloading}
              className="w-full md:w-auto rounded-lg bg-slate-900 text-white px-6 py-3 text-sm font-medium hover:bg-slate-800 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {downloading ? "Generazione in corso..." : "Scarica Riepilogo PDF"}
            </button>
          </div>
        </section>

        <footer className="text-xs text-slate-500 pt-4">
          Il file PDF viene generato al momento e scaricato sul tuo dispositivo. 
          Nessun dato viene salvato sul server. Tratta il file come dato sensibile.
        </footer>
      </div>
    </main>
  );
}