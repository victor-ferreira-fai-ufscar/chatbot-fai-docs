"use client";

import { useState, useEffect } from "react";
import Sidebar from "@/components/layout/Sidebar";
import SourcesPanel from "@/components/layout/SourcesPanel";
import ChatWindow from "@/components/chat/ChatWindow";

export type SidebarMode = "history" | "settings";

export default function Home() {
  const [conversations, setConversations] = useState([]);
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("history");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
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

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  // Configurações Globais de Chat
  const [config, setConfig] = useState({
    ragEngine: "LightRAG (Grafo)",
    lightragMode: "hybrid",
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
        setConfig(JSON.parse(savedConfig));
      } catch (e) {
        console.error("Erro ao carregar config", e);
      }
    }
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

  const handleDeleteConversation = async (id: number) => {
    if (!confirm("Tem certeza que deseja excluir esta conversa?")) return;

    try {
      await fetch(`${API_BASE_URL}/history/${id}?user_id=${encodeURIComponent(userId ?? "")}`, { method: 'DELETE' });
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

  return (
    <main className="flex h-screen overflow-hidden">
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
          selectedConversationId={selectedConversationId}
          conversations={conversations}
          isBackendConnected={isBackendConnected}
          lightragStatus={lightragStatus}
          config={config}
          setConfig={setConfig}
        />
        
        <div className="flex-1 relative bg-gradient-to-br from-white to-gray-50 flex flex-col">
          <ChatWindow
            config={config}
            userId={userId}
            selectedConversationId={selectedConversationId}
            onConversationCreated={fetchHistory}
            onActiveSources={(s, a) => { setActiveSources(s); setActiveAnswer(a); }}
            onGenerating={(g) => { setSourcesLoading(g); if (g) { setActiveSources([]); setActiveAnswer(""); } }}
          />
        </div>

        <SourcesPanel sources={activeSources} answerContent={activeAnswer} loading={sourcesLoading} />
    </main>
  );
}
