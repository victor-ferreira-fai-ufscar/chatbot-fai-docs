"use client";

import { useState, useEffect, useRef } from "react";
import Image from "next/image";
import { Copy, Check, Menu, FileText, MessageSquarePlus } from "lucide-react";
import { toast } from "sonner";
import Sidebar from "@/components/layout/Sidebar";
import SourcesPanel, { parseSourceItems } from "@/components/layout/SourcesPanel";
import ChatWindow from "@/components/chat/ChatWindow";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Sheet, SheetContent, SheetTitle, SheetDescription } from "@/components/ui/sheet";

export type SidebarMode = "history" | "settings";

export default function Home() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("history");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  // Superfícies exclusivas de mobile (<lg): gaveta do menu (hambúrguer do header)
  // e gaveta de fontes (botão do header). Estado independente do viewport — só
  // muda por toque em botões lg:hidden, então SSR/hidratação são idênticos.
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  // Estado do servico de RAG (LightRAG), sondado pelo backend em /status.
  // null = ainda verificando; "online"/"offline" alimentam a bolinha da sidebar.
  const [lightragStatus, setLightragStatus] = useState<"online" | "offline" | null>(null);
  // ID de sessao do usuario (sem login ainda): gerado e guardado no localStorage
  const [userId, setUserId] = useState<string | null>(null);
  // Fontes da resposta atual (alimenta a SourcesPanel estilo NotebookLM, 3a coluna).
  const [activeSources, setActiveSources] = useState<string[]>([]);
  const [activeAnswer, setActiveAnswer] = useState<string>("");
  const [sourcesLoading, setSourcesLoading] = useState(false);
  // Compartilhamento: URL do link gerado (null = modal fechado) + feedback de "copiado".
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [shareCopied, setShareCopied] = useState(false);
  // Renomeações otimistas ainda não confirmadas pelo servidor (id -> título novo).
  // fetchHistory sobrepõe esses títulos por cima do payload do backend até o servidor
  // refletir o valor — sem isso, um GET obsoleto (poll de 15s) reverteria o rename.
  const pendingRenamesRef = useRef<Map<number, string>>(new Map());

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  // Configurações Globais de Chat
  const [config, setConfig] = useState({
    ragEngine: "LightRAG (Grafo)",
    lightragMode: "mix",
    provider: "OpenAI API",
    model: "gpt-4o-mini",
    topK: 4,
    threshold: 0.0
  });

  // Carregar histórico do backend (do usuário da sessão)
  const fetchHistory = async (uid: string | null = userId) => {
    if (!uid) return;
    // A conectividade (backend + LightRAG) é responsabilidade ÚNICA do checkStatus()
    // (sonda /status). Aqui só carregamos as conversas — se também escrevêssemos
    // isBackendConnected, os dois pollers competiriam pelo mesmo estado e a bolinha
    // ficaria piscando entre online/offline.
    try {
      const response = await fetch(`${API_BASE_URL}/history/?user_id=${encodeURIComponent(uid)}`);
      if (response.ok) {
        const data = await response.json();
        // Preserva renomeações pendentes: se este GET foi lido ANTES do PATCH commitar,
        // ele traz o título antigo. Sobrepomos pelo pendente; quando o servidor já
        // reflete o novo, limpamos o pendente (reconciliado).
        const pend = pendingRenamesRef.current;
        if (pend.size > 0) {
          for (const c of data) {
            const p = pend.get(c.id);
            if (p === undefined) continue;
            if (c.title === p) pend.delete(c.id);
            else c.title = p;
          }
        }
        setConversations(data);
      }
    } catch (e) {
      console.error("Erro ao buscar histórico", e);
    }
  };

  // Fonte única de verdade da conexão: o backend (/status) confirma que está no ar
  // e sonda o LightRAG de fato. Distingue três casos para a bolinha não mentir:
  //   200            -> backend ok; lightrag = online/offline conforme a sonda
  //   resposta !ok   -> backend respondeu (logo, no ar), mas /status ainda não existe
  //                     (imagem antiga) ou deu erro -> estado do RAG desconhecido ("verificando")
  //   falha de rede  -> nem o backend responde -> "sem conexão"
  const checkStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/status`);
      if (response.ok) {
        setIsBackendConnected(true);
        const data = await response.json();
        setLightragStatus(data?.lightrag?.status === "online" ? "online" : "offline");
      } else {
        setIsBackendConnected(true);
        setLightragStatus(null);
      }
    } catch (e) {
      console.error("Erro ao verificar status", e);
      setIsBackendConnected(false);
      setLightragStatus(null);
    }
  };

  // Inicializar config e ID de sessão no mount
  useEffect(() => {
    const savedConfig = localStorage.getItem("fai_chatbot_config");
    if (savedConfig) {
      try {
        const parsed = JSON.parse(savedConfig);
        // Migracao unica: configs antigas ficaram no default "hybrid". "mix" (grafo+vetorial)
        // recupera o trecho exato e provou-se bem mais preciso, entao empurramos "mix" UMA vez.
        // Escolhas futuras do usuario no seletor de Modo sao respeitadas (flag impede repetir).
        if (!localStorage.getItem("fai_cfg_mode_mix_v1")) {
          parsed.lightragMode = "mix";
        }
        setConfig(parsed);
      } catch (e) {
        console.error("Erro ao carregar config", e);
      }
    }
    localStorage.setItem("fai_cfg_mode_mix_v1", "1");
    let uid = localStorage.getItem("fai_user_id");
    if (!uid) {
      uid = (crypto?.randomUUID?.() ?? `sess-${Date.now()}-${Math.random().toString(36).slice(2)}`);
      localStorage.setItem("fai_user_id", uid);
    }
    setUserId(uid);
  }, []);

  // Buscar histórico e iniciar polling de saúde quando o userId estiver disponível
  useEffect(() => {
    if (!userId) return;
    fetchHistory(userId);
    const healthCheck = setInterval(() => fetchHistory(userId), 15000);
    return () => clearInterval(healthCheck);
  }, [userId]);

  // Polling do status do RAG (independe do userId): sonda /status no mount e a cada 15s.
  useEffect(() => {
    checkStatus();
    const statusCheck = setInterval(checkStatus, 15000);
    return () => clearInterval(statusCheck);
  }, []);

  // Salvar persistência
  useEffect(() => {
    localStorage.setItem("fai_chatbot_config", JSON.stringify(config));
  }, [config]);

  const handleNewChat = () => {
    setSelectedConversationId(null);
    setSidebarMode("history");
  };

  const handleSelectConversation = (id: number) => {
    setSelectedConversationId(id);
    setSidebarMode("history");
  };

  const handleRenameConversation = async (id: number, newTitle: string) => {
    const title = newTitle.trim();
    if (!title || !userId) return;
    // Marca como pendente ANTES do update otimista: sobrevive a um fetchHistory
    // concorrente (poll de 15s / fim de streaming) até o servidor confirmar.
    pendingRenamesRef.current.set(id, title);
    setConversations((prev) => prev.map((c: any) => (c.id === id ? { ...c, title } : c)));
    try {
      const res = await fetch(`${API_BASE_URL}/history/${id}?user_id=${encodeURIComponent(userId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Sucesso: mantém pendente até um fetchHistory ver o título novo — um GET obsoleto
      // (lido antes do PATCH) ainda pode estar em voo. O próximo poll reconcilia e limpa.
    } catch (e) {
      console.error("Erro ao renomear conversa", e);
      pendingRenamesRef.current.delete(id);
      fetchHistory();
    }
  };

  const handleShareConversation = async (id: number) => {
    if (!userId) return;
    try {
      const res = await fetch(
        `${API_BASE_URL}/history/${id}/share?user_id=${encodeURIComponent(userId)}`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // O backend devolve o caminho relativo (/shared/<token>); a origem é a do próprio app.
      setShareCopied(false);
      setShareUrl(`${window.location.origin}${data.path}`);
    } catch (e) {
      console.error("Erro ao compartilhar conversa", e);
      toast.error("Não foi possível gerar o link de compartilhamento.");
    }
  };

  const handleCopyShareUrl = async () => {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setShareCopied(true);
      toast.success("Link copiado!");
      setTimeout(() => setShareCopied(false), 2000);
    } catch {
      toast.error("Não foi possível copiar automaticamente. Copie o link manualmente.");
    }
  };

  const handleDeleteConversation = async (id: number) => {
    if (!confirm("Tem certeza que deseja excluir esta conversa?")) return;

    try {
      await fetch(`${API_BASE_URL}/history/${id}?user_id=${encodeURIComponent(userId ?? "")}`, { method: 'DELETE' });
      pendingRenamesRef.current.delete(id); // conversa foi embora: descarta rename pendente órfão
      setConversations(conversations.filter((c: any) => c.id !== id));
      if (selectedConversationId === id) setSelectedConversationId(null);
      fetchHistory();
    } catch (e) {
      console.error("Erro ao deletar conversa", e);
    }
  };

  const handleClearHistory = async () => {
    if (!userId) return;
    if (!confirm("Tem certeza que deseja limpar todo o histórico de conversas?")) return;

    try {
      await fetch(`${API_BASE_URL}/history/?user_id=${encodeURIComponent(userId)}`, { method: 'DELETE' });
      setConversations([]);
      setSelectedConversationId(null);
      fetchHistory();
    } catch (e) {
      console.error("Erro ao limpar histórico", e);
    }
  };

  const toggleSettings = () => {
    if (sidebarMode === "history") {
      setSidebarMode("settings");
      setIsSidebarCollapsed(false); // Expansão automática
    } else {
      setSidebarMode("history");
    }
  };

  // Badge do botão de fontes do header mobile: mesma contagem que o painel
  // (um item por página citada), via o parse exportado pelo SourcesPanel.
  const mobileSourceCount = parseSourceItems(activeSources).length;

  return (
    <main className="flex h-screen max-lg:h-dvh overflow-hidden">
        <Sidebar
          mode={sidebarMode}
          setMode={setSidebarMode}
          isCollapsed={isSidebarCollapsed}
          setIsCollapsed={setIsSidebarCollapsed}
          onNewChat={handleNewChat}
          onClearHistory={handleClearHistory}
          onOpenSettings={toggleSettings}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          onRenameConversation={handleRenameConversation}
          onShareConversation={handleShareConversation}
          selectedConversationId={selectedConversationId}
          conversations={conversations}
          isBackendConnected={isBackendConnected}
          lightragStatus={lightragStatus}
          config={config}
          setConfig={setConfig}
          className="max-lg:hidden"
        />

        {/* min-w-0: sem isso o flex child não encolhe abaixo do min-content do
            conteúdo (input/chips) e estoura o layout em telas estreitas. */}
        <div className="flex-1 min-w-0 relative bg-gradient-to-br from-white to-gray-50 flex flex-col">
          {/* Header exclusivo de mobile (<lg): hambúrguer (gaveta do menu), marca,
              fontes (gaveta) e nova conversa. Em desktop não existe (display:none). */}
          <header className="lg:hidden flex h-12 shrink-0 items-center gap-1 border-b border-border bg-card px-2">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              data-testid="mobile-menu-button"
              aria-label="Abrir menu"
              className="text-muted-foreground"
              onClick={() => setMobileSidebarOpen(true)}
            >
              <Menu size={20} />
            </Button>
            <Image src="/fai-icone.png" alt="" width={22} height={22} className="ml-1 shrink-0 object-contain" />
            <span className="truncate text-sm font-semibold text-foreground">
              Lina <span className="font-light text-muted-foreground">· FAI-UFSCar</span>
            </span>
            <div className="flex-1" />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              data-testid="mobile-sources-button"
              aria-label="Ver fontes"
              className="relative text-muted-foreground"
              onClick={() => setSourcesOpen(true)}
            >
              <FileText size={20} />
              {mobileSourceCount > 0 && (
                <span className="absolute top-0.5 right-0.5 flex h-[15px] min-w-[15px] items-center justify-center rounded-full bg-accent-orange px-1 text-[9px] font-bold text-white">
                  {mobileSourceCount}
                </span>
              )}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              data-testid="mobile-new-chat"
              aria-label="Nova conversa"
              className="text-muted-foreground"
              onClick={handleNewChat}
            >
              <MessageSquarePlus size={20} />
            </Button>
          </header>
          {/* Wrapper flex-1 min-h-0: reserva a altura restante abaixo do header
              mobile; em desktop (header display:none) equivale ao layout antigo. */}
          <div className="flex min-h-0 flex-1 flex-col">
            <ChatWindow
              config={config}
              userId={userId}
              selectedConversationId={selectedConversationId}
              onConversationCreated={fetchHistory}
              onNewChat={handleNewChat}
              onActiveSources={(s, a) => { setActiveSources(s); setActiveAnswer(a); }}
              onGenerating={(g) => { setSourcesLoading(g); if (g) { setActiveSources([]); setActiveAnswer(""); } }}
              onOpenSourcesPanel={() => setSourcesOpen(true)}
            />
          </div>
        </div>

        <SourcesPanel
          sources={activeSources}
          answerContent={activeAnswer}
          loading={sourcesLoading}
          mobileOpen={sourcesOpen}
          onMobileOpenChange={setSourcesOpen}
        />

        {/* Gaveta do menu em mobile: renderiza a MESMA <Sidebar> (o Radix desmonta o
            conteúdo com a gaveta fechada, então em desktop nunca há duplicata no DOM).
            isCollapsed fixo em false: o chevron "Minimizar menu" passa a fechar a gaveta. */}
        <Sheet open={mobileSidebarOpen} onOpenChange={setMobileSidebarOpen}>
          <SheetContent
            side="left"
            showCloseButton={false}
            className="w-72 max-w-[85vw] gap-0 border-sidebar-hover bg-sidebar-dark p-0 text-gray-300"
            // Sem auto-foco no primeiro botão: o foco programático abria o tooltip
            // "Minimizar menu" junto com a gaveta (artefato visual em toque).
            onOpenAutoFocus={(e) => e.preventDefault()}
          >
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <SheetDescription className="sr-only">Histórico de conversas e configurações.</SheetDescription>
            <Sidebar
              mode={sidebarMode}
              setMode={setSidebarMode}
              isCollapsed={false}
              setIsCollapsed={(v) => { if (v) setMobileSidebarOpen(false); }}
              onNewChat={() => { handleNewChat(); setMobileSidebarOpen(false); }}
              onClearHistory={handleClearHistory}
              onOpenSettings={toggleSettings}
              onSelectConversation={(id) => { handleSelectConversation(id); setMobileSidebarOpen(false); }}
              onDeleteConversation={handleDeleteConversation}
              onRenameConversation={handleRenameConversation}
              onShareConversation={(id) => { setMobileSidebarOpen(false); handleShareConversation(id); }}
              selectedConversationId={selectedConversationId}
              conversations={conversations}
              isBackendConnected={isBackendConnected}
              lightragStatus={lightragStatus}
              config={config}
              setConfig={setConfig}
              className="w-full"
            />
          </SheetContent>
        </Sheet>

        <Dialog open={shareUrl !== null} onOpenChange={(open) => { if (!open) setShareUrl(null); }}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Compartilhar conversa</DialogTitle>
              <DialogDescription>
                Qualquer pessoa com este link poderá visualizar a conversa (somente leitura).
              </DialogDescription>
            </DialogHeader>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={shareUrl ?? ""}
                onFocus={(e) => e.currentTarget.select()}
                aria-label="Link de compartilhamento"
                className="flex-1 min-w-0 rounded-md border border-border bg-muted px-3 py-2 text-sm max-lg:text-base text-foreground outline-none focus:ring-1 focus:ring-accent-blue"
              />
              <Button type="button" onClick={handleCopyShareUrl} className="shrink-0 gap-1.5">
                {shareCopied ? <Check className="size-4" /> : <Copy className="size-4" />}
                {shareCopied ? "Copiado" : "Copiar"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
    </main>
  );
}
