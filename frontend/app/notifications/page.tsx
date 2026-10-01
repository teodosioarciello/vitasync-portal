"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

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

function statusClasses(status: string) {
  if (status === "sent") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (status === "failed") {
    return "border-red-200 bg-red-50 text-red-700";
  }

  return "border-slate-200 bg-slate-50 text-slate-700";
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
    <main className="min-h-screen p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Notifiche</h1>
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

        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
            {error}
          </div>
        )}

        {loading ? (
          <div className="bg-white rounded-2xl shadow p-6 text-sm text-slate-600">
            Caricamento notifiche...
          </div>
        ) : notifications.length === 0 ? (
          <div className="bg-white rounded-2xl shadow p-6 space-y-3">
            <h2 className="text-lg font-semibold">Nessuna notifica</h2>
            <p className="text-sm text-slate-600">
              Non ci sono ancora notifiche registrate per questo account.
            </p>
            <p className="text-xs text-slate-500">
              Le notifiche compaiono quando il sistema elabora promemoria scaduti
              tramite lo script manuale o il wrapper schedulabile.
            </p>
          </div>
        ) : (
          <section className="bg-white rounded-2xl shadow p-6">
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

                    <span
                      className={`shrink-0 rounded-full border px-2 py-1 text-xs font-medium ${statusClasses(
                        n.status
                      )}`}
                    >
                      {n.status}
                    </span>
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
          </section>
        )}

        <section className="bg-white rounded-2xl shadow p-6">
          <h2 className="text-lg font-semibold mb-2">Nota operativa</h2>
          <p className="text-sm text-slate-700">
            Questa pagina e' sola lettura. Non invia email, non abilita push,
            non elimina dati e non modifica la retention dei documenti.
          </p>
        </section>

        <footer className="text-xs text-slate-500">
          VitaSync Portal e' uno strumento di organizzazione
          personale/familiare. Non formula diagnosi, non prescrive terapie e non
          sostituisce il parere medico.
        </footer>
      </div>
    </main>
  );
}