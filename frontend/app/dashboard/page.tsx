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
    <main className="min-h-screen p-6 bg-slate-50">
      <div className="max-w-6xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
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
                      <Link href="/reminders">
                        <Button>Vai ai promemoria</Button>
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
                          <h3 className="font-medium text-slate-900">{r.title}</h3>
                          <p className="text-xs text-slate-600 mt-1">
                            {new Date(r.scheduled_at).toLocaleString("it-IT")}
                          </p>
                        </div>
                        <span className="text-xs text-slate-500">Pendente</span>
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
                <Link href="/reminders">
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <h3 className="font-semibold text-slate-900 mb-2">
                      ⏰ Promemoria
                    </h3>
                    <p className="text-sm text-slate-600">
                      Gestisci promemoria per farmaci e visite.
                    </p>
                  </Card>
                </Link>

                <Link href="/trend">
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <h3 className="font-semibold text-slate-900 mb-2">
                      📊 Trend esami
                    </h3>
                    <p className="text-sm text-slate-600">
                      Visualizza l'andamento dei tuoi esami nel tempo.
                    </p>
                  </Card>
                </Link>

                <Link href="/notifications">
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <h3 className="font-semibold text-slate-900 mb-2">
                      🔔 Notifiche
                    </h3>
                    <p className="text-sm text-slate-600">
                      Storico delle notifiche inviate.
                    </p>
                  </Card>
                </Link>

                <Link href="/report">
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <h3 className="font-semibold text-slate-900 mb-2">
                      📋 Report PDF
                    </h3>
                    <p className="text-sm text-slate-600">
                      Genera un riepilogo per il medico.
                    </p>
                  </Card>
                </Link>

                <Link href="/settings">
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <h3 className="font-semibold text-slate-900 mb-2">
                      ⚙️ Impostazioni
                    </h3>
                    <p className="text-sm text-slate-600">
                      Configura notifiche e preferenze.
                    </p>
                  </Card>
                </Link>
              </div>
            </section>
          </>
        )}

        <footer className="text-xs text-slate-500 text-center pt-8">
          VitaSync Portal è uno strumento di organizzazione personale. Non
          sostituisce il parere medico.
        </footer>
      </div>
    </main>
  );
}