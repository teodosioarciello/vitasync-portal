"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ identifier, password }),
      });

      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Login fallito.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-md bg-white rounded-2xl shadow p-8">
        <h1 className="text-2xl font-bold mb-2">VitaSync Portal</h1>
        <p className="text-sm text-slate-600 mb-6">
          Accedi per gestire referti, ricette, terapia e promemoria.
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-identifier" className="block text-sm font-medium mb-1">
              Username o email
            </label>
            <input id="login-identifier"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              required
            />
          </div>

          <div>
            <label htmlFor="login-password" className="block text-sm font-medium mb-1">Password</label>
            <input id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              required
            />
          </div>

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 text-white py-2 font-medium hover:bg-slate-800 disabled:opacity-60"
          >
            {loading ? "Accesso..." : "Accedi"}
          </button>
        </form>

        <div className="mt-6 text-sm">
          Non hai un account?{" "}
          <Link href="/register" className="text-blue-700 hover:underline">
            Registrati
          </Link>
        </div>

        <div className="mt-6 text-xs text-slate-500 border-t pt-4">
          VitaSync Portal e&apos; uno strumento di organizzazione personale/familiare.
          Non formula diagnosi e non sostituisce il parere medico.
        </div>
      </div>
    </main>
  );
}
