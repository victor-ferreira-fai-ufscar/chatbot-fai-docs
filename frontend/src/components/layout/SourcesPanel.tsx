"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  PanelRight,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---- parsing das linhas de fonte ("- Manual do Coordenador.pdf (págs. 4-6, 9)") ----
function parseFilename(line: string): string {
  return line
    .replace(/^-\s*/, "")
    .replace(/\s*\((?:ref id:|p[áa]gs?\.).*\)\s*$/i, "")
    .trim();
}

function parsePages(line: string): number[] {
  const m = line.match(/p[áa]gs?\.\s*([\d\s,\-]+)/i);
  if (!m) return [];
  const pages = new Set<number>();
  for (const tok of m[1].split(/[,\s]+/)) {
    const r = tok.match(/^(\d{1,4})(?:-(\d{1,4}))?$/);
    if (!r) continue;
    const a = parseInt(r[1], 10);
    const b = r[2] ? parseInt(r[2], 10) : a;
    if (b >= a && b - a < 60) for (let p = a; p <= b; p++) pages.add(p);
  }
  return [...pages].sort((x, y) => x - y);
}

// Normaliza para comparacao (minuscula, sem acento, so alfanumerico).
function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9]/g, "");
}

// Termos de conteudo (>=5 letras) da resposta, para destacar no trecho-fonte.
const STOP = new Set([
  "sobre", "para", "como", "quando", "onde", "manual", "coordenador", "fonte", "fontes",
  "pagina", "paginas", "pode", "deve", "esta", "essa", "esse", "pelo", "pela", "pelos",
  "pelas", "dos", "das", "com", "uma", "que", "nao", "sera", "seja", "ainda", "entao",
  "todos", "todas", "cada", "qual", "quais", "porem", "tambem", "apos", "ate",
]);
function answerTerms(answer: string): Set<string> {
  const words = norm(answer || "").match(/[a-z0-9]{5,}/g) || [];
  return new Set(words.filter((w) => !STOP.has(w)).slice(0, 60));
}

// Renderiza o texto destacando palavras cujo radical normalizado esta em `terms`.
function Highlighted({ text, terms }: { text: string; terms: Set<string> }) {
  if (!terms.size || !text) return <>{text}</>;
  const parts = text.split(/(\s+)/);
  return (
    <>
      {parts.map((w, i) => {
        const n = norm(w);
        return n.length >= 5 && terms.has(n) ? (
          <mark key={i} className="bg-amber-100 text-gray-900 rounded px-0.5">{w}</mark>
        ) : (
          <span key={i}>{w}</span>
        );
      })}
    </>
  );
}

interface SourceItem {
  file: string;
  page: number | null;
}

function SourceCard({ item, terms }: { item: SourceItem; terms: Set<string> }) {
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (item.page == null) return;
    setLoading(true);
    setError(false);
    fetch(`${API_BASE_URL}/documents/page-text?name=${encodeURIComponent(item.file)}&page=${item.page}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => { if (!cancelled) setText((d.text || "").trim()); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [item.file, item.page]);

  const openPdf = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/documents/download-url?name=${encodeURIComponent(item.file)}`);
      if (!res.ok) return;
      const data = await res.json();
      const url = item.page ? `${data.signed_url}#page=${item.page}` : data.signed_url;
      window.open(url, "_blank", "noopener,noreferrer");
    } catch { /* silencioso */ }
  };

  const LIMIT = 480;
  const long = (text?.length || 0) > LIMIT;
  const shown = text && !expanded && long ? text.slice(0, LIMIT) + "…" : text;

  return (
    <Card className="gap-0 overflow-hidden rounded-lg py-0 shadow-none transition-colors hover:border-accent-blue/40">
      <CardHeader className="grid-cols-[1fr_auto] items-center gap-2 border-b bg-muted/50 px-3 py-2 [.border-b]:pb-2">
        <div className="flex min-w-0 items-center gap-2">
          {item.page != null && (
            <Badge
              variant="secondary"
              className="shrink-0 rounded bg-accent-blue/10 px-1.5 py-0.5 text-[10px] font-bold text-accent-blue"
            >
              Pág. {item.page}
            </Badge>
          )}
          <span className="truncate text-[11px] text-muted-foreground" title={item.file}>{item.file}</span>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={openPdf}
              className="shrink-0 text-muted-foreground hover:text-accent-blue"
              aria-label={`Abrir o PDF${item.page != null ? ` na página ${item.page}` : ""}`}
            >
              <ExternalLink size={13} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>{`Abrir o PDF${item.page != null ? ` na página ${item.page}` : ""}`}</TooltipContent>
        </Tooltip>
      </CardHeader>

      <CardContent className="px-3 py-2 text-[12px] leading-relaxed text-gray-700">
        {loading && (
          <div className="flex items-center gap-2 py-1 text-[11px] text-muted-foreground">
            <Spinner className="size-3" /> carregando trecho…
          </div>
        )}
        {error && <div className="py-1 text-[11px] italic text-muted-foreground">Trecho indisponível.</div>}
        {shown && (
          <>
            <p className="whitespace-pre-wrap"><Highlighted text={shown} terms={terms} /></p>
            {long && (
              <Button
                type="button"
                variant="link"
                size="xs"
                onClick={() => setExpanded((e) => !e)}
                className="mt-1 h-auto p-0 text-[10px] font-medium text-accent-blue"
              >
                {expanded ? <><ChevronUp size={11} /> ver menos</> : <><ChevronDown size={11} /> ver trecho completo</>}
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface SourcesPanelProps {
  sources: string[];
  answerContent: string;
  loading?: boolean;
}

export default function SourcesPanel({ sources, answerContent, loading = false }: SourcesPanelProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  // Expande cada linha de fonte (que pode citar varias paginas) num card por pagina.
  const items: SourceItem[] = [];
  for (const line of sources || []) {
    const file = parseFilename(line);
    if (!file) continue;
    const pages = parsePages(line);
    if (pages.length === 0) items.push({ file, page: null });
    else for (const p of pages) items.push({ file, page: p });
  }
  const terms = answerTerms(answerContent);

  const header = (onCollapse?: () => void) => (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b px-4">
      <FileText size={15} className="text-accent-blue" />
      <span className="text-sm font-semibold text-gray-700">Fontes</span>
      {items.length > 0 && (
        <Badge variant="secondary" className="rounded-full px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          {items.length}
        </Badge>
      )}
      {onCollapse && (
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={onCollapse}
              className="ml-auto text-muted-foreground hover:text-gray-700"
              aria-label="Minimizar painel de fontes"
            >
              <ChevronRight size={16} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Minimizar fontes</TooltipContent>
        </Tooltip>
      )}
    </div>
  );

  const list = (
    <ScrollArea className="flex-1">
      <div className="space-y-3 p-3">
        {loading && items.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 px-4 text-center text-muted-foreground">
            <Spinner className="size-5 text-accent-blue" />
            <p className="text-xs">Buscando as fontes da resposta…</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 text-center text-muted-foreground">
            <FileText size={28} className="mb-3 opacity-40" />
            <p className="text-xs leading-relaxed">
              As fontes da resposta aparecerão aqui, com a página e o trecho do manual em que a Lina se baseou.
            </p>
          </div>
        ) : (
          items.map((item, i) => <SourceCard key={`${item.file}-${item.page}-${i}`} item={item} terms={terms} />)
        )}
      </div>
    </ScrollArea>
  );

  return (
    <>
      {/* Desktop: 3a coluna fixa (telas grandes) */}
      {collapsed ? (
        // Trilho estreito quando minimizado: botao para reexpandir.
        <aside className="hidden h-full w-10 shrink-0 flex-col items-center border-l bg-white py-2 lg:flex">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => setCollapsed(false)}
                className="relative text-accent-blue hover:text-accent-blue"
                aria-label="Expandir painel de fontes"
              >
                <PanelRight size={18} />
                {items.length > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 flex h-[15px] min-w-[15px] items-center justify-center rounded-full bg-accent-orange px-1 text-[9px] font-bold text-white">
                    {items.length}
                  </span>
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="left">Mostrar fontes</TooltipContent>
          </Tooltip>
        </aside>
      ) : (
        <aside className="hidden h-full w-80 shrink-0 flex-col border-l bg-white lg:flex">
          {header(() => setCollapsed(true))}
          {list}
        </aside>
      )}

      {/* Mobile/telas estreitas: botao flutuante que abre a gaveta (Sheet) */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="icon-lg"
              onClick={() => setMobileOpen(true)}
              className="fixed bottom-5 right-5 z-30 rounded-full bg-accent-blue text-white shadow-lg hover:bg-accent-blue-hover lg:hidden"
              aria-label="Ver fontes"
            >
              <FileText size={20} />
              {items.length > 0 && (
                <span className="absolute -top-1 -right-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-accent-orange px-1 text-[10px] font-bold text-white">
                  {items.length}
                </span>
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="left">Ver fontes</TooltipContent>
        </Tooltip>

        <SheetContent
          side="right"
          showCloseButton
          className="w-80 max-w-[85vw] gap-0 p-0"
        >
          <SheetHeader className="flex h-12 shrink-0 flex-row items-center gap-2 space-y-0 border-b px-4 py-0">
            <FileText size={15} className="text-accent-blue" />
            <SheetTitle className="text-sm font-semibold text-gray-700">Fontes</SheetTitle>
            {items.length > 0 && (
              <Badge variant="secondary" className="rounded-full px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                {items.length}
              </Badge>
            )}
            <SheetDescription className="sr-only">
              Páginas e trechos do manual em que a Lina se baseou para responder.
            </SheetDescription>
          </SheetHeader>
          {list}
        </SheetContent>
      </Sheet>
    </>
  );
}
