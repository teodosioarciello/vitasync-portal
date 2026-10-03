"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, Button, EmptyState } from "@/components/ui";
import { apiFetch } from "@/lib/api";

type Patient = {
  id: string;
  display_name: string;
};

type Reminder = {
  id: string;
  title: string;
  scheduled_at: string;
  status: string;
};

// Nav dashboard: solo pagine statiche raggiungibili direttamente.
// Le route dinamiche tipo /documents/[documentId]/review non vanno qui:
// necessitano di un ID e vengono raggiunte dalle pagine che lo conoscono.
const navItems: { href: string; title: string; description: string }[] = [
  {
    href: "/documents",
    title: "Documenti",
    description: "Carica referti, gestisci elenco e cestino.",
  },
  {
    href: "/reminders",
    title: "Promemoria",
    description: "Gestisci promemoria per farmaci e visite.",
  },
  {
    href: "/medicines",
    title: "Medicinali",
    description: "Elenco dei farmaci disponibili.",
  },
  {
    href: "/therapies",
    title: "Terapie",
    description: "Piani terapeutici collegati ai farmaci.",
  },
  {
    href: "/trend",
    title: "Trend esami",
    description: "Andamento dei tuoi esami nel tempo.",
  },
  {
    href: "/notifications",
    title: "Notifiche",
    description: "Storico delle notifiche inviate.",
  },
  {
    href: "/report",
    title: "Report PDF",
    description: "Riepilogo da portare al medico.",
  },
  {
    href: "/settings",
    title: "Impostazioni",
    description: "Preferenze di notifica e canale.",
  },
];

export default function DashboardPage() {
  const router = useRouter();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const me = await apiFetch<Patient>("/api/patients/me");
        setPatient(me);

        const allReminders = await apiFetch<Reminder[]>(
          `/api/reminders?patient_id=${me.id}&status=pending`
        );
        setReminders(allReminders.slice(0, 5));
      } catch (err: any) {
        setError(err.message || "Impossibile caricare la dashboard.");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  async function handleLogout() {
    setLoggingOut(true);

    try {
      await apiFetch("/api/auth/logout", { method: "POST" }).catch(() => {});

      if (typeof window !== "undefined") {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
      }

      router.push("/login");
    } catch (err) {
      console.error("Errore durante il logout:", err);
      router.push("/login");
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <main id="main-content" className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-slate-900">
              Ciao, {patient?.display_name || "..."}
            </h1>
            <p className="text-sm text-slate-600 mt-1">
              Benvenuto nel tuo portale sanitario personale.
            </p>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            loading={loggingOut}
          >
            {loggingOut ? "Uscita..." : "Esci"}
          </Button>
        </header>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-800">
            {error}
          </div>
        )}

        {loading ? (
          <Card>
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
            </div>
          </Card>
        ) : (
          <>
            <section>
              <h2 className="text-xl font-semibold text-slate-900 mb-4">
                Promemoria in scadenza
              </h2>

              {reminders.length === 0 ? (
                <Card>
                  <EmptyState
                    title="Nessun promemoria"
                    description="Non hai promemoria pendenti. Creane uno per iniziare."
                    action={
                      <Link
                        href="/reminders"
                        className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
                      >
                        Vai ai promemoria
                      </Link>
                    }
                  />
                </Card>
              ) : (
                <div className="grid gap-4">
                  {reminders.map((r) => (
                    <Card key={r.id} padding="sm">
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-medium text-slate-900">
                            {r.title}
                          </h3>
                          <p className="text-xs text-slate-600 mt-1">
                            {new Date(r.scheduled_at).toLocaleString("it-IT")}
                          </p>
                        </div>

                        <span className="text-xs text-slate-500">
                          Pendente
                        </span>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </section>

            <section>
              <h2 className="text-xl font-semibold text-slate-900 mb-4">
                Azioni rapide
              </h2>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {navItems.map((item) => (
                  <Link key={item.href} href={item.href}>
                    <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                      <h3 className="font-semibold text-slate-900 mb-2">
                        {item.title}
                      </h3>
                      <p className="text-sm text-slate-600">
                        {item.description}
                      </p>
                    </Card>
                  </Link>
                ))}
              </div>
            </section>
          </>
        )}

        <footer className="text-xs text-slate-500 text-center pt-8">
          VitaSync Portal e&apos; uno strumento di organizzazione personale.
          Non sostituisce il parere medico.
        </footer>
      </div>
    </main>
  );
}