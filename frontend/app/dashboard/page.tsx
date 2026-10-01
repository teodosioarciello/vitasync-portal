"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { API_BASE, apiFetch } from "@/lib/api";
import { formatDateTime, humanReminderType } from "@/lib/format";

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
  deleted_at?: string | null;
};

type Reminder = {
  id: string;
  patient_id: string;
  therapy_id: string | null;
  title: string;
  reminder_type: string;
  scheduled_at: string;
  status: string;
};

export default function DashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [trashDocuments, setTrashDocuments] = useState<DocumentItem[]>([]);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reminderError, setReminderError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [permanentDeletingId, setPermanentDeletingId] = useState<string | null>(null);

  async function loadActiveAndTrash(p: Patient) {
    const docs = await apiFetch<DocumentItem[]>(
      `/api/documents?patient_id=${p.id}`
    );
    setDocuments(docs);

    try {
      const trash = await apiFetch<DocumentItem[]>(
        `/api/documents/trash?patient_id=${p.id}`
      );
      setTrashDocuments(trash);
    } catch {
      setTrashDocuments([]);
    }
  }

  useEffect(() => {
    async function load() {
      try {
        const me = await apiFetch<User>("/api/auth/me");
        setUser(me);

        const myPatient = await apiFetch<Patient>("/api/patients/me");
        setPatient(myPatient);

        await loadActiveAndTrash(myPatient);

        try {
          const rems = await apiFetch<Reminder[]>(
            `/api/reminders?patient_id=${myPatient.id}&status=pending`
          );
          setReminders(rems);
          setReminderError(null);
        } catch {
          setReminders([]);
          setReminderError("Promemoria non disponibili.");
        }
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

  async function onUpload(e: FormEvent) {
    e.preventDefault();

    const activePatient = patient;
    if (!file || !activePatient) return;

    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append("title", file.name);
      formData.append("document_type", "lab_report");
      formData.append("file", file);

      const res = await fetch(
        `${API_BASE}/api/documents/upload?patient_id=${activePatient.id}`,
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

      await loadActiveAndTrash(activePatient);
      setFile(null);
    } catch (err: any) {
      setError(err.message || "Upload fallito.");
    } finally {
      setLoading(false);
    }
  }

  async function onDeleteDocument(doc: DocumentItem) {
    const activePatient = patient;
    if (!activePatient) return;

    const ok = window.confirm(
      `Eliminare il documento "${doc.title}"? Verra' spostato nel cestino.`
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

      await loadActiveAndTrash(activePatient);
      setMessage(res.detail || "Documento spostato nel cestino.");
    } catch (err: any) {
      setError(err.message || "Spostamento nel cestino fallito.");
    } finally {
      setDeletingId(null);
    }
  }

  async function onRestoreDocument(doc: DocumentItem) {
    const activePatient = patient;
    if (!activePatient) return;

    const ok = window.confirm(
      `Ripristinare il documento "${doc.title}"?`
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

      await loadActiveAndTrash(activePatient);
      setMessage(res.detail || "Documento ripristinato dal cestino.");
    } catch (err: any) {
      setError(err.message || "Ripristino documento fallito.");
    } finally {
      setRestoringId(null);
    }
  }

  async function onPermanentDeleteDocument(doc: DocumentItem) {
    const activePatient = patient;
    if (!activePatient) return;

    const first = window.confirm(
      `Eliminare definitivamente il documento "${doc.title}"? L'operazione non e' reversibile.`
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

      await loadActiveAndTrash(activePatient);
      setMessage(res.detail || "Documento eliminato definitivamente.");
    } catch (err: any) {
      setError(err.message || "Eliminazione definitiva fallita.");
    } finally {
      setPermanentDeletingId(null);
    }
  }

  const now = new Date();
  const endToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() + 1
  );
  const endSoon = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

  const pending = [...reminders]
    .filter((r) => r.status === "pending")
    .sort(
      (a, b) =>
        new Date(a.scheduled_at).getTime() -
        new Date(b.scheduled_at).getTime()
    );

  const overdue = pending.filter(
    (r) => new Date(r.scheduled_at).getTime() < now.getTime()
  );

  const today = pending.filter((r) => {
    const t = new Date(r.scheduled_at).getTime();
    return t >= now.getTime() && t < endToday.getTime();
  });

  const upcoming = pending.filter((r) => {
    const t = new Date(r.scheduled_at).getTime();
    return t >= endToday.getTime() && t <= endSoon.getTime();
  });

  const urgentCount = overdue.length + today.length;

  return (
    <main className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">VitaSync Portal</h1>
            <p className="text-sm text-slate-600">
              Bentornato, {user?.full_name || user?.username || "utente"}.
            </p>
          </div>

          <nav className="flex flex-wrap items-center gap-2">
            <Link
              href="/medicines"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Medicinali
            </Link>

            <Link
              href="/therapies"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Terapie
            </Link>

            <Link
              href="/reminders"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Promemoria
            </Link>

            <Link
              href="/trend"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Trend esami
            </Link>

            <Link
              href="/notifications"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Notifiche
            </Link>

            <Link
              href="/report"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Report PDF
            </Link>

            <button
              onClick={onLogout}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
            >
              Esci
            </button>
          </nav>
        </header>

        {message && (
          <div className="text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg p-3">
            {message}
          </div>
        )}

        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {error}
          </div>
        )}

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            href="/medicines"
            className="bg-white rounded-2xl shadow p-5 hover:bg-slate-50"
          >
            <h2 className="font-semibold">Medicinali</h2>
            <p className="text-sm text-slate-600 mt-1">
              Gestisci l&apos;elenco dei farmaci conosciuti.
            </p>
          </Link>

          <Link
            href="/therapies"
            className="bg-white rounded-2xl shadow p-5 hover:bg-slate-50"
          >
            <h2 className="font-semibold">Terapie</h2>
            <p className="text-sm text-slate-600 mt-1">
              Associa farmaci, dose, frequenza e stato.
            </p>
          </Link>

          <Link
            href="/reminders"
            className="bg-white rounded-2xl shadow p-5 hover:bg-slate-50"
          >
            <h2 className="font-semibold">Promemoria</h2>
            <p className="text-sm text-slate-600 mt-1">
              Segna assunzioni, controlli e rinnovi.
            </p>
          </Link>
        </section>

        <section className="bg-white rounded-2xl shadow p-6 space-y-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Promemoria in evidenza</h2>
              <p className="text-sm text-slate-600">
                {urgentCount > 0
                  ? `${urgentCount} promemoria tra scaduti e oggi.`
                  : "Nessun promemoria urgente."}
              </p>
            </div>

            <Link
              href="/reminders"
              className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100"
            >
              Apri promemoria
            </Link>
          </div>

          {reminderError && (
            <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-3">
              {reminderError}
            </div>
          )}

          {pending.length === 0 ? (
            <div className="text-sm text-slate-600">
              Nessun promemoria da fare.
            </div>
          ) : (
            <div className="space-y-4">
              {overdue.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-red-700 mb-2">
                    Scaduti ({overdue.length})
                  </h3>
                  <ul className="divide-y divide-slate-200">
                    {overdue.slice(0, 5).map((r) => (
                      <li
                        key={r.id}
                        className="py-2 flex items-start justify-between gap-3"
                      >
                        <div>
                          <p className="font-medium">{r.title}</p>
                          <p className="text-xs text-slate-500">
                            {humanReminderType(r.reminder_type)} -{" "}
                            {formatDateTime(r.scheduled_at)}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                          scaduto
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {today.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-amber-700 mb-2">
                    Oggi ({today.length})
                  </h3>
                  <ul className="divide-y divide-slate-200">
                    {today.slice(0, 5).map((r) => (
                      <li
                        key={r.id}
                        className="py-2 flex items-start justify-between gap-3"
                      >
                        <div>
                          <p className="font-medium">{r.title}</p>
                          <p className="text-xs text-slate-500">
                            {humanReminderType(r.reminder_type)} -{" "}
                            {formatDateTime(r.scheduled_at)}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-700">
                          oggi
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {upcoming.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-slate-700 mb-2">
                    Prossimi 7 giorni ({upcoming.length})
                  </h3>
                  <ul className="divide-y divide-slate-200">
                    {upcoming.slice(0, 5).map((r) => (
                      <li
                        key={r.id}
                        className="py-2 flex items-start justify-between gap-3"
                      >
                        <div>
                          <p className="font-medium">{r.title}</p>
                          <p className="text-xs text-slate-500">
                            {humanReminderType(r.reminder_type)} -{" "}
                            {formatDateTime(r.scheduled_at)}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-600">
                          in programma
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-4">Carica documento</h2>

          <form onSubmit={onUpload} className="space-y-4">
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
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
                <li
                  key={doc.id}
                  className="py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
                >
                  <div>
                    <p className="font-medium">{doc.title}</p>
                    <p className="text-xs text-slate-500">
                      {doc.document_type} - {doc.processing_status}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Link
                      href={`/documents/${doc.id}/review`}
                      className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium hover:bg-slate-100"
                    >
                      Review
                    </Link>

                    <button
                      onClick={() => void onDeleteDocument(doc)}
                      disabled={deletingId === doc.id}
                      className="rounded-lg border border-red-200 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      {deletingId === doc.id ? "Elimino..." : "Elimina"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
            <h2 className="text-lg font-semibold">Cestino documenti</h2>
            <p className="text-sm text-slate-600">
              {trashDocuments.length === 0
                ? "Nessun documento nel cestino."
                : `${trashDocuments.length} documenti nel cestino.`}
            </p>
          </div>

          {!patient ? (
            <p className="text-sm text-slate-600">Caricamento paziente...</p>
          ) : trashDocuments.length === 0 ? (
            <p className="text-sm text-slate-600">
              I documenti eliminati compariranno qui e potranno essere
              ripristinati o eliminati definitivamente.
            </p>
          ) : (
            <ul className="divide-y divide-slate-200">
              {trashDocuments.map((doc) => (
                <li
                  key={doc.id}
                  className="py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3"
                >
                  <div>
                    <p className="font-medium">{doc.title}</p>
                    <p className="text-xs text-slate-500">
                      {doc.document_type} - {doc.processing_status}
                    </p>
                    <p className="text-xs text-slate-500">
                      Eliminato il{" "}
                      {doc.deleted_at ? formatDateTime(doc.deleted_at) : "—"}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => void onRestoreDocument(doc)}
                      disabled={
                        restoringId === doc.id ||
                        permanentDeletingId === doc.id
                      }
                      className="rounded-lg border border-emerald-200 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                    >
                      {restoringId === doc.id ? "Ripristino..." : "Ripristina"}
                    </button>

                    <button
                      onClick={() => void onPermanentDeleteDocument(doc)}
                      disabled={
                        permanentDeletingId === doc.id ||
                        restoringId === doc.id
                      }
                      className="rounded-lg border border-red-300 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                    >
                      {permanentDeletingId === doc.id
                        ? "Elimino..."
                        : "Elimina definitivamente"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-2">Prossimi step</h2>
          <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1">
            <li>Retention automatica e purge pianificata del cestino.</li>
            <li>Email/push per promemoria.</li>
            <li>Ricorrenze avanzate.</li>
            <li>Collegamento ricetta -&gt; terapia piu' ricco.</li>
            <li>Report PDF per il consulto medico.</li>
          </ul>
        </section>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. Non formula diagnosi, non prescrive terapie e non
          sostituisce il parere medico.
        </footer>
      </div>
    </main>
  );
}