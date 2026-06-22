import type { Metadata, Viewport } from "next";
import { Source_Sans_3 } from "next/font/google";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Toaster } from "@/components/ui/sonner";

// Fonte oficial do site da FAI-UFSCar (Source Sans Pro). next/font auto-hospeda.
const sourceSans = Source_Sans_3({
  subsets: ["latin"],
  weight: ["300", "400", "600", "700"],
  variable: "--font-source-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Lina — Assistente Virtual da FAI-UFSCar",
    template: "%s · Lina | FAI-UFSCar",
  },
  description:
    "Lina é a assistente virtual da FAI-UFSCar (Fundação de Apoio Institucional ao Desenvolvimento Científico e Tecnológico). Tire dúvidas sobre o Manual do Coordenador e os processos da Fundação, com respostas fundamentadas e fontes citadas.",
  applicationName: "Lina · FAI-UFSCar",
  authors: [{ name: "FAI-UFSCar", url: "https://www.fai.ufscar.br" }],
  keywords: [
    "FAI", "UFSCar", "FAI-UFSCar", "Manual do Coordenador", "assistente virtual",
    "chatbot", "Fundação de Apoio", "coordenador de projetos",
  ],
  icons: {
    icon: "/fai-icone.png",
    shortcut: "/fai-icone.png",
    apple: "/fai-icone.png",
  },
  openGraph: {
    title: "Lina — Assistente Virtual da FAI-UFSCar",
    description:
      "Assistente virtual da FAI-UFSCar para o Manual do Coordenador, com respostas fundamentadas e fontes citadas.",
    type: "website",
    locale: "pt_BR",
    siteName: "Lina · FAI-UFSCar",
  },
};

export const viewport: Viewport = {
  themeColor: "#3c8dbc",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className={sourceSans.variable}>
      <body className="antialiased flex flex-col h-screen overflow-hidden bg-background text-foreground">
        <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        <Toaster richColors position="top-center" />
      </body>
    </html>
  );
}
