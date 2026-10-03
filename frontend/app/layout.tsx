import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VitaSync Portal",
  description:
    "Organizzazione personale e familiare di documenti sanitari, referti, ricette e promemoria.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="it">
            <body>
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-slate-900 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow"
        >
          Salta al contenuto principale
        </a>
        {children}
      </body>
    </html>
  );
}
