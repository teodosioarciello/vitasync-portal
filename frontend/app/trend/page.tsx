"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Alert, Badge, Button, Card, EmptyState } from "@/components/ui";

type Patient = {
  id: string;
  family_id: string;
  display_name: string;
  relationship_to_owner: string;
};

type CodeSummary = {
  test_code: string;
  test_name_normalized: string;
  last_value_numeric: number | null;
  last_value_text: string | null;
  last_unit: string | null;
  last_flag: string | null;
  last_date: string | null;
  points_count: number;
};

type TrendPoint = {
  date: string | null;
  value_numeric: number | null;
  value_text: string | null;
  unit: string | null;
  reference_min: number | null;
  reference_max: number | null;
  reference_text: string | null;
  flag: string | null;
  document_id: string;
  document_title: string;
  test_name_normalized: string;
  confirmed_by_user: boolean;
  user_corrected: boolean;
  created_at: string;
};

type TrendResponse = {
  patient_id: string;
  test_code: string;
  test_name_normalized: string | null;
  unit: string | null;
  points: TrendPoint[];
};

function formatDate(value: string | null): string {
  if (!value) return "-";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleDateString("it-IT");
}

function formatNumber(value: number | null | undefined): string {
  if (value == null) return "-";
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "");
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

function flagBadgeVariant(
  flag: string | null
): "default" | "success" | "warning" | "danger" | "info" {
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

function pointColor(flag: string | null): string {
  switch (flag) {
    case "normal":
      return "#16a34a";
    case "above_range":
      return "#d97706";
    case "below_range":
      return "#0284c7";
    case "critical":
      return "#dc2626";
    default:
      return "#64748b";
  }
}

function TrendChart({ points }: { points: TrendPoint[] }) {
  const values = points
    .map((p) => p.value_numeric)
    .filter((v): v is number => typeof v === "number");

  if (values.length === 0) {
    return (
      <div className="text-sm text-slate-600">
        Nessun valore numerico confermato da mostrare.
      </div>
    );
  }

  let min = Math.min(...values);
  let max = Math.max(...values);

  if (min === max) {
    min -= 1;
    max += 1;
  }

  const width = 900;
  const height = 280;
  const pad = 56;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  const coords = points.map((p, i) => {
    const v = p.value_numeric ?? min;
    const x =
      points.length === 1
        ? width / 2
        : pad + (i * innerW) / (points.length - 1);
    const y = pad + innerH - ((v - min) / (max - min)) * innerH;
    return { x, y, p };
  });

  const polyline = coords.map((c) => `${c.x},${c.y}`).join(" ");

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full min-w-[700px] h-[280px]"
        role="img"
        aria-label="Grafico trend esami"
      >
        <rect x="0" y="0" width={width} height={height} fill="white" />

        <line
          x1={pad}
          y1={pad}
          x2={width - pad}
          y2={pad}
          stroke="#e2e8f0"
        />
        <line
          x1={pad}
          y1={height - pad}
          x2={width - pad}
          y2={height - pad}
          stroke="#cbd5e1"
        />

        <text x={12} y={pad + 4} fontSize="12" fill="#64748b">
          {formatNumber(max)}
        </text>
        <text x={12} y={height - pad + 4} fontSize="12" fill="#64748b">
          {formatNumber(min)}
        </text>

        <polyline
          points={polyline}
          fill="none"
          stroke="#334155"
          strokeWidth="2"
        />

        {coords.map((c) => (
          <circle
            key={`${c.p.document_id}-${c.p.created_at}`}
            cx={c.x}
            cy={c.y}
            r="5"
            fill={pointColor(c.p.flag)}
            stroke="white"
            strokeWidth="1.5"
          >
            <title>
              {formatDate(c.p.date)} - {formatNumber(c.p.value_numeric)}{" "}
              {c.p.unit ?? ""}
            </title>
          </circle>
        ))}

        {coords.length > 0 && (
          <text
            x={pad}
            y={height - 18}
            fontSize="12"
            fill="#64748b"
          >
            {formatDate(coords[0].p.date)}
          </text>
        )}

        {coords.length > 1 && (
          <text
            x={width - pad}
            y={height - 18}
            fontSize="12"
            fill="#64748b"
            textAnchor="end"
          >
            {formatDate(coords[coords.length - 1].p.date)}
          </text>
        )}
      </svg>
    </div>
  );
}

