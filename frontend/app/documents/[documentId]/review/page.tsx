"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Alert, Badge, Button, Card, EmptyState } from "@/components/ui";

type DocumentItem = {
  id: string;
  title: string;
  document_type: string;
  processing_status: string;
  document_date: string | null;
};

type LabTest = {
  id: string;
  document_id: string;
  test_code: string;
  test_name_original: string;
  test_name_normalized: string;
  value_numeric: number | null;
  value_text: string | null;
  unit: string | null;
  reference_min: number | null;
  reference_max: number | null;
  reference_text: string | null;
  flag: string | null;
  confidence: number | null;
  confirmed_by_user: boolean;
  user_corrected: boolean;
  notes: string | null;
};

type Draft = {
  value_numeric: string;
  unit: string;
  notes: string;
};

function flagBadgeVariant(flag: string | null): "default" | "success" | "warning" | "danger" | "info" {
  switch (flag) {
    case "normal":
      return "success";
    case "above_range":
      return "warning";
    case "below_range":
      return "info";
    case "critical":
      return "danger";
    default:
      return "default";
  }
}

function flagLabel(flag: string | null): string {
  switch (flag) {
    case "normal":
      return "normale";
    case "above_range":
      return "sopra range";
    case "below_range":
      return "sotto range";
    case "critical":
      return "critico";
    default:
      return "n/d";
  }
}

function rangeLabel(row: LabTest): string {
  if (row.reference_text) return row.reference_text;
  if (row.reference_min != null && row.reference_max != null)
    return `${row.reference_min} - ${row.reference_max}`;
  if (row.reference_max != null) return `< ${row.reference_max}`;
  if (row.reference_min != null) return `> ${row.reference_min}`;
  return "-";
}

export default function ReviewPage() {
  const params = useParams<{ documentId: string }>();
  const documentId = params?.documentId;

  const [doc, setDoc] = useState<DocumentItem | null>(null);
  const [rows, setRows] = useState<LabTest[]>([]);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const applyRows = useCallback((list: LabTest[]) => {
    setRows(list);
    const next: Record<string, Draft> = {};
    for (const r of list) {
      next[r.id] = {
        value_numeric:
          r.value_numeric != null ? String(r.value_numeric) : "",
        unit: r.unit ?? "",
        notes: r.notes ?? "",
      };
    }
    setDrafts(next);
  }, []);

  const load = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    try {
      const d = await apiFetch<DocumentItem>(`/api/documents/${documentId}`);
      setDoc(d);
      const list = await apiFetch<LabTest[]>(
        `/api/lab-tests?document_id=${documentId}`
      );
      applyRows(list);
    } catch (err: any) {
      setError(err.message || "Impossibile caricare la review.");
    } finally {
      setLoading(false);
    }
  }, [documentId, applyRows]);

  useEffect(() => {
    load();
  }, [load]);

  async function onExtract() {
    if (!documentId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const list = await apiFetch<LabTest[]>(
        `/api/documents/${documentId}/extract`,
        { method: "POST" }
      );
      applyRows(list);
      setMessage(`Estratti ${list.length} valori.`);
    } catch (err: any) {
      setError(err.message || "Estrazione fallita.");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmRow(row: LabTest) {
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const draft = drafts[row.id];
      const payload: Record<string, unknown> = { confirmed: true };

      const parsed =
        draft.value_numeric.trim() !== "" ? Number(draft.value_numeric) : NaN;
      if (Number.isFinite(parsed)) payload.value_numeric = parsed;
      if (draft.unit !== (row.unit ?? "")) payload.unit = draft.unit;
      if (draft.notes !== (row.notes ?? "")) payload.notes = draft.notes;

      const updated = await apiFetch<LabTest>(
        `/api/lab-tests/${row.id}`,
        { method: "PATCH", body: JSON.stringify(payload) }
      );

      setRows((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setMessage(`Confermato: ${updated.test_name_normalized}`);
    } catch (err: any) {
      setError(err.message || "Conferma riga fallita.");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmAll() {
    if (!documentId) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch<{ updated_count: number; detail: string }>(
        `/api/documents/${documentId}/lab-tests/confirm-all`,
        { method: "POST" }
      );
      setMessage(res.detail);
      const list = await apiFetch<LabTest[]>(
        `/api/lab-tests?document_id=${documentId}`
      );
      applyRows(list);
    } catch (err: any) {
      setError(err.message || "Conferma tutti fallita.");
    } finally {
      setBusy(false);
    }
  }

  function setDraft(id: string, field: keyof Draft, value: string) {
    setDrafts((prev) => ({
      ...prev,
      [id]: { ...prev[id], [field]: value },
    }));
  }

  const pendingCount = rows.filter((r) => !r.confirmed_by_user).length;

  return (
    <main id="main-content" className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <Link
              href="/dashboard"
              className="text-sm text-blue-700 hover:underline"
            >
              &larr; Torna alla dashboard
            </Link>
            <h1 className="text-2xl font-bold mt-1">
              Review estrazione valori
            </h1>
            {doc && (
              <p className="text-sm text-slate-600">
                {doc.title} &middot; {doc.document_type}
                {doc.document_date ? ` \u00b7 ${doc.document_date}` : ""}
              </p>
            )}
          </div>
          <Button
            type="button"
            variant="primary"
            onClick={onConfirmAll}
            disabled={busy || pendingCount === 0}
            loading={busy}
          >
            Conferma tutti ({pendingCount})
          </Button>
        </header>

        {error && <Alert variant="error">{error}</Alert>}
        {message && <Alert variant="success">{message}</Alert>}

        {loading ? (
          <Card>
            <p className="text-sm text-slate-600">Caricamento...</p>
          </Card>
        ) : rows.length === 0 ? (
          <Card className="space-y-4">
            <EmptyState
              title="Nessun valore estratto per questo documento."
              description={"Esegui l'estrazione per visualizzare i valori lab da confermare."}
              action={
                <Button
                  type="button"
                  variant="primary"
                  onClick={onExtract}
                  disabled={busy}
                  loading={busy}
                >
                  {busy ? "Estrazione..." : "Estrai valori"}
                </Button>
              }
            />
            <p className="text-xs text-slate-500">
              Nota: in questa versione l&apos;estrazione supporta solo PDF
              testuali. Immagini/scansioni (OCR) arrivano in uno step
              successivo.
            </p>
          </Card>
        ) : (
          <Card padding="sm" className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" aria-label="Valori estratti dal documento">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3" scope="col">Esame</th>
                    <th className="px-4 py-3" scope="col">Valore</th>
                    <th className="px-4 py-3" scope="col">Unita</th>
                    <th className="px-4 py-3" scope="col">Riferimento</th>
                    <th className="px-4 py-3" scope="col">Flag</th>
                    <th className="px-4 py-3" scope="col">Note</th>
                    <th className="px-4 py-3" scope="col"><span className="sr-only">Azioni</span></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {rows.map((row) => {
                    const draft = drafts[row.id] ?? {
                      value_numeric: "",
                      unit: "",
                      notes: "",
                    };
                    const isTextOnly =
                      row.value_numeric == null && row.value_text != null;
                    return (
                      <tr key={row.id} className="align-top">
                        <td className="px-4 py-3">
                          <div className="font-medium">{row.test_name_normalized}</div>
                          <div className="text-xs text-slate-500">
                            {row.test_name_original} &middot; {row.test_code}
                          </div>
                          {row.confidence != null && (
                            <div className="text-[10px] text-slate-400">
                              conf: {Math.round(row.confidence * 100)}%
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isTextOnly ? (
                            <Badge variant="default" className="max-w-xs truncate">
                              {row.value_text}
                            </Badge>
                          ) : (
                            <input aria-label={`Valore numerico per ${row.test_name_normalized}`}
                              type="number"
                              step="any"
                              value={draft.value_numeric}
                              onChange={(e) =>
                                setDraft(row.id, "value_numeric", e.target.value)
                              }
                              className="w-28 rounded-lg border border-slate-300 px-2 py-1"
                            />
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <input aria-label={`Unita per ${row.test_name_normalized}`}
                            type="text"
                            value={draft.unit}
                            onChange={(e) =>
                              setDraft(row.id, "unit", e.target.value)
                            }
                            className="w-24 rounded-lg border border-slate-300 px-2 py-1"
                          />
                        </td>
                        <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                          {rangeLabel(row)}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={flagBadgeVariant(row.flag)}>
                            {flagLabel(row.flag)}
                          </Badge>
                          {row.user_corrected && (
                            <div className="text-[10px] text-amber-700 mt-1">
                              corretto
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <input aria-label={`Note per ${row.test_name_normalized}`}
                            type="text"
                            value={draft.notes}
                            onChange={(e) =>
                              setDraft(row.id, "notes", e.target.value)
                            }
                            placeholder="-"
                            className="w-40 rounded-lg border border-slate-300 px-2 py-1"
                          />
                        </td>
                        <td className="px-4 py-3">
                          {row.confirmed_by_user ? (
                            <Badge variant="success">confermato</Badge>
                          ) : (
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              onClick={() => onConfirmRow(row)}
                              disabled={busy}
                            >
                              Conferma
                            </Button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. I valori estratti vanno sempre verificati
          dall&apos;utente. Non formula diagnosi e non sostituisce il parere
          medico.
        </footer>
      </div>
    </main>
  );
}