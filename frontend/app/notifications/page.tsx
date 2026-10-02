"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { Alert, Badge, Card, EmptyState } from "@/components/ui";

type NotificationItem = {
  id: string;
  reminder_id: string | null;
  patient_id: string | null;
  user_id: string | null;
  channel: string;
  event: string;
  status: string;
  recipient: string | null;
  subject: string | null;
  error: string | null;
  scheduled_for: string | null;
  sent_at: string | null;
  created_at: string;
  metadata_json: Record<string, unknown>;
};

function statusVariant(status: string): "success" | "danger" | "default" {
  if (status === "sent") {
    return "success";
  }

  if (status === "failed") {
    return "danger";
  }

  return "default";
}

function channelLabel(channel: string) {
  if (channel === "console") return "console";
  if (channel === "smtp") return "email";
  return channel;
}

export default function NotificationsPage() {
  const router = useRouter();

  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<NotificationItem[]>(
          "/api/notifications?limit=100"
        );
        setNotifications(data);
        setError(null);
      } catch (err: any) {
        const message = err?.message || "Impossibile caricare le notifiche.";
        setError(message);

        if (/non autenticato|401|unauthorized/i.test(message)) {
          router.replace("/login");
        }
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router]);

  return (
    <main className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Notifiche</h1>
            <p className="text-sm text-slate-600">
              Storico delle notifiche promemoria registrate dal sistema.
            </p>
          </div>

          <Link
            href="/dashboard"
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-100"
          >
            Torna alla dashboard
          </Link>
        </header>

        {error && <Alert variant="error">{error}</Alert>}

        {loading ? (
          <Card>
            <p className="text-sm text-slate-600">Caricamento notifiche...</p>
          </Card>
        ) : notifications.length === 0 ? (
          <Card>
            <EmptyState
              title="Nessuna notifica"
              description="Non ci sono ancora notifiche registrate per questo account. Le notifiche compaiono quando il sistema elabora promemoria scaduti tramite lo script manuale o il wrapper schedulabile."
            />
          </Card>
        ) : (
          <Card>
            <div className="flex items-center justify-between gap-3 mb-4">
              <h2 className="text-lg font-semibold">Notifiche recenti</h2>
              <span className="text-sm text-slate-600">
                {notifications.length} notifiche
              </span>
            </div>

            <ul className="divide-y divide-slate-200">
              {notifications.map((n) => (
                <li key={n.id} className="py-4 space-y-2">
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                    <div>
                      <p className="font-medium">
                        {n.subject || "Notifica senza oggetto"}
                      </p>
                      <p className="text-xs text-slate-500">
                        {channelLabel(n.channel)} - {n.event}
                      </p>
                    </div>

                    <Badge variant={statusVariant(n.status)} className="shrink-0">
                      {n.status}
                    </Badge>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-slate-600">
                    <p>
                      <span className="font-medium">Creata:</span>{" "}
                      {formatDateTime(n.created_at)}
                    </p>

                    {n.sent_at && (
                      <p>
                        <span className="font-medium">Inviata:</span>{" "}
                        {formatDateTime(n.sent_at)}
                      </p>
                    )}

                    {n.scheduled_for && (
                      <p>
                        <span className="font-medium">Scheduled:</span>{" "}
                        {formatDateTime(n.scheduled_for)}
                      </p>
                    )}

                    {n.recipient && (
                      <p>
                        <span className="font-medium">Destinatario:</span>{" "}
                        {n.recipient}
                      </p>
                    )}

                    {n.reminder_id && (
                      <p className="break-all">
                        <span className="font-medium">Reminder:</span>{" "}
                        {n.reminder_id}
                      </p>
                    )}

                    {n.error && (
                      <p className="text-red-700">
                        <span className="font-medium">Errore:</span> {n.error}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card>
          <h2 className="text-lg font-semibold mb-2">Nota operativa</h2>
          <p className="text-sm text-slate-700">
            Questa pagina e' sola lettura. Non invia email, non abilita push,
            non elimina dati e non modifica la retention dei documenti.
          </p>
        </Card>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e' uno strumento di organizzazione
          personale/familiare. Non formula diagnosi, non prescrive terapie e non
          sostituisce il parere medico.
        </footer>
      </div>
    </main>
  );
}