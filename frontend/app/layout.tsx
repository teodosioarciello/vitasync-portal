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
      <body>{children}</body>
    </html>
  );
}