export default function TrendPage() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [codes, setCodes] = useState<CodeSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [trend, setTrend] = useState<TrendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [trendLoading, setTrendLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const loadInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const myPatient = await apiFetch<Patient>("/api/patients/me");
      setPatient(myPatient);

      const list = await apiFetch<CodeSummary[]>(
        `/api/lab-tests/codes?patient_id=${myPatient.id}`
      );

      setCodes(list);

      if (list.length > 0) {
        setSelected((prev) => prev ?? list[0].test_code);
        setMessage(`${list.length} esami confermati disponibili per il trend.`);
      } else {
        setSelected(null);
        setTrend(null);
        setMessage(
          "Nessun valore confermato trovato. Carica un referto, estrai i valori e confermali dalla review."
        );
      }
    } catch (err: any) {
      setError(err.message || "Impossibile caricare i dati trend.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitial();
  }, [loadInitial]);

  useEffect(() => {
    let cancelled = false;

    async function loadTrend() {
      if (!patient || !selected) {
        setTrend(null);
        return;
      }

      setTrendLoading(true);
      setError(null);

      try {
        const res = await apiFetch<TrendResponse>(
          `/api/lab-tests/trend?test_code=${encodeURIComponent(
            selected
          )}&patient_id=${patient.id}`
        );

        if (!cancelled) {
          setTrend(res);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || "Impossibile caricare il trend.");
        }
      } finally {
        if (!cancelled) {
          setTrendLoading(false);
        }
      }
    }

    loadTrend();

    return () => {
      cancelled = true;
    };
  }, [patient, selected]);

  const points = trend?.points ?? [];

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
              Trend esami
            </h1>
            <p className="text-sm text-slate-600">
              Vengono mostrati solo i valori confermati dall&apos;utente.
            </p>
          </div>

          <Button
            variant="secondary"
            onClick={() => void loadInitial()}
            disabled={loading}
            loading={loading}
          >
            {loading ? "Caricamento..." : "Ricarica"}
          </Button>
        </header>

        {error && <Alert variant="error">{error}</Alert>}

        {message && <Alert variant="success">{message}</Alert>}

        <Card className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-end gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium mb-1">Esame</label>
              <select
                value={selected ?? ""}
                onChange={(e) => setSelected(e.target.value)}
                disabled={loading || codes.length === 0}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 bg-white disabled:opacity-60"
              >
                {codes.length === 0 && (
                  <option value="">Nessun esame confermato</option>
                )}
                {codes.map((c) => (
                  <option key={c.test_code} value={c.test_code}>
                    {c.test_name_normalized} ({c.points_count} punti)
                  </option>
                ))}
              </select>
            </div>

            <div className="text-sm text-slate-600">
              {trend?.test_name_normalized ?? "-"}
              {trend?.unit ? ` - ${trend.unit}` : ""}
            </div>
          </div>

          {codes.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              {codes.slice(0, 3).map((c) => (
                <button
                  key={c.test_code}
                  onClick={() => setSelected(c.test_code)}
                  className={`rounded-xl border p-3 text-left hover:bg-slate-50 ${
                    selected === c.test_code
                      ? "border-slate-900 bg-slate-50"
                      : "border-slate-200"
                  }`}
                >
                  <div className="font-medium">{c.test_name_normalized}</div>
                  <div className="text-xs text-slate-500 mt-1">
                    ultimo: {formatNumber(c.last_value_numeric)}{" "}
                    {c.last_unit ?? ""} - {formatDate(c.last_date)}
                  </div>
                  <div className="mt-2">
                    <Badge variant={flagBadgeVariant(c.last_flag)}>
                      {flagLabel(c.last_flag)}
                    </Badge>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Card>

        {trendLoading ? (
          <Card>
            <p className="text-sm text-slate-600">Caricamento trend...</p>
          </Card>
        ) : points.length === 0 ? (
          <Card>
            <EmptyState
              title="Nessun punto storico"
              description="Nessun punto storico confermato per questo esame."
            />
          </Card>
        ) : (
          <>
            <Card>
              <h2 className="text-lg font-semibold mb-4">
                Grafico {trend?.test_name_normalized ?? ""}
              </h2>
              <TrendChart points={points} />
            </Card>

            <Card className="overflow-hidden">
              <h2 className="text-lg font-semibold">Storico confermati</h2>
              <p className="text-xs text-slate-500 mt-1 mb-4">
                Il delta e&apos; calcolato rispetto al punto precedente nello storico.
              </p>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Data</th>
                      <th className="px-4 py-3">Valore</th>
                      <th className="px-4 py-3">Delta</th>
                      <th className="px-4 py-3">Unita</th>
                      <th className="px-4 py-3">Riferimento</th>
                      <th className="px-4 py-3">Flag</th>
                      <th className="px-4 py-3">Documento</th>
                      <th className="px-4 py-3">Stato</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {points.map((p, idx) => {
                      const prev = idx > 0 ? points[idx - 1] : null;
                      const delta =
                        p.value_numeric != null && prev?.value_numeric != null
                          ? p.value_numeric - prev.value_numeric
                          : null;

                      return (
                        <tr key={`${p.document_id}-${p.created_at}`}>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {formatDate(p.date)}
                          </td>
                          <td className="px-4 py-3 font-medium">
                            {formatNumber(p.value_numeric)}
                            {p.value_numeric == null && p.value_text
                              ? ` (${p.value_text})`
                              : ""}
                          </td>
                          <td className="px-4 py-3">
                            {delta == null ? (
                              "-"
                            ) : (
                              <span
                                className={
                                  delta > 0
                                    ? "text-amber-700"
                                    : delta < 0
                                    ? "text-sky-700"
                                    : "text-slate-500"
                                }
                              >
                                {delta > 0 ? "+" : ""}
                                {formatNumber(delta)}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3">{p.unit ?? "-"}</td>
                          <td className="px-4 py-3 text-slate-600 whitespace-nowrap">
                            {p.reference_text ??
                              (p.reference_min != null && p.reference_max != null
                                ? `${formatNumber(p.reference_min)} - ${formatNumber(
                                    p.reference_max
                                  )}`
                                : p.reference_max != null
                                ? `< ${formatNumber(p.reference_max)}`
                                : p.reference_min != null
                                ? `> ${formatNumber(p.reference_min)}`
                                : "-")}
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant={flagBadgeVariant(p.flag)}>
                              {flagLabel(p.flag)}
                            </Badge>
                          </td>
                          <td className="px-4 py-3">
                            <Link
                              href={`/documents/${p.document_id}/review`}
                              className="text-blue-700 hover:underline"
                            >
                              {p.document_title}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-500">
                            {p.confirmed_by_user ? "confermato" : "bozza"}
                            {p.user_corrected ? " - corretto" : ""}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </>
        )}

        <footer className="text-xs text-slate-500">
          VitaSync Portal e&apos; uno strumento di organizzazione
          personale/familiare. Il trend non formula diagnosi e non sostituisce
          il parere medico.
        </footer>
      </div>
    </main>
  );
}