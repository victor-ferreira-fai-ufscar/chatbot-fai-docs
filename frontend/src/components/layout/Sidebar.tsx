import { MessageSquarePlus, Trash2, Settings, History, Plus, ArrowLeft, Info, X, HelpCircle } from 'lucide-react';
import { useState, useEffect } from 'react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { SidebarMode } from '@/app/page';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface SidebarProps {
  mode: SidebarMode;
  setMode: (mode: SidebarMode) => void;
  isCollapsed: boolean;
  setIsCollapsed: (v: boolean) => void;
  onNewChat: () => void;
  onClearHistory: () => void;
  onOpenSettings: () => void;
  onSelectConversation: (id: number) => void;
  onDeleteConversation: (id: number) => void;
  selectedConversationId: number | null;
  conversations: any[];
  config: any;
  setConfig: (v: any) => void;
}

export default function Sidebar({ 
  mode, 
  setMode, 
  isCollapsed, 
  setIsCollapsed,
  onNewChat, 
  onClearHistory, 
  onOpenSettings, 
  onSelectConversation,
  onDeleteConversation,
  selectedConversationId,
  conversations,
  config,
  setConfig
}: SidebarProps) {
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<{name: string, label: string}[]>([]);
  
  useEffect(() => {
    if (config.provider === "Ollama local") {
      const fetchOllamaModels = async () => {
        try {
          const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
          const res = await fetch(`${API_BASE_URL}/chat/ollama/models`);
          if (res.ok) {
            const data = await res.json();
            setOllamaModels(data);
            // Autoselecionar primeiro modelo se estiver vazio
            if (!config.model && data.length > 0) {
              setConfig((prev: any) => ({ ...prev, model: data[0].name }));
            }
          }
        } catch (e) {
          console.error("Erro ao buscar modelos Ollama", e);
        }
      };
      fetchOllamaModels();
    }
  }, [config.provider]);

  const handleConfigChange = (field: string, value: any) => {
    setConfig((prev: any) => ({ ...prev, [field]: value }));
  };

  return (
    <>
      <aside className={cn(
        "bg-sidebar-dark flex flex-col text-gray-300 h-[calc(100vh-3.5rem)] transition-all duration-300 ease-in-out z-20",
        isCollapsed ? "w-16" : "w-64"
      )}>
        
        {mode === "history" ? (
          <>
            {/* Top Actions */}
            <div className="p-3 space-y-2 border-b border-sidebar-hover">
              <button 
                onClick={onNewChat}
                className={cn(
                  "w-full flex items-center bg-accent-blue hover:bg-accent-blue-hover text-white rounded font-medium transition-all duration-200",
                  isCollapsed ? "justify-center p-2" : "gap-2 py-2 px-3 text-sm"
                )}
                title="Nova Conversa"
              >
                {isCollapsed ? <Plus size={20} /> : <><MessageSquarePlus size={18} /> Nova Conversa</>}
              </button>
              
              <button 
                onClick={onOpenSettings}
                className={cn(
                  "w-full flex items-center bg-sidebar-hover hover:bg-gray-700 text-white rounded transition-all duration-200 border border-gray-600",
                  isCollapsed ? "justify-center p-2" : "gap-2 py-2 px-3 text-sm"
                )}
                title="Configurações"
              >
                <Settings size={isCollapsed ? 20 : 18} />
                {!isCollapsed && <span>Configurações</span>}
              </button>

              {!isCollapsed && (
                <button 
                  onClick={onClearHistory}
                  className="w-full flex items-center gap-2 text-gray-400 hover:text-accent-orange text-xs py-1 transition-colors group"
                >
                  <Trash2 size={14} className="group-hover:text-accent-orange" />
                  Limpar histórico
                </button>
              )}
            </div>

            {/* History List */}
            <div className="flex-1 overflow-y-auto px-2 py-4">
              {!isCollapsed && (
                <div className="flex items-center gap-2 px-2 mb-4 text-xs font-semibold text-gray-500 uppercase tracking-widest">
                  <History size={12} />
                  Histórico
                </div>
              )}
              
              {isCollapsed ? (
                <div className="flex flex-col items-center gap-4 text-gray-600">
                  <History size={20} />
                </div>
              ) : (
                conversations.length === 0 ? (
                  <div className="px-3 text-xs text-gray-500 italic">Nenhuma conversa recente</div>
                ) : (
                  <div className="space-y-1">
                    {conversations.map((conv) => (
                      <div 
                        key={conv.id} 
                        className={cn(
                          "group flex items-center gap-1 rounded transition-colors pr-1",
                          selectedConversationId === conv.id ? "bg-sidebar-hover text-white shadow-sm" : "hover:bg-sidebar-hover/50"
                        )}
                      >
                        <button 
                          onClick={() => onSelectConversation(conv.id)}
                          className="flex-1 text-left px-3 py-2 text-sm truncate"
                          title={conv.title}
                        >
                          {conv.title}
                        </button>
                        
                        <button 
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteConversation(conv.id);
                          }}
                          className="p-1.5 text-gray-500 hover:text-accent-orange opacity-0 group-hover:opacity-100 transition-all"
                          title="Excluir conversa"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    ))}
                  </div>
                )
              )}
            </div>
          </>
        ) : (
          /* Settings View */
          <div className="flex flex-col h-full overflow-hidden">
            <div className="p-4 border-b border-sidebar-hover flex items-center justify-between">
               <div className="flex items-center gap-3">
                  <button 
                    onClick={() => setMode("history")}
                    className="p-1 hover:bg-sidebar-hover rounded transition-colors"
                    title="Voltar ao Histórico"
                  >
                      <ArrowLeft size={18} />
                  </button>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">Configurações</h2>
               </div>
               <button 
                onClick={() => setIsHelpModalOpen(true)}
                className="p-1 text-gray-500 hover:text-accent-blue transition-colors"
                title="Ajuda sobre o Motor"
               >
                 <HelpCircle size={20} />
               </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 space-y-6">
               {/* Motor RAG */}
               <div className="space-y-2">
                 <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Motor de RAG</label>
                 <select 
                  value={config.ragEngine}
                  onChange={(e) => handleConfigChange("ragEngine", e.target.value)}
                  className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                 >
                   <option>LightRAG (Grafo)</option>
                 </select>
               </div>

               {config.ragEngine === "LightRAG (Grafo)" ? (
                  /* LightRAG Specific Mode */
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Modo LightRAG</label>
                      <select 
                        value={config.lightragMode}
                        onChange={(e) => handleConfigChange("lightragMode", e.target.value)}
                        className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                      >
                        <option value="hybrid">hybrid (Local + Global)</option>
                        <option value="mix">mix (Grafo + Vetorial)</option>
                        <option value="local">local (Específico)</option>
                        <option value="global">global (Geral)</option>
                        <option value="naive">naive (Vetorial Simples)</option>
                      </select>
                    </div>
                    <div className="p-3 bg-blue-900/20 border border-blue-900/30 rounded text-[10px] text-blue-300 leading-relaxed italic">
                      Neste modo, o LLM e embeddings são gerenciados pelo servidor LightRAG.
                    </div>
                  </div>
               ) : (
                  /* Supabase Mode Settings */
                  <div className="space-y-6 animate-in fade-in slide-in-from-top-2 duration-300">
                    {/* Provedor IA */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Provedor de IA</label>
                      <select 
                        value={config.provider}
                        onChange={(e) => handleConfigChange("provider", e.target.value)}
                        className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                      >
                        <option>OpenAI API</option>
                        <option>Google Gemini</option>
                        <option>Ollama local</option>
                      </select>
                    </div>

                    {/* Modelo */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Modelo</label>
                      {config.provider === "OpenAI API" ? (
                        <select
                          value={config.model}
                          onChange={(e) => handleConfigChange("model", e.target.value)}
                          className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                        >
                          <option value="gpt-4o-mini">gpt-4o-mini</option>
                          <option value="gpt-4o">gpt-4o</option>
                          <option value="gpt-4-turbo">gpt-4-turbo</option>
                          <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                        </select>
                      ) : config.provider === "Google Gemini" ? (
                        <select
                          value={config.model}
                          onChange={(e) => handleConfigChange("model", e.target.value)}
                          className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                        >
                          <option value="gemini-1.5-flash">gemini-1.5-flash</option>
                          <option value="gemini-1.5-pro">gemini-1.5-pro</option>
                          <option value="gemini-1.0-pro">gemini-1.0-pro</option>
                        </select>
                      ) : (
                        ollamaModels.length > 0 ? (
                          <select
                            value={config.model}
                            onChange={(e) => handleConfigChange("model", e.target.value)}
                            className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                          >
                            <option value="">Selecione um modelo local</option>
                            {ollamaModels.map((m) => (
                              <option key={m.name} value={m.name}>{m.label}</option>
                            ))}
                          </select>
                        ) : (
                          <input 
                            type="text"
                            value={config.model}
                            onChange={(e) => handleConfigChange("model", e.target.value)}
                            placeholder="Digitando ou conectando Ollama..."
                            className="w-full bg-sidebar-hover border-none text-xs rounded p-2 focus:ring-1 focus:ring-accent-blue"
                          />
                        )
                      )}
                    </div>

                    {/* Parâmetros */}
                    <div className="space-y-4 pt-4 border-t border-sidebar-hover">
                        <div className="flex justify-between items-center text-[10px] text-gray-500 uppercase tracking-widest">
                          <span>Trechos (Top K)</span>
                          <span className="text-white">{config.topK}</span>
                        </div>
                        <input 
                          type="range" min="1" max="20" step="1"
                          value={config.topK}
                          onChange={(e) => handleConfigChange("topK", parseInt(e.target.value))}
                          className="w-full accent-accent-blue"
                        />

                        <div className="flex justify-between items-center text-[10px] text-gray-500 uppercase tracking-widest">
                          <span>Threshold Relevância</span>
                          <span className="text-white">{config.threshold}</span>
                        </div>
                        <input 
                          type="range" min="0" max="1" step="0.05"
                          value={config.threshold}
                          onChange={(e) => handleConfigChange("threshold", parseFloat(e.target.value))}
                          className="w-full accent-accent-blue"
                        />
                    </div>
                  </div>
               )}
            </div>
          </div>
        )}

        {/* Footer Branding */}
        {!isCollapsed && (
          <div className="p-4 text-[10px] text-gray-600 border-t border-sidebar-hover text-center shrink-0">
            FAI-UFSCar Chatbot v1.0
          </div>
        )}
      </aside>

      {/* Unified Help Modal */}
      {isHelpModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col animate-in zoom-in duration-300">
            <div className="p-6 border-b flex items-center justify-between bg-gray-50">
              <div className="flex items-center gap-3">
                <HelpCircle className="text-accent-blue" size={24} />
                <h3 className="text-xl font-bold text-gray-900">
                  {config.ragEngine === "LightRAG (Grafo)" ? "Entendendo o LightRAG" : "Entendendo o Motor Supabase"}
                </h3>
              </div>
              <button 
                onClick={() => setIsHelpModalOpen(false)}
                className="p-2 hover:bg-gray-200 rounded-full transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {config.ragEngine === "LightRAG (Grafo)" ? (
                <>
                  <div className="p-4 bg-blue-50 border border-blue-100 rounded-lg">
                    <h4 className="font-bold text-blue-900 mb-1">O que é LightRAG (Grafo)?</h4>
                    <p className="text-sm text-blue-800 leading-relaxed">
                      Imagine um mapa que conecta todas as informações importantes dos seus documentos. Este motor não apenas lê o texto, ele "conecta os pontos" entre pessoas, normas e processos, entendendo como um assunto influencia o outro.
                    </p>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Card title="Hybrid" desc="O equilíbrio perfeito: responde bem tanto perguntas diretas quanto dúvidas mais amplas (Resumo + Detalhes)." />
                    <Card title="Mix" desc="Uma mistura entre a inteligência de conexões e a busca rápida por palavras-chave." />
                    <Card title="Local" desc="Especialista em detalhes: ideal para buscar informações sobre um ponto muito específico ou uma pessoa citada." />
                    <Card title="Global" desc="Visão panorâmica: ideal para entender temas gerais, tendências ou o 'quadro geral' dos seus documentos." />
                    <Card title="Naive" desc="Busca simples e direta baseada apenas na semelhança das palavras, sem olhar as conexões entre elas." />
                  </div>
                </>
              ) : (
                <>
                  <div className="p-4 bg-orange-50 border border-orange-100 rounded-lg">
                    <h4 className="font-bold text-orange-900 mb-1">O que é o Motor Tradicional?</h4>
                    <p className="text-sm text-orange-800 leading-relaxed">
                      É o sistema de busca padrão. Ele funciona como um índice super inteligente que encontra os trechos dos documentos que mais se parecem com a sua pergunta e os entrega para a Inteligência Artificial analisar.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <Card 
                      title="Quantidade de Trechos (Top K)" 
                      desc="Define quantos pedaços de texto a IA deve ler antes de te responder. Mais trechos dão mais 'bagagem' para a resposta, mas muitos trechos podem poluir o resultado." 
                    />
                    <Card 
                      title="Nível de Exigência (Threshold)" 
                      desc="O quão parecido o documento deve ser para ser usado. Um nível alto traz só o que é certeiro; um nível baixo permite que a IA tente ajudar mesmo que a informação seja apenas parecida." 
                    />
                    <Card 
                      title="Refinamento (Reranking)" 
                      desc="Uma segunda camada de inteligência que organiza os textos encontrados para garantir que a informação mais importante esteja sempre no topo." 
                    />
                  </div>
                </>
              )}
            </div>
            
            <div className="p-4 border-t bg-gray-50 flex justify-end">
              <button 
                onClick={() => setIsHelpModalOpen(false)}
                className="px-6 py-2 bg-accent-blue hover:bg-accent-blue-hover text-white rounded-lg font-medium transition-colors"
              >
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Card({ title, desc }: { title: string, desc: string }) {
  return (
    <div className="p-4 border border-gray-100 rounded-lg hover:border-accent-blue/30 hover:bg-accent-blue/5 transition-all group">
      <h5 className="font-bold text-gray-900 mb-1 group-hover:text-accent-blue transition-colors">{title}</h5>
      <p className="text-xs text-gray-600 leading-relaxed">{desc}</p>
    </div>
  );
}
