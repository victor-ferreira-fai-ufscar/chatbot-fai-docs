"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Loader2, Link2Off } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type SharedMessage = { role: string; content: string; sources?: string[] };

// Remove o prefixo "- " dos cards de fonte para exibi-los como chips estaticos.
function sourceLabel(line: string): string {
  return (line || "").replace(/^\s*-\s*/, "").trim();
}

export default function SharedConversationPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token;
  const [status, setStatus] = useState<"loading" | "ok" | "notfound" | "error">("loading");
  const [title, setTitle] = useState("");
  const [messages, setMessages] = useState<SharedMessage[]>([]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/shared/${encodeURIComponent(token)}`);
        if (cancelled) return;
        if (res.status === 404) { setStatus("notfound"); return; }
        if (!res.ok) { setStatus("error"); return; }
        const data = await res.json();
        if (cancelled) return;
        setTitle(data.title || "Conversa");
        setMessages(
          (data.messages || []).map((m: any) => ({
            role: m.role,
            content: m.content,
            sources: m.metadata?.sources,
          }))
        );
        setStatus("ok");
      } catch {
        if (!cancelled) setStatus("error");
      }
    })();
    return () => { cancelled = true; };
  }, [token]);

  return (
    <main className="min-h-screen bg-gradient-to-br from-white to-gray-50">
      {/* Cabecalho fixo com a marca da FAI e o titulo da conversa */}
      <header className="sticky top-0 z-10 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div className="min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-widest text-accent-blue">
              FAI•UFSCar · Conversa compartilhada
            </div>
            <h1 className="truncate text-sm font-semibold text-foreground" title={title}>
              {status === "ok" ? title : "Conversa"}
            </h1>
          </div>
          <span className="shrink-0 rounded-full border border-border bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">
            Somente leitura
          </span>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-4 py-6">
        {status === "loading" && (
          <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
            <Loader2 className="size-5 animate-spin text-accent-blue" /> Carregando conversa…
          </div>
        )}

        {(status === "notfound" || status === "error") && (
          <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
            <Link2Off className="size-8 text-muted-foreground" />
            <p className="text-sm font-medium text-foreground">
              {status === "notfound" ? "Link inválido ou conversa indisponível." : "Não foi possível carregar a conversa."}
            </p>
            <p className="max-w-sm text-xs text-muted-foreground">
              Verifique se o link está completo e correto. Se o problema persistir, solicite um novo link a quem compartilhou.
            </p>
          </div>
        )}

        {status === "ok" && (
          <div className="space-y-6">
            {messages.length === 0 && (
              <p className="py-20 text-center text-sm text-muted-foreground">Esta conversa não tem mensagens.</p>
            )}
            {messages.map((m, idx) => (
              <div key={idx} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[85%] space-y-2 ${m.role === "user" ? "items-end" : "items-start"}`}>
                  <div
                    className={`rounded-2xl px-4 py-2 shadow-sm ${
                      m.role === "user"
                        ? "rounded-tr-none bg-accent-blue text-white"
                        : "rounded-tl-none border border-border bg-card text-card-foreground"
                    }`}
                  >
                    <div
                      className={`prose prose-sm max-w-none prose-p:leading-relaxed ${
                        m.role === "user"
                          ? "prose-invert prose-p:text-white prose-headings:text-white prose-a:text-blue-200"
                          : "prose-gray"
                      }`}
                    >
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                    </div>
                  </div>

                  {m.role === "assistant" && m.sources && m.sources.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                        <FileText size={10} /> Fontes Pesquisadas
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {m.sources.map((s, i) => (
                          <span
                            key={i}
                            className="rounded-md border border-border bg-muted px-2 py-1 text-[10px] text-muted-foreground"
                          >
                            {sourceLabel(s)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <footer className="mx-auto max-w-3xl px-4 pb-10 pt-2 text-center text-[10px] text-muted-foreground">
        Gerado pela assistente virtual da FAI•UFSCar. Conteúdo somente para leitura.
      </footer>
    </main>
  );
}
