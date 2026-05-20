import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/layout/Header";

export const metadata: Metadata = {
  title: "FAI-Ufscar Chatbot",
  description: "Chatbot inteligente para busca de documentos da FAI-Ufscar",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="antialiased flex flex-col h-screen overflow-hidden">
        {children}
      </body>
    </html>
  );
}
