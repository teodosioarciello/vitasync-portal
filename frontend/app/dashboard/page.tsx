"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { API_BASE, apiFetch } from "@/lib/api";

type User = {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
  email_verified: boolean;
};

type Patient = {
  id: string;
  family_id: string;
  display_name: string;
  relationship_to_owner: string;
};

type DocumentItem = {
  id: string;
  title: string;
  document_type: string;
  processing_status: string;
};

export default function DashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const me = await apiFetch<User>("/api/auth/me");
        setUser(me);

        const myPatient = await apiFetch<Patient>("/api/patients/me");
        setPatient(myPatient);

        const docs = await apiFetch<DocumentItem[]>(
          `/api/documents?patient_id=${myPatient.id}`
        );
        setDocuments(docs);
      } catch (err: any) {
        setError(err.message || "Impossibile caricare i dati.");
        router.replace("/login");
      }
    }

    load();
  }, [router]);

  async function onLogout() {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
      router.replace("/login");
    } catch (err: any) {
      setError(err.message || "Logout fallito.");
    }
  }

  async function onUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file || !patient) return;

    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append("title", file.name);
      formData.append("document_type", "lab_report");
      formData.append("file", file);

      const res = await fetch(
        `${API_BASE}/api/documents/upload?patient_id=${patient.id}`,
        {
          method: "POST",
          credentials: "include",
          body: formData,
        }
      );

      const rawText = await res.text();

      let data: any = null;
      try {
        data = rawText ? JSON.parse(rawText) : null;
      } catch {
        data = null;
      }

      if (!res.ok) {
        let detail = data?.detail ?? rawText ?? `Errore ${res.status}`;

        if (Array.isArray(detail)) {
          detail = detail
            .map((d: any) => `${(d.loc || []).join(".")}: ${d.msg}`)
            .join(" | ");
        }

        console.error("Errore upload:", res.status, data);
        throw new Error(String(detail));
      }

      setMessage(`Documento caricato: ${data.title}`);

      const docs = await apiFetch<DocumentItem[]>(
        `/api/documents?patient_id=${patient.id}`
      );

      setDocuments(docs);
      setFile(null);
    } catch (err: any) {
      setError(err.message || "Upload fallito.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">VitaSync Portal</h1>
            <p className="text-sm text-slate-600">
              Bentornato, {user?.full_name || user?.username || "utente"}.
            </p>
          </div>

          <button
            onClick={onLogout}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100"
          >
            Esci
          </button>
        </header>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Carica documento</h2>

          <form onSubmit={onUpload} className="space-y-4">
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png,.heic"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-slate-700
                file:mr-4 file:py-2 file:px-4
                file:rounded-lg file:border-0
                file:text-sm file:font-medium
                file:bg-slate-900 file:text-white
                hover:file:bg-slate-800"
            />

            <button
              type="submit"
              disabled={!file || loading}
              className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-800 disabled:opacity-60"
            >
              {loading ? "Caricamento..." : "Carica referto"}
            </button>
          </form>

          {message && (
            <div className="mt-4 text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg p-3">
              {message}
            </div>
          )}

          {error && (
            <div className="mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              {error}
            </div>
          )}
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Documenti recenti</h2>

          {!patient ? (
            <p className="text-sm text-slate-600">Caricamento paziente...</p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-slate-600">
              Nessun documento caricato.
            </p>
          ) : (
            <ul className="divide-y divide-slate-200">
              {documents.map((doc) => (
                <li key={doc.id} className="py-3 flex items-center justify-between">
                  <div>
                    <p className="font-medium">{doc.title}</p>
                    <p className="text-xs text-slate-500">
                      {doc.document_type} - {doc.processing_status}
                    </p>
                  </div>

                  <span className="text-xs uppercase tracking-wide text-slate-500">
                    bozza
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-2">Prossimi step</h2>
          <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
            <li>Estrazione OCR/parsing referti.</li>
            <li>Review valori estratti e conferma utente.</li>
            <li>Trend storici esami.</li>
            <li>Caricamento ricette e collegamento terapia.</li>
            <li>Reminder farmaci, ritiri e controlli.</li>
            <li>Report PDF per il consulto medico.</li>
          </ul>
        </section>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione personale/familiare.
          Non formula diagnosi, non prescrive terapie e non sostituisce il parere
          medico.
        </footer>
      </div>
    </main>
  );
}
