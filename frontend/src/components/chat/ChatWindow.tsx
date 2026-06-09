"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Mic, Plus, Image, FileText, X, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  genTime?: number;
  usage?: number;
}

interface ChatWindowProps {
  config: any;
  userId: string | null;
  selectedConversationId: number | null;
  onConversationCreated: () => void;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.top = "0";
        textarea.style.left = "0";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        const successful = document.execCommand("copy");
        document.body.removeChild(textarea);
        if (!successful) {
          throw new Error("execCommand copy failed");
        }
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Erro ao copiar texto: ", err);
    }
  };

  return (
    <button
      onClick={handleCopy}
      className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium transition-all duration-200 border shrink-0 ${
        copied
          ? "bg-green-50 text-green-600 border-green-200"
          : "bg-gray-50/50 text-gray-500 border-gray-200/60 hover:bg-gray-100 hover:text-gray-700"
      }`}
      title="Copiar mensagem"
    >
      {copied ? (
        <>
          <Check size={11} className="stroke-[2.5]" />
          <span>Copiado!</span>
        </>
      ) : (
        <>
          <Copy size={11} />
          <span>Copiar</span>
        </>
      )}
    </button>
  );
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function ChatWindow({ config, userId, selectedConversationId, onConversationCreated }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Olá! Como posso ajudar você hoje com os documentos da FAI-Ufscar?" }
  ]);
  const [input, setInput] = useState("");
  const [showAttachments, setShowAttachments] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const attachmentRef = useRef<HTMLDivElement>(null);

  // Sync internal conversationId with prop and fetch messages if needed
  useEffect(() => {
    setConversationId(selectedConversationId);
    
    if (selectedConversationId) {
      const fetchMessages = async () => {
        setIsTyping(true);
        try {
          const response = await fetch(`${API_BASE_URL}/history/${selectedConversationId}/messages?user_id=${encodeURIComponent(userId ?? "")}`);
          if (response.ok) {
            const data = await response.json();
            // Map backend messages to frontend format
            setMessages(data.map((m: any) => ({
              role: m.role,
              content: m.content,
              sources: m.metadata?.sources,
              genTime: m.metadata?.gen_time,
              usage: m.metadata?.usage
            })));
          }
        } catch (e) {
          console.error("Erro ao carregar mensagens", e);
        } finally {
          setIsTyping(false);
        }
      };
      fetchMessages();
    } else {
      // Reset for new chat
      setMessages([{ role: "assistant", content: "Olá! Como posso ajudar você hoje com os documentos da FAI-Ufscar?" }]);
    }
  }, [selectedConversationId]);

  // Close attachments menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (attachmentRef.current && !attachmentRef.current.contains(event.target as Node)) {
        setShowAttachments(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;
    
    const userMessage = input.trim();
    setInput("");
    setShowAttachments(false);
    setIsTyping(true);

    // Add user message to UI
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);

    // Prepare assistant placeholder message
    setMessages(prev => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: userMessage,
          conversation_id: conversationId,
          user_id: userId ?? "guest",
          rag_engine: config.ragEngine,
          mode: config.lightragMode,
          provider: config.provider,
          model: config.model,
          top_k: config.topK,
          reranker_threshold: config.threshold
        }),
      });

      if (!response.ok) throw new Error("Erro na comunicação com o servidor.");

      const reader = response.body?.getReader();
      if (!reader) throw new Error("Stream não disponível.");

      const decoder = new TextDecoder();
      let lastMessageContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.error) {
                lastMessageContent = `Erro: ${data.error}`;
              } else if (data.content) {
                lastMessageContent += data.content;
              }

              // Update the last assistant message in real-time
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsgIndex = newMessages.length - 1;
                newMessages[lastMsgIndex] = { 
                  ...newMessages[lastMsgIndex], 
                  content: lastMessageContent,
                  sources: data.sources || newMessages[lastMsgIndex].sources,
                  genTime: data.gen_time || newMessages[lastMsgIndex].genTime,
                  usage: data.usage || newMessages[lastMsgIndex].usage
                };
                
                // If the stream is finished, set the final conversation ID
                if (data.done) {
                  if (!conversationId && data.conversation_id) {
                    onConversationCreated();
                  }
                  setConversationId(data.conversation_id);
                }
                
                return newMessages;
              });

            } catch (e) {
              console.error("Erro ao parsear chunk JSON", e);
            }
          }
        }
      }

    } catch (error: any) {
      console.error("Erro no chat:", error);
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = `Desculpe, ocorreu um erro de conexão: ${error.message}`;
        return newMessages;
      });
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50/30">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((m, idx) => (
          <div key={idx} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : ''}`}>
            {m.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-header-blue flex items-center justify-center text-white shrink-0 shadow-sm">
                <Bot size={18} />
              </div>
            )}
            
            <div className={`max-w-[85%] flex flex-col gap-2 ${m.role === 'user' ? 'items-end' : ''}`}>
              <div className={`rounded-2xl px-4 py-2 shadow-sm ${
                m.role === 'user' 
                  ? 'bg-accent-blue text-white rounded-tr-none' 
                  : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none'
              }`}>
                <div className={`prose prose-sm max-w-none prose-p:leading-relaxed ${
                  m.role === 'user'
                    ? 'prose-invert prose-p:text-white prose-headings:text-white prose-a:text-blue-200'
                    : 'prose-gray'
                }`}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {m.content || (isTyping && idx === messages.length - 1 ? "..." : "")}
                  </ReactMarkdown>
                </div>
              </div>

              {/* Botões de Cópia e Metadados/Fontes */}
              {m.role === 'user' && m.content && (
                <div className="px-1 flex justify-end">
                  <CopyButton text={m.content} />
                </div>
              )}

              {m.role === 'assistant' && m.content && (
                <div className="px-1 space-y-2">
                  <div className="flex items-center gap-3">
                    <CopyButton text={m.content} />
                    {m.genTime && (
                      <div className="text-[9px] text-gray-400 italic">
                        Resposta gerada em {m.genTime.toFixed(2)}s
                      </div>
                    )}
                  </div>
                  {m.sources && m.sources.length > 0 && (
                    <div className="space-y-2 animate-in fade-in duration-500 mt-1">
                      <div className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                        <FileText size={10} /> Fontes Pesquisadas
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {m.sources.map((s, i) => (
                          <div key={i} className="text-[10px] bg-gray-100 border border-gray-200 text-gray-600 px-2 py-1 rounded transition-colors hover:bg-gray-200">
                            {s.replace("- ", "").split(",")[0]}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {m.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-gray-500 shrink-0 shadow-sm">
                <User size={18} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-gray-100 shadow-[0_-4px_10px_rgba(0,0,0,0.02)]">
        <div className="max-w-4xl mx-auto flex gap-3 items-end relative">
          
          {/* Attachments Dropdown */}
          <div ref={attachmentRef} className="relative">
            {showAttachments && (
              <div className="absolute bottom-full left-0 mb-4 bg-white border border-gray-100 rounded-2xl shadow-2xl p-2 min-w-[200px] animate-in fade-in slide-in-from-bottom-4 duration-300 z-50">
                <div className="text-[10px] font-bold text-gray-400 px-3 py-2 uppercase tracking-wider">Enviar para o Chat</div>
                <button className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 rounded-xl text-sm text-gray-700 transition-colors group">
                  <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center group-hover:bg-blue-100 transition-colors">
                    <FileText size={18} className="text-blue-500" />
                  </div>
                  <span>Anexar Arquivo</span>
                </button>
                <button className="w-full flex items-center gap-3 p-3 hover:bg-gray-50 rounded-xl text-sm text-gray-700 transition-colors group">
                  <div className="w-8 h-8 bg-purple-50 rounded-lg flex items-center justify-center group-hover:bg-purple-100 transition-colors">
                    <Image size={18} className="text-purple-500" />
                  </div>
                  <span>Anexar Imagem</span>
                </button>
              </div>
            )}
            <button 
              onClick={() => setShowAttachments(!showAttachments)}
              className={`p-2.5 rounded-full transition-all duration-300 ${
                showAttachments ? 'bg-gray-100 text-gray-600 rotate-45' : 'bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-accent-blue'
              }`}
            >
              <Plus size={22} />
            </button>
          </div>

          {/* Main Input Field */}
          <div className="flex-1 flex gap-2 items-center bg-gray-50 rounded-[24px] px-4 py-1.5 border border-gray-200 focus-within:border-accent-blue focus-within:bg-white focus-within:shadow-md transition-all">
            <input 
              type="text" 
              placeholder="Digite sua dúvida aqui..."
              className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-2"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              disabled={isTyping}
            />
            <button 
              className="text-gray-400 hover:text-accent-blue p-2 transition-colors disabled:opacity-30"
              title="Gravação de voz (em breve)"
              disabled={isTyping}
            >
              <Mic size={20} />
            </button>
          </div>

          {/* Send Button */}
          <button 
            onClick={handleSend}
            className="bg-accent-blue hover:bg-accent-blue-hover text-white p-3 rounded-full shadow-lg shadow-accent-blue/20 transition-all active:scale-95 disabled:opacity-50 disabled:grayscale disabled:shadow-none"
            disabled={!input.trim() || isTyping}
          >
            <Send size={20} />
          </button>
        </div>
        <p className="text-[10px] text-gray-400 text-center mt-3">
          O chatbot pode cometer erros. Considere verificar as fontes citadas.
        </p>
      </div>
    </div>
  );
}
