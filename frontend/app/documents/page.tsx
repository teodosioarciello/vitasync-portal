"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { API_BASE, apiFetch } from "@/lib/api";
import { Alert, Button, Card, EmptyState } from "@/components/ui";

type Patient = {
  id: string;
  display_name: string;
};

type DocumentItem = {
  id: string;
  title?: string;
  source_filename?: string;
  document_type?: string;
  created_at?: string;
  updated_at?: string;
  deleted_at?: string | null;
};

function displayTitle(doc: DocumentItem): string {
  return doc.title || doc.source_filename || "Documento";
}

function displayDate(value?: string | null): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString("it-IT");
}

export default function DocumentsPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [patient, setPatient] = useState<Patient | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [trashDocuments, setTrashDocuments] = useState<DocumentItem[]>([]);
  const [file, setFile] = useState<File | null>(null);

  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [permanentDeletingId, setPermanentDeletingId] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadActiveAndTrash = useCallback(async (activePatient: Patient) => {
    const docs = await apiFetch<DocumentItem[]>(
      `/api/documents?patient_id=${activePatient.id}`
    );
    setDocuments(docs);

    try {
      const trash = await apiFetch<DocumentItem[]>(
        `/api/documents/trash?patient_id=${activePatient.id}`
      );
      setTrashDocuments(trash);
    } catch {
      setTrashDocuments([]);
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const me = await apiFetch<Patient>("/api/patients/me");
      setPatient(me);
      await loadActiveAndTrash(me);
    } catch (err: any) {
      const text = err?.message || "Impossibile caricare i documenti.";
      setError(text);

      if (/non autenticato|401|unauthorized/i.test(text)) {
        router.replace("/login");
      }
    } finally {
      setLoading(false);
    }
  }, [loadActiveAndTrash, router]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onUpload(e: FormEvent) {
    e.preventDefault();

    if (!file || !patient) return;

    setUploading(true);
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
        data = rawText;
      }

      if (!res.ok) {
        const detail =
          data?.detail ??
          rawText ??
          `Upload fallito con stato ${res.status}`;

        if (res.status === 401) {
          router.replace("/login");
        }

        throw new Error(String(detail));
      }

      setMessage(`Documento caricato: ${data?.title ?? file.name}`);
      await loadActiveAndTrash(patient);

      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err: any) {
      setError(err.message || "Upload fallito.");
    } finally {
      setUploading(false);
    }
  }

  async function onDelete(doc: DocumentItem) {
    if (!patient) return;

    const ok = window.confirm(
      `Eliminare il documento "${displayTitle(doc)}"? Verra' spostato nel cestino.`
    );

    if (!ok) return;

    setDeletingId(doc.id);
    setError(null);
    setMessage(null);

    try {
      const res = await apiFetch<{ detail: string }>(
        `/api/documents/${doc.id}`,
        {
          method: "DELETE",
        }
      );

      await loadActiveAndTrash(patient);
      setMessage(res.detail || "Documento spostato nel cestino.");
    } catch (err: any) {
      setError(err.message || "Spostamento nel cestino fallito.");
    } finally {
      setDeletingId(null);
    }
  }

  async function onRestore(doc: DocumentItem) {
    if (!patient) return;

    const ok = window.confirm(
      `Ripristinare il documento "${displayTitle(doc)}"?`
    );

    if (!ok) return;

    setRestoringId(doc.id);
    setError(null);
    setMessage(null);

    try {
      const res = await apiFetch<{ detail: string }>(
        `/api/documents/${doc.id}/restore`,
        {
          method: "POST",
        }
      );

      await loadActiveAndTrash(patient);
      setMessage(res.detail || "Documento ripristinato dal cestino.");
    } catch (err: any) {
      setError(err.message || "Ripristino documento fallito.");
    } finally {
      setRestoringId(null);
    }
  }

  async function onPermanentDelete(doc: DocumentItem) {
    if (!patient) return;

    const first = window.confirm(
      `Eliminare definitivamente il documento "${displayTitle(doc)}"? L'operazione non e' reversibile.`
    );

    if (!first) return;

    const second = window.confirm(
      "Conferma definitiva: il documento e il file verranno eliminati per sempre. Procedere?"
    );

    if (!second) return;

    setPermanentDeletingId(doc.id);
    setError(null);
    setMessage(null);

    try {
      const res = await apiFetch<{ detail: string }>(
        `/api/documents/${doc.id}/permanent`,
        {
          method: "DELETE",
        }
      );

      await loadActiveAndTrash(patient);
      setMessage(res.detail || "Documento eliminato definitivamente.");
    } catch (err: any) {
      setError(err.message || "Eliminazione definitiva fallita.");
    } finally {
      setPermanentDeletingId(null);
    }
  }

  return (
    <main className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-blue-700 hover:underline"
            >
              &larr; Torna alla dashboard
            </Link>
            <h1 className="text-2xl font-bold mt-1 text-slate-900">
              Documenti
            </h1>
            <p className="text-sm text-slate-600">
              Carica referti e gestisci documenti attivi e cestino.
            </p>
          </div>

          <Button
            type="button"
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

        <Card className="space-y-4">
          <h2 className="text-lg font-semibold">Carica documento</h2>

          <p className="text-sm text-slate-600">
            Formati accettati: PDF, JPEG, PNG. Dimensione massima tipica: 25 MB.
            Il file viene validato dal backend prima del salvataggio.
          </p>

          <form onSubmit={onUpload} className="space-y-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-slate-700 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-slate-800"
            />

            <Button
              type="submit"
              variant="primary"
              loading={uploading}
              disabled={!file || uploading || loading}
            >
              {uploading ? "Caricamento..." : "Carica referto"}
            </Button>
          </form>
        </Card>

        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Documenti attivi</h2>
            <span className="text-sm text-slate-600">
              {documents.length} documenti
            </span>
          </div>

          {loading ? (
            <p className="text-sm text-slate-600">Caricamento documenti...</p>
          ) : documents.length === 0 ? (
            <EmptyState
              title="Nessun documento attivo"
              description="Carica un referto per iniziare. I documenti caricati compaiono qui."
            />
          ) : (
            <ul className="divide-y divide-slate-200">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
                >
                  <div className="min-w-0">
                    <Link
                      href={`/documents/${doc.id}/review`}
                      className="font-medium break-words text-blue-700 hover:underline"
                    >
                      {displayTitle(doc)}
                    </Link>
                    <p className="text-xs text-slate-500 mt-1">
                      Creato: {displayDate(doc.created_at)}
                      {doc.document_type ? ` - ${doc.document_type}` : ""}
                    </p>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Link
                      href={`/documents/${doc.id}/review`}
                      className="inline-flex items-center justify-center rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                    >
                      Apri review
                    </Link>

                    <Button
                      type="button"
                      size="sm"
                      variant="dangerOutline"
                      onClick={() => void onDelete(doc)}
                      disabled={deletingId === doc.id}
                      loading={deletingId === doc.id}
                    >
                      Elimina
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold">Cestino</h2>
            <span className="text-sm text-slate-600">
              {trashDocuments.length} documenti
            </span>
          </div>

          <p className="text-xs text-slate-500">
            I documenti eliminati finiscono qui e possono essere ripristinati o
            eliminati definitivamente.
          </p>

          {loading ? (
            <p className="text-sm text-slate-600">Caricamento cestino...</p>
          ) : trashDocuments.length === 0 ? (
            <EmptyState
              title="Cestino vuoto"
              description="Nessun documento nel cestino."
            />
          ) : (
            <ul className="divide-y divide-slate-200">
              {trashDocuments.map((doc) => (
                <li
                  key={doc.id}
                  className="py-4 space-y-3"
                >
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium break-words">
                        {displayTitle(doc)}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        Eliminato: {displayDate(doc.deleted_at)}
                      </p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        size="sm"
                        variant="infoOutline"
                        onClick={() => void onRestore(doc)}
                        disabled={restoringId === doc.id}
                        loading={restoringId === doc.id}
                      >
                        Ripristina
                      </Button>

                      <Button
                        type="button"
                        size="sm"
                        variant="danger"
                        onClick={() => void onPermanentDelete(doc)}
                        disabled={permanentDeletingId === doc.id}
                        loading={permanentDeletingId === doc.id}
                      >
                        Elimina definitivamente
                      </Button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione personale.
          Tratta i documenti caricati come dati sensibili.
        </footer>
      </div>
    </main>
  );
}