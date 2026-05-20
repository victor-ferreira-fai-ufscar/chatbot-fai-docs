"use client";

import { useState, useEffect } from "react";
import Header from "@/components/layout/Header";
import Sidebar from "@/components/layout/Sidebar";
import ChatWindow from "@/components/chat/ChatWindow";

export type SidebarMode = "history" | "settings";

export default function Home() {
  const [conversations, setConversations] = useState([]);
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("history");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [selectedConversationId, setSelectedConversationId] = useState<number | null>(null);
  const [isBackendConnected, setIsBackendConnected] = useState<boolean | null>(null);
  
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  // Configurações Globais de Chat
  const [config, setConfig] = useState({
    ragEngine: "Supabase (Padrão)",
    lightragMode: "hybrid",
    provider: "OpenAI API",
    model: "gpt-4o-mini",
    topK: 4,
    threshold: 0.0
  });

  // Carregar histórico do backend
  const fetchHistory = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/history/`);
      if (response.ok) {
        setIsBackendConnected(true);
        const data = await response.json();
        setConversations(data);
      } else {
        setIsBackendConnected(false);
      }
    } catch (e) {
      console.error("Erro ao buscar histórico", e);
      setIsBackendConnected(false);
    }
  };

  // Carregar persistência e histórico no mount
  useEffect(() => {
    const savedConfig = localStorage.getItem("fai_chatbot_config");
    if (savedConfig) {
      try {
        setConfig(JSON.parse(savedConfig));
      } catch (e) {
        console.error("Erro ao carregar config", e);
      }
    }
    fetchHistory();
    // Iniciar polling de saúde
    const healthCheck = setInterval(fetchHistory, 15000);
    return () => clearInterval(healthCheck);
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
      await fetch(`${API_BASE_URL}/history/${id}`, { method: 'DELETE' });
      setConversations(conversations.filter((c: any) => c.id !== id));
      if (selectedConversationId === id) setSelectedConversationId(null);
      fetchHistory();
    } catch (e) {
      console.error("Erro ao deletar conversa", e);
    }
  };

  const handleClearHistory = () => {
    // Para simplificar, poderíamos deletar todos no backend ou apenas resetar local
    setConversations([]);
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
    <div className="flex flex-col h-screen overflow-hidden">
      <Header 
        onToggleSidebar={() => setIsSidebarCollapsed(!isSidebarCollapsed)} 
        isBackendConnected={isBackendConnected}
      />
      
      <main className="flex flex-1 overflow-hidden">
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
          config={config}
          setConfig={setConfig}
        />
        
        <div className="flex-1 relative bg-gradient-to-br from-white to-gray-50 flex flex-col">
          <ChatWindow 
            config={config} 
            selectedConversationId={selectedConversationId}
            onConversationCreated={fetchHistory}
          />
        </div>
      </main>
    </div>
  );
}
