"use client";

import Link from "next/link";
import { useState } from "react";
import { apiFetch } from "@/lib/api";

export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [verificationUrl, setVerificationUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setVerificationUrl(null);
    setLoading(true);

    try {
      const data = await apiFetch<any>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          username,
          email,
          password,
          full_name: fullName || null,
          accept_privacy: acceptPrivacy,
          accept_terms: acceptTerms,
          invite_code: inviteCode || null,
        }),
      });

      if (data.verification_url) {
        setVerificationUrl(data.verification_url);
      }

      if (data.user.email_verified) {
        setSuccess("Account creato. Ora puoi effettuare il login.");
      } else {
        setSuccess(
          "Account creato. Verifica la email per completare la registrazione."
        );
      }
    } catch (err: any) {
      setError(err.message || "Registrazione fallita.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main id="main-content" className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow p-8">
        <h1 className="text-2xl font-bold mb-2">Creazione account</h1>
        <p className="text-sm text-slate-600 mb-6">
          Registrati a VitaSync Portal per organizzare documenti sanitari,
          terapie e promemoria.
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="register-username" className="block text-sm font-medium mb-1">Username</label>
            <input id="register-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              required
              minLength={3}
            />
          </div>

          <div>
            <label htmlFor="register-email" className="block text-sm font-medium mb-1">Email</label>
            <input id="register-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              required
            />
          </div>

          <div>
            <label htmlFor="register-full-name" className="block text-sm font-medium mb-1">
              Nome completo
            </label>
            <input id="register-full-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
            />
          </div>

          <div>
            <label htmlFor="register-password" className="block text-sm font-medium mb-1">Password</label>
            <input id="register-password" aria-describedby="register-password-hint"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              required
              minLength={12}
            />
            <p id="register-password-hint" className="text-xs text-slate-500 mt-1">
              Minimo 12 caratteri.
            </p>
          </div>

          <div>
            <label htmlFor="register-invite-code" className="block text-sm font-medium mb-1">
              Codice invito opzionale
            </label>
            <input id="register-invite-code"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2"
              placeholder="Lascia vuoto se non richiesto"
            />
          </div>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={acceptPrivacy}
              onChange={(e) => setAcceptPrivacy(e.target.checked)}
              className="mt-1"
              required
            />
            <span>
              Ho letto e accetto l&apos;informativa privacy e acconsento al
              trattamento dei dati sanitari per le finalita del servizio.
            </span>
          </label>

          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={acceptTerms}
              onChange={(e) => setAcceptTerms(e.target.checked)}
              className="mt-1"
              required
            />
            <span>Accetto i termini di utilizzo.</span>
          </label>

          {error && (
            <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg p-3">
              {error}
            </div>
          )}

          {success && (
            <div className="text-sm text-green-800 bg-green-50 border border-green-200 rounded-lg p-3">
              {success}
            </div>
          )}

          {verificationUrl && (
            <div className="text-sm bg-blue-50 border border-blue-200 rounded-lg p-3">
              <p className="mb-2">
                Link di verifica disponibile in ambiente di sviluppo:
              </p>
              <a
                href={verificationUrl}
                target="_blank"
                rel="noreferrer"
                className="text-blue-700 underline break-all"
              >
                {verificationUrl}
              </a>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 text-white py-2 font-medium hover:bg-slate-800 disabled:opacity-60"
          >
            {loading ? "Creazione..." : "Registrati"}
          </button>
        </form>

        <div className="mt-6 text-sm">
          Hai gia un account?{" "}
          <Link href="/login" className="text-blue-700 hover:underline">
            Accedi
          </Link>
        </div>
      </div>
    </main>
  );
}
