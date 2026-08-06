import { MessageSquarePlus, Trash2, Settings, History, Plus, ArrowLeft, HelpCircle, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Pencil, Check, Share2, BookOpen, NotebookText } from 'lucide-react';
import Image from 'next/image';
import { useState, useEffect, useRef, type MouseEvent } from 'react';
import { cn } from '@/lib/utils';
import { SidebarMode } from '@/app/page';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

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
  onRenameConversation: (id: number, title: string) => void;
  onShareConversation: (id: number) => void;
  selectedConversationId: number | null;
  conversations: any[];
  isBackendConnected?: boolean | null;
  lightragStatus?: "online" | "offline" | null;
  config: any;
  setConfig: (v: any) => void;
}

// Classes compartilhadas para os SelectTrigger no fundo escuro da sidebar.
const darkSelectTrigger =
  "w-full bg-sidebar-hover border-none text-gray-200 text-xs rounded p-2 h-auto shadow-none focus-visible:ring-1 focus-visible:ring-accent-blue [&_svg]:text-gray-400";

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
  onRenameConversation,
  onShareConversation,
  selectedConversationId,
  conversations,
  isBackendConnected,
  lightragStatus,
  config,
  setConfig
}: SidebarProps) {
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);
  // Manual de uso (botão de livro): instruções amigáveis de como usar o chat.
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  // Lista de recursos do modal "Como utilizar": RECOLHIDA por padrão. O objetivo do
  // modal é caber inteiro na tela, sem barra de rolagem — a lista é o bloco mais alto,
  // então fica atrás do botão do caderninho e só aparece sob demanda.
  const [showRecursos, setShowRecursos] = useState(false);
  // Fecha o modal SEMPRE recolhendo a lista — se reabrisse expandida, o modal voltaria
  // a ter barra de rolagem no segundo acesso.
  const closeManual = () => {
    setIsManualModalOpen(false);
    setShowRecursos(false);
  };
  const [ollamaModels, setOllamaModels] = useState<{name: string, label: string}[]>([]);

  // Renomear conversa (edição inline): id em edição + rascunho do título. O ref evita
  // commit duplo — ao apertar Enter, o input desmonta e dispara onBlur logo em seguida.
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const renameFinishing = useRef(false);
  // Quando a edição termina por TECLADO (Enter/Escape), devolvemos o foco ao lápis
  // daquela linha para o usuário não ser jogado ao <body>. Fica null em fim por
  // mouse/blur (aí o foco deve ir para onde o usuário clicou, não voltar ao lápis).
  const refocusRenameId = useRef<number | null>(null);

  // Após a edição fechar, se veio do teclado, devolve o foco ao lápis da linha
  // (o botão só volta a existir depois do re-render, daí o rAF).
  useEffect(() => {
    if (editingId !== null || refocusRenameId.current === null) return;
    const id = refocusRenameId.current;
    refocusRenameId.current = null;
    requestAnimationFrame(() => {
      document.querySelector<HTMLButtonElement>(`[data-rename-id="${id}"]`)?.focus();
    });
  }, [editingId]);

  const startRename = (id: number, currentTitle: string) => {
    setEditingId(id);
    setEditingTitle(currentTitle);
    renameFinishing.current = false;
  };

  const commitRename = (id: number, originalTitle: string) => {
    if (renameFinishing.current) return;
    renameFinishing.current = true;
    const title = editingTitle.trim();
    setEditingId(null);
    // Só chama a API se o título mudou de fato (e não ficou vazio).
    if (title && title !== originalTitle) onRenameConversation(id, title);
  };

  const cancelRename = () => {
    renameFinishing.current = true;
    setEditingId(null);
  };

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

  // Indicador de conexão do rodapé. Precedência: se o próprio backend não responde,
  // nada do RAG importa ("Sem conexão"); com backend no ar, refletimos o LightRAG.
  // Verde = online; laranja (pulsando) = offline/sem conexão; cinza = ainda verificando.
  // `neutral` = estado informativo (verificando): texto cinza, não laranja de alerta.
  const connection =
    isBackendConnected === false
      ? { color: "bg-accent-orange", pulse: true, online: false, neutral: false, label: "Sem conexão", title: "Sem conexão com o servidor" }
      : lightragStatus === "online"
        ? { color: "bg-fai-green", pulse: false, online: true, neutral: false, label: "Online", title: "Base de conhecimento (LightRAG) conectada" }
        : lightragStatus === "offline"
          ? { color: "bg-accent-orange", pulse: true, online: false, neutral: false, label: "Base offline", title: "Servidor de RAG (LightRAG) indisponível" }
          : { color: "bg-gray-500", pulse: true, online: false, neutral: true, label: "Verificando…", title: "Verificando conexão…" };

  return (
    <>
      <aside className={cn(
        "bg-sidebar-dark flex flex-col text-gray-300 h-full transition-all duration-300 ease-in-out z-20",
        isCollapsed ? "w-16" : "w-64"
      )}>

        {/* Topo: marca FAI-UFSCar + minimizar/expandir (estilo ChatGPT) */}
        {isCollapsed ? (
          <div className="flex h-14 shrink-0 items-center justify-center border-b border-sidebar-hover/60 px-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  onClick={() => setIsCollapsed(false)}
                  className="group relative flex size-9 items-center justify-center rounded-md transition-colors hover:bg-sidebar-hover"
                  aria-label="Expandir menu"
                >
                  <Image
                    src="/fai-icone.png"
                    alt="FAI • UFSCar"
                    width={24}
                    height={24}
                    className="object-contain transition-opacity group-hover:opacity-0"
                  />
                  <ChevronRight size={18} className="absolute text-gray-200 opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">Expandir menu</TooltipContent>
            </Tooltip>
          </div>
        ) : (
          <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-sidebar-hover/60 px-3">
            <Image
              src="/fai-icone.png"
              alt="FAI • UFSCar"
              width={26}
              height={26}
              className="shrink-0 object-contain"
            />
            <span className="text-[15px] font-semibold tracking-tight text-white">
              FAI <span className="font-light text-gray-300">• UFSCar</span>
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setIsCollapsed(true)}
                  className="ml-auto text-gray-400 hover:bg-sidebar-hover hover:text-white"
                  aria-label="Minimizar menu"
                >
                  <ChevronLeft size={18} />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Minimizar menu</TooltipContent>
            </Tooltip>
          </div>
        )}

        {mode === "history" ? (
          <>
            {/* Top Actions */}
            <div className="p-3 space-y-2 border-b border-sidebar-hover">
              <Button
                onClick={onNewChat}
                title="Nova Conversa"
                className={cn(
                  "w-full flex items-center bg-accent-blue hover:bg-accent-blue-hover text-white rounded font-medium transition-all duration-200 h-auto",
                  isCollapsed ? "justify-center p-2" : "gap-2 py-2 px-3 text-sm"
                )}
              >
                {isCollapsed ? <Plus size={20} /> : <><MessageSquarePlus size={18} /> Nova Conversa</>}
              </Button>

              <Button
                onClick={onOpenSettings}
                title="Configurações"
                className={cn(
                  "w-full flex items-center bg-sidebar-hover hover:bg-gray-700 text-white rounded transition-all duration-200 border border-gray-600 h-auto",
                  isCollapsed ? "justify-center p-2" : "gap-2 py-2 px-3 text-sm"
                )}
              >
                <Settings size={isCollapsed ? 20 : 18} />
                {!isCollapsed && <span>Configurações</span>}
              </Button>

              <Button
                onClick={() => setIsManualModalOpen(true)}
                title="Como utilizar o chat"
                className={cn(
                  "w-full flex items-center bg-sidebar-hover hover:bg-gray-700 text-white rounded transition-all duration-200 border border-gray-600 h-auto",
                  isCollapsed ? "justify-center p-2" : "gap-2 py-2 px-3 text-sm"
                )}
              >
                <BookOpen size={isCollapsed ? 20 : 18} />
                {!isCollapsed && <span>Como utilizar</span>}
              </Button>

              {!isCollapsed && (
                <Button
                  variant="ghost"
                  onClick={onClearHistory}
                  className="w-full flex items-center justify-start gap-2 text-gray-400 hover:text-accent-orange hover:bg-transparent text-xs py-1 px-0 h-auto font-normal transition-colors group"
                >
                  <Trash2 size={14} className="group-hover:text-accent-orange" />
                  Limpar histórico
                </Button>
              )}
            </div>

            {/* History List */}
            <ScrollArea className="flex-1 px-2 py-4">
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
                    {conversations.map((conv) => {
                      const isEditing = editingId === conv.id;
                      return (
                      <div
                        key={conv.id}
                        className={cn(
                          "group flex items-center gap-1 rounded transition-colors pr-1",
                          selectedConversationId === conv.id ? "bg-sidebar-hover text-white shadow-sm" : "hover:bg-sidebar-hover/50"
                        )}
                      >
                        {isEditing ? (
                          <>
                            <input
                              autoFocus
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onFocus={(e) => e.target.select()}
                              onKeyDown={(e) => {
                                // Fim por teclado: marca a linha p/ devolver o foco ao lápis.
                                if (e.key === "Enter") { e.preventDefault(); refocusRenameId.current = conv.id; commitRename(conv.id, conv.title); }
                                else if (e.key === "Escape") { e.preventDefault(); refocusRenameId.current = conv.id; cancelRename(); }
                              }}
                              onBlur={() => commitRename(conv.id, conv.title)}
                              maxLength={200}
                              className="flex-1 min-w-0 rounded bg-sidebar-dark px-3 py-2 text-sm max-lg:text-base text-white outline-none ring-1 ring-accent-blue"
                              aria-label="Novo título da conversa"
                            />
                            <Button
                              variant="ghost"
                              size="icon-xs"
                              // onMouseDown (não onClick): dispara ANTES do onBlur do input,
                              // então o commit acontece com o botão ainda montado.
                              onMouseDown={(e: MouseEvent<HTMLButtonElement>) => {
                                e.preventDefault();
                                commitRename(conv.id, conv.title);
                              }}
                              className="text-gray-400 hover:text-fai-green hover:bg-transparent"
                              title="Salvar"
                              aria-label="Salvar título"
                            >
                              <Check size={14} />
                            </Button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => onSelectConversation(conv.id)}
                              className="flex-1 min-w-0 text-left px-3 py-2 text-sm truncate"
                              title={conv.title}
                            >
                              {conv.title}
                            </button>

                            <Button
                              variant="ghost"
                              size="icon-xs"
                              data-rename-id={conv.id}
                              onClick={(e: MouseEvent<HTMLButtonElement>) => {
                                e.stopPropagation();
                                startRename(conv.id, conv.title);
                              }}
                              // SEMPRE visível (discreto, realça no hover): so-no-hover deixava
                              // o ícone invisível até passar o mouse e inacessível no toque.
                              className="text-gray-400 hover:text-accent-blue hover:bg-transparent transition-colors"
                              title="Renomear conversa"
                              aria-label={`Renomear conversa: ${conv.title}`}
                            >
                              <Pencil size={13} />
                            </Button>

                            <Button
                              variant="ghost"
                              size="icon-xs"
                              onClick={(e: MouseEvent<HTMLButtonElement>) => {
                                e.stopPropagation();
                                onShareConversation(conv.id);
                              }}
                              className="text-gray-400 hover:text-fai-green hover:bg-transparent transition-colors"
                              title="Compartilhar conversa"
                              aria-label={`Compartilhar conversa: ${conv.title}`}
                            >
                              <Share2 size={13} />
                            </Button>

                            <Button
                              variant="ghost"
                              size="icon-xs"
                              onClick={(e: MouseEvent<HTMLButtonElement>) => {
                                e.stopPropagation();
                                onDeleteConversation(conv.id);
                              }}
                              className="text-gray-400 hover:text-accent-orange hover:bg-transparent transition-colors"
                              title="Excluir conversa"
                              aria-label={`Excluir conversa: ${conv.title}`}
                            >
                              <Trash2 size={13} />
                            </Button>
                          </>
                        )}
                      </div>
                      );
                    })}
                  </div>
                )
              )}
            </ScrollArea>
          </>
        ) : (
          /* Settings View */
          <div className="flex flex-col h-full overflow-hidden">
            <div className="p-4 border-b border-sidebar-hover flex items-center justify-between">
               <div className="flex items-center gap-3">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={() => setMode("history")}
                    className="text-gray-300 hover:text-white hover:bg-sidebar-hover"
                    title="Voltar ao Histórico"
                    aria-label="Voltar ao Histórico"
                  >
                      <ArrowLeft size={18} />
                  </Button>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">Configurações</h2>
               </div>
               <Tooltip>
                 <TooltipTrigger asChild>
                   <Button
                     variant="ghost"
                     size="icon-sm"
                     onClick={() => setIsHelpModalOpen(true)}
                     className="text-gray-500 hover:text-accent-blue hover:bg-sidebar-hover"
                     title="Ajuda sobre o Motor"
                     aria-label="Ajuda sobre o Motor"
                   >
                     <HelpCircle size={20} />
                   </Button>
                 </TooltipTrigger>
                 <TooltipContent side="bottom">Ajuda sobre o Motor</TooltipContent>
               </Tooltip>
            </div>

            <ScrollArea className="flex-1">
             <div className="p-4 space-y-6">
               {/* Motor RAG */}
               <div className="space-y-2">
                 <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Motor de RAG</label>
                 <Select
                  value={config.ragEngine}
                  onValueChange={(value) => handleConfigChange("ragEngine", value)}
                 >
                   <SelectTrigger className={darkSelectTrigger}>
                     <SelectValue />
                   </SelectTrigger>
                   <SelectContent>
                     <SelectItem value="LightRAG (Grafo)">LightRAG (Grafo)</SelectItem>
                   </SelectContent>
                 </Select>
               </div>

               {config.ragEngine === "LightRAG (Grafo)" ? (
                  /* LightRAG Specific Mode */
                  <div className="space-y-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Modo LightRAG</label>
                      <Select
                        value={config.lightragMode}
                        onValueChange={(value) => handleConfigChange("lightragMode", value)}
                      >
                        <SelectTrigger className={darkSelectTrigger}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="hybrid">hybrid (Local + Global)</SelectItem>
                          <SelectItem value="mix">mix (Grafo + Vetorial)</SelectItem>
                          <SelectItem value="local">local (Específico)</SelectItem>
                          <SelectItem value="global">global (Geral)</SelectItem>
                          <SelectItem value="naive">naive (Vetorial Simples)</SelectItem>
                        </SelectContent>
                      </Select>
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
                      <Select
                        value={config.provider}
                        onValueChange={(value) => handleConfigChange("provider", value)}
                      >
                        <SelectTrigger className={darkSelectTrigger}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="OpenAI API">OpenAI API</SelectItem>
                          <SelectItem value="Google Gemini">Google Gemini</SelectItem>
                          <SelectItem value="Ollama local">Ollama local</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Modelo */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Modelo</label>
                      {config.provider === "OpenAI API" ? (
                        <Select
                          value={config.model}
                          onValueChange={(value) => handleConfigChange("model", value)}
                        >
                          <SelectTrigger className={darkSelectTrigger}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="gpt-4o-mini">gpt-4o-mini</SelectItem>
                            <SelectItem value="gpt-4o">gpt-4o</SelectItem>
                            <SelectItem value="gpt-4-turbo">gpt-4-turbo</SelectItem>
                            <SelectItem value="gpt-3.5-turbo">gpt-3.5-turbo</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : config.provider === "Google Gemini" ? (
                        <Select
                          value={config.model}
                          onValueChange={(value) => handleConfigChange("model", value)}
                        >
                          <SelectTrigger className={darkSelectTrigger}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="gemini-1.5-flash">gemini-1.5-flash</SelectItem>
                            <SelectItem value="gemini-1.5-pro">gemini-1.5-pro</SelectItem>
                            <SelectItem value="gemini-1.0-pro">gemini-1.0-pro</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : (
                        ollamaModels.length > 0 ? (
                          <Select
                            value={config.model}
                            onValueChange={(value) => handleConfigChange("model", value)}
                          >
                            <SelectTrigger className={darkSelectTrigger}>
                              <SelectValue placeholder="Selecione um modelo local" />
                            </SelectTrigger>
                            <SelectContent>
                              {ollamaModels.map((m) => (
                                <SelectItem key={m.name} value={m.name}>{m.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : (
                          <Input
                            type="text"
                            value={config.model}
                            onChange={(e) => handleConfigChange("model", e.target.value)}
                            placeholder="Digitando ou conectando Ollama..."
                            className="bg-sidebar-hover border-none text-gray-200 text-xs max-lg:text-base rounded p-2 h-auto shadow-none placeholder:text-gray-500 focus-visible:ring-1 focus-visible:ring-accent-blue"
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
            </ScrollArea>
          </div>
        )}

        {/* Rodapé: status de conexão — bolinha verde (online) / laranja (offline). */}
        <div className="mt-auto shrink-0 border-t border-sidebar-hover p-3 text-center">
          <div
            className={cn(
              "flex items-center justify-center gap-1.5 text-[10px] font-medium",
              connection.online || connection.neutral ? "text-gray-400" : "text-accent-orange"
            )}
            title={connection.title}
          >
            <span
              className={cn(
                "size-2 shrink-0 rounded-full",
                connection.color,
                connection.pulse && "animate-pulse"
              )}
            />
            {!isCollapsed && <span>{connection.label}</span>}
          </div>
        </div>
      </aside>

      {/* Unified Help Modal */}
      <Dialog open={isHelpModalOpen} onOpenChange={setIsHelpModalOpen}>
        <DialogContent className="max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col gap-0 p-0">
          <DialogHeader className="p-6 border-b bg-gray-50 text-left">
            <div className="flex items-center gap-3">
              <HelpCircle className="text-accent-blue shrink-0" size={24} />
              <DialogTitle className="text-xl font-bold text-gray-900">
                {config.ragEngine === "LightRAG (Grafo)" ? "Entendendo o LightRAG" : "Entendendo o Motor Supabase"}
              </DialogTitle>
            </div>
          </DialogHeader>

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
                  <HelpCard title="Hybrid" desc="O equilíbrio perfeito: responde bem tanto perguntas diretas quanto dúvidas mais amplas (Resumo + Detalhes)." />
                  <HelpCard title="Mix" desc="Uma mistura entre a inteligência de conexões e a busca rápida por palavras-chave." />
                  <HelpCard title="Local" desc="Especialista em detalhes: ideal para buscar informações sobre um ponto muito específico ou uma pessoa citada." />
                  <HelpCard title="Global" desc="Visão panorâmica: ideal para entender temas gerais, tendências ou o 'quadro geral' dos seus documentos." />
                  <HelpCard title="Naive" desc="Busca simples e direta baseada apenas na semelhança das palavras, sem olhar as conexões entre elas." />
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
                  <HelpCard
                    title="Quantidade de Trechos (Top K)"
                    desc="Define quantos pedaços de texto a IA deve ler antes de te responder. Mais trechos dão mais 'bagagem' para a resposta, mas muitos trechos podem poluir o resultado."
                  />
                  <HelpCard
                    title="Nível de Exigência (Threshold)"
                    desc="O quão parecido o documento deve ser para ser usado. Um nível alto traz só o que é certeiro; um nível baixo permite que a IA tente ajudar mesmo que a informação seja apenas parecida."
                  />
                  <HelpCard
                    title="Refinamento (Reranking)"
                    desc="Uma segunda camada de inteligência que organiza os textos encontrados para garantir que a informação mais importante esteja sempre no topo."
                  />
                </div>
              </>
            )}
          </div>

          <DialogFooter className="p-4 border-t bg-gray-50 sm:justify-end">
            <Button
              onClick={() => setIsHelpModalOpen(false)}
              className="px-6 py-2 bg-accent-blue hover:bg-accent-blue-hover text-white rounded-lg font-medium transition-colors h-auto"
            >
              Entendido
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual de uso: instruções amigáveis de como usar o chat (botão de livro). */}
      {/* closeManual em vez de setIsManualModalOpen direto: o botão "Entendido" fecha
          por estado e NÃO passa pelo onOpenChange do Radix, então o reset da lista
          precisa estar num handler único usado pelos dois caminhos de fechamento. */}
      <Dialog
        open={isManualModalOpen}
        onOpenChange={(open) => (open ? setIsManualModalOpen(true) : closeManual())}
      >
        {/* max-h 85vh -> 90vh e o conteúdo com espaçamento menor: com a lista recolhida
            o modal precisa caber SEM rolagem também em telas baixas (~700px), onde os
            85vh deixavam o conteúdo 28px maior que a área útil. */}
        <DialogContent className="max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col gap-0 p-0">
          <DialogHeader className="p-4 border-b bg-gray-50 text-center">
            <div className="flex items-center justify-center gap-3">
              <BookOpen className="text-accent-blue shrink-0" size={24} />
              <DialogTitle className="text-xl font-bold text-gray-900">
                Como utilizar o chat
              </DialogTitle>
            </div>
          </DialogHeader>

          {/* Registro FORMAL CORDIAL (2026-07-27): mantém o tratamento direto e a persona
              Lina, sem exclamações nem coloquialismos. Emojis são PONTUAIS por decisão do
              usuário ("pode conter emotes, sem exageros"): um por título de seção, como
              âncora visual — não no texto corrido nem nos itens da lista, que usam
              marcadores normais. Títulos e texto corrido centralizados; a LISTA fica
              alinhada à esquerda — item centralizado perde a margem de retorno da vista. */}
          <div className="flex-1 overflow-y-auto p-5 space-y-3">
            {/* Bloco de apresentação REMOVIDO em 2026-07-27 (pedido do usuário): a
                persona já se apresenta na tela de boas-vindas, e repetir isso aqui só
                atrasava o acesso às orientações, que é o objetivo do modal. */}

            {/* Funcionalidades — recolhidas atrás do "caderninho" para o modal caber
                sem barra de rolagem. Volta ao estado fechado sempre que o modal fecha. */}
            <div>
              <button
                type="button"
                onClick={() => setShowRecursos((v) => !v)}
                aria-expanded={showRecursos}
                aria-controls="manual-recursos"
                className="mx-auto flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-bold text-gray-900 transition-colors hover:border-accent-blue/40 hover:bg-accent-blue/5"
              >
                <NotebookText size={16} className="text-accent-blue shrink-0" />
                Recursos disponíveis
                {showRecursos
                  ? <ChevronUp size={14} className="text-gray-500" />
                  : <ChevronDown size={14} className="text-gray-500" />}
              </button>
              {showRecursos && (
                <ul id="manual-recursos" className="mt-3 space-y-1.5 text-sm text-gray-700 leading-relaxed list-disc pl-5">
                  <li><strong>Consultas por texto:</strong> digite sua dúvida no campo de mensagem e envie.</li>
                  <li><strong>Consultas por voz:</strong> utilize o microfone para ditar a pergunta.</li>
                  <li><strong>Verificação das fontes:</strong> cada resposta indica a página do manual de onde a informação foi extraída, no painel lateral, e o documento pode ser baixado.</li>
                  <li><strong>Gestão das conversas:</strong> renomeie, compartilhe por link ou exporte em PDF.</li>
                  <li><strong>Histórico:</strong> as conversas ficam registradas na barra lateral.</li>
                </ul>
              )}
            </div>

            {/* Formulação da consulta */}
            <div className="p-4 bg-green-50 border border-green-100 rounded-lg">
              <h4 className="font-bold text-green-900 mb-1 text-center">💡 Dica de Pergunta</h4>
              <p className="text-sm text-green-800 leading-relaxed">
                Capriche na pergunta! Quanto mais objetiva e específica ela for, melhor
                será a minha resposta.
              </p>
              <p className="text-sm text-green-800 leading-relaxed mt-2">
                👉 Em vez de: <em>“E a compra?”</em>
                <br />
                👉 Prefira: <em>“Como crio uma solicitação de compra no sistema?”</em>
              </p>
            </div>

            {/* Escopo: geral vs. projeto específico */}
            <div className="p-4 bg-amber-50 border border-amber-100 rounded-lg">
              <h4 className="font-bold text-amber-900 mb-1 text-center">📌 Escopo de Atendimento</h4>
              <p className="text-sm font-medium text-amber-900">O que posso responder?</p>
              <p className="text-sm text-amber-800 leading-relaxed mt-1">
                Conheço os procedimentos de gestão dos projetos da FAI•UFSCar, mas não tenho
                acesso a dados específicos de um determinado projeto. Para consultar saldos,
                status ou etapas de um projeto específico, recomendo que entre em contato
                diretamente com o <strong>Gestor de seu Projeto</strong>.
              </p>
            </div>
          </div>

          <DialogFooter className="p-3 border-t bg-gray-50 sm:justify-end">
            <Button
              onClick={closeManual}
              className="px-6 py-2 bg-accent-blue hover:bg-accent-blue-hover text-white rounded-lg font-medium transition-colors h-auto"
            >
              Entendido
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function HelpCard({ title, desc }: { title: string, desc: string }) {
  return (
    <Card className="p-4 gap-1 rounded-lg border-gray-100 shadow-none hover:border-accent-blue/30 hover:bg-accent-blue/5 transition-all group">
      <CardHeader className="p-0 gap-0">
        <CardTitle className="font-bold text-gray-900 group-hover:text-accent-blue transition-colors">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <p className="text-xs text-gray-600 leading-relaxed">{desc}</p>
      </CardContent>
    </Card>
  );
}
