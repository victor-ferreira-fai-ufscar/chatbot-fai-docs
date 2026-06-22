"use client";

import { useState, useRef, useEffect } from "react";
import { Send, User, Mic, Square, Loader2, Plus, Image, FileText, X, Copy, Check, Download, Reply, ArrowDown } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

interface QuotedRef {
  role: "user" | "assistant";
  content: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  genTime?: number;
  usage?: number;
  quoted?: QuotedRef;
}

interface ChatWindowProps {
  config: any;
  userId: string | null;
  selectedConversationId: number | null;
  onConversationCreated: () => void;
  // Notifica o pai (page.tsx) das fontes da resposta atual, para alimentar a SourcesPanel.
  onActiveSources?: (sources: string[], answer: string) => void;
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
    <Button
      type="button"
      variant="outline"
      size="xs"
      onClick={handleCopy}
      title="Copiar mensagem"
      className={cn(
        "text-[10px] shrink-0",
        copied
          ? "border-fai-green/30 bg-fai-green/10 text-fai-green hover:bg-fai-green/10 hover:text-fai-green"
          : "text-muted-foreground"
      )}
    >
      {copied ? (
        <>
          <Check className="stroke-[2.5]" />
          <span>Copiado!</span>
        </>
      ) : (
        <>
          <Copy />
          <span>Copiar</span>
        </>
      )}
    </Button>
  );
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// Extrai o nome do arquivo de uma linha de fonte. Tolera o formato atual
// ("- arquivo.pdf (pág. 12)" / "(págs. 4-6, 9)") e o legado ("(Ref ID: 123)").
function extractFilename(sourceLine: string): string {
  return sourceLine
    .replace(/^-\s*/, "")
    .replace(/\s*\((?:ref id:|p[áa]gs?\.).*\)\s*$/i, "")
    .trim();
}

// Rótulo de página de uma linha de fonte ("pág. 12" / "págs. 4-6, 9"), ou null.
function extractPagesLabel(sourceLine: string): string | null {
  const m = sourceLine.match(/\((p[áa]gs?\.[^)]*)\)/i);
  return m ? m[1].trim() : null;
}

// Primeira página citada na linha de fonte (para abrir o PDF direto nela), ou null.
function extractSourcePage(sourceLine: string): number | null {
  const m = sourceLine.match(/p[áa]gs?\.\s*(\d{1,4})/i);
  return m ? parseInt(m[1], 10) : null;
}

// Procura, no texto da resposta, a pagina citada para um arquivo no formato
// "[arquivo.pdf, pag. N]" (best-effort: usa o numero de rodape que o modelo citou).
// Retorna null quando nao ha citacao de pagina correspondente.
function extractCitedPage(answerContent: string, filename: string): number | null {
  if (!answerContent || !filename) return null;
  const target = filename.trim().toLowerCase();
  // Captura "[<arquivo> , pag. N]" tolerando virgula/traço e "pag"/"pág."
  const re = /\[([^\]]+?)[,\s-]+p[aá]g\.?\s*(\d{1,4})\]/gi;
  let firstPage: number | null = null;
  let match: RegExpExecArray | null;
  while ((match = re.exec(answerContent)) !== null) {
    const fileInCite = match[1].trim().toLowerCase();
    const page = parseInt(match[2], 10);
    if (Number.isNaN(page)) continue;
    if (firstPage === null) firstPage = page;
    // Match frouxo do nome (o modelo cita o arquivo como aparece nas fontes).
    if (fileInCite === target || fileInCite.includes(target) || target.includes(fileInCite)) {
      return page;
    }
  }
  // Sem match de nome: se houve alguma pagina citada, usa a primeira (geralmente
  // ha um unico documento em jogo). Caso contrario, sem pagina.
  return firstPage;
}

// Gera um trecho curto e limpo (sem marcações de markdown) de uma mensagem citada.
function quotePreview(text: string, max = 140): string {
  const clean = (text || "")
    .replace(/```[\s\S]*?```/g, " ")          // blocos de código
    .replace(/[#>*_`~\-]+/g, " ")              // símbolos de markdown
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")   // links -> só o texto
    .replace(/\s+/g, " ")
    .trim();
  return clean.length > max ? clean.slice(0, max).trimEnd() + "…" : clean;
}

// Bloco visual da mensagem citada (estilo "responder" do WhatsApp).
function QuotedBlock({ quoted, onUserBubble }: { quoted: QuotedRef; onUserBubble?: boolean }) {
  const label = quoted.role === "assistant" ? "Assistente" : "Você";
  return (
    <div
      className={cn(
        "mb-1.5 rounded-md border-l-[3px] px-2.5 py-1.5 text-[11px] leading-snug",
        onUserBubble
          ? "border-white/70 bg-white/15 text-white/90"
          : "border-accent-blue/60 bg-accent-blue/5 text-muted-foreground"
      )}
    >
      <div className={cn("font-semibold text-[10px] mb-0.5", onUserBubble ? "text-white/90" : "text-accent-blue")}>
        {label}
      </div>
      <div className="line-clamp-2 opacity-90">{quotePreview(quoted.content)}</div>
    </div>
  );
}

// Botão "Responder" (mencionar mensagem como contexto).
function ReplyButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      type="button"
      variant="outline"
      size="xs"
      onClick={onClick}
      title="Responder / mencionar esta mensagem"
      className="text-[10px] text-muted-foreground shrink-0"
    >
      <Reply />
      <span>Responder</span>
    </Button>
  );
}

export default function ChatWindow({ config, userId, selectedConversationId, onConversationCreated, onActiveSources }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [replyingTo, setReplyingTo] = useState<QuotedRef | null>(null);
  const [showAttachments, setShowAttachments] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const attachmentRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // Rastreia se o usuario esta perto do fim (para auto-seguir novas mensagens sem "puxar" quem rolou para cima).
  const atBottomRef = useRef(true);

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
              usage: m.metadata?.usage,
              quoted: m.metadata?.quoted
            })));
            // Alimenta a SourcesPanel com as fontes da ultima resposta da conversa carregada.
            const lastAsst = [...data].reverse().find((m: any) => m.role === "assistant" && m.metadata?.sources?.length);
            if (onActiveSources) onActiveSources(lastAsst?.metadata?.sources || [], lastAsst?.content || "");
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
      setMessages([]);
      if (onActiveSources) onActiveSources([], "");
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

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
  };

  // Detecta a distancia ate o fim: controla a visibilidade da setinha e o auto-seguir.
  const handleMessagesScroll = () => {
    const el = messagesContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    atBottomRef.current = distanceFromBottom < 80;
    setShowScrollToBottom(distanceFromBottom > 160);
  };

  // Ao chegarem novas mensagens (ou chunks de streaming), segue o fim apenas se o
  // usuario ja estava perto do fim — quem rolou para cima nao e "puxado".
  useEffect(() => {
    if (atBottomRef.current) {
      scrollToBottom("auto");
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isTyping) return;

    const userMessage = input.trim();
    const quoted = replyingTo;
    setInput("");
    setReplyingTo(null);
    setShowAttachments(false);
    setIsTyping(true);
    atBottomRef.current = true; // ao enviar, acompanha a resposta ate o fim

    // Add user message to UI (com a citação, se houver)
    setMessages(prev => [...prev, { role: "user", content: userMessage, quoted: quoted ?? undefined }]);

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
          quoted: quoted ?? null,
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
      // Buffer de SSE: uma leitura do stream pode terminar no MEIO de uma linha
      // "data: {...}". Sem acumular o resto, o JSON parcial falha no parse e o
      // pedaco seguinte (sem o prefixo "data: ") e descartado — perdendo
      // conteudo e ate o evento final "done". Modelos que emitem muitos chunks
      // minusculos (ex.: qwen3, ~900+ eventos por resposta) expoem isso o tempo
      // todo. Por isso so processamos linhas COMPLETAS e guardamos o resto.
      let sseBuffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // { stream: true } evita corromper caracteres multibyte (ç, ã, ú)
        // partidos entre duas leituras.
        sseBuffer += decoder.decode(value, { stream: true });
        const lines = sseBuffer.split('\n');
        sseBuffer = lines.pop() ?? ""; // mantem a ultima linha (possivelmente incompleta)

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

              // Ao finalizar a resposta, publica as fontes para a SourcesPanel (3a coluna).
              if (data.done && onActiveSources) {
                onActiveSources(data.sources || [], lastMessageContent);
              }

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

  // Envia o audio gravado ao backend (Whisper) e injeta a transcricao no input.
  const transcribeAudio = async (blob: Blob) => {
    setIsTranscribing(true);
    try {
      const formData = new FormData();
      formData.append("file", blob, "gravacao.webm");
      const res = await fetch(`${API_BASE_URL}/audio/transcribe`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || `Falha na transcrição (${res.status}).`);
      }
      const data = await res.json();
      const text = (data.text || "").trim();
      if (text) {
        // Acrescenta ao que ja estiver digitado (com espaco), sem sobrescrever.
        setInput((prev) => (prev ? `${prev} ${text}` : text));
      } else {
        toast.error("Não foi possível entender o áudio. Tente falar mais perto do microfone.");
      }
    } catch (e: any) {
      console.error("Erro ao transcrever áudio", e);
      toast.error(`Erro ao transcrever o áudio: ${e.message}`);
    } finally {
      setIsTranscribing(false);
    }
  };

  // Encerra a gravacao em andamento e libera o microfone.
  const stopRecording = () => {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    mediaStreamRef.current = null;
    setIsRecording(false);
  };

  // Inicia a captura de audio do microfone. Requer contexto seguro (HTTPS ou
  // localhost) — em HTTP por IP o navegador bloqueia o acesso ao microfone.
  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      toast.error(
        "O microfone só funciona em conexão segura (HTTPS) ou via localhost. " +
          "Acesse a aplicação por HTTPS para gravar áudio."
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        audioChunksRef.current = [];
        if (blob.size > 0) transcribeAudio(blob);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
    } catch (e) {
      console.error("Erro ao acessar o microfone", e);
      toast.error("Não foi possível acessar o microfone. Verifique as permissões do navegador.");
    }
  };

  const toggleRecording = () => {
    if (isRecording) stopRecording();
    else startRecording();
  };

  // Libera o microfone se o componente for desmontado durante a gravacao.
  useEffect(() => {
    return () => {
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  // Busca a URL assinada da fonte e abre o documento. Se a resposta citou uma
  // pagina para esse arquivo, abre direto nela via fragmento #page=N (suportado
  // pelos visualizadores de PDF do navegador).
  const handleDownloadSource = async (sourceLine: string, answerContent?: string) => {
    const filename = extractFilename(sourceLine);
    if (!filename) return;
    try {
      const res = await fetch(`${API_BASE_URL}/documents/download-url?name=${encodeURIComponent(filename)}`);
      if (res.ok) {
        const data = await res.json();
        // Pagina deterministica da propria linha de fonte (backend) tem prioridade;
        // como fallback, tenta a citacao "[arquivo.pdf, pag. N]" no texto da resposta.
        const page = extractSourcePage(sourceLine)
          ?? (answerContent ? extractCitedPage(answerContent, filename) : null);
        const url = page ? `${data.signed_url}#page=${page}` : data.signed_url;
        window.open(url, "_blank", "noopener,noreferrer");
      } else if (res.status === 404) {
        toast.error("Este documento ainda não está disponível para download no repositório.");
      } else {
        toast.error("Não foi possível obter o documento no momento.");
      }
    } catch (e) {
      console.error("Erro ao baixar documento", e);
      toast.error("Erro de conexão ao tentar baixar o documento.");
    }
  };

  return (
    <div className="flex flex-col h-full bg-muted/30">
      {/* Messages Area */}
      <div
        ref={messagesContainerRef}
        onScroll={handleMessagesScroll}
        className="flex-1 overflow-y-auto p-6 space-y-6"
      >
        {messages.map((m, idx) => (
          <div key={idx} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : ''}`}>
            {m.role === 'assistant' && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    onClick={() => setShowAbout(true)}
                    className="size-8 rounded-full shrink-0 shadow-sm ring-2 ring-transparent hover:ring-accent-blue/40 transition-all focus:outline-none focus-visible:ring-accent-blue/60"
                    aria-label="Sobre a Lina"
                  >
                    <Avatar className="size-8 shrink-0">
                      <AvatarImage
                        src="/Lina.jpg"
                        alt="Lina, assistente virtual da FAI-UFSCar"
                        className="object-cover"
                      />
                      <AvatarFallback className="bg-primary text-primary-foreground">L</AvatarFallback>
                    </Avatar>
                  </button>
                </TooltipTrigger>
                <TooltipContent>Sobre a Lina</TooltipContent>
              </Tooltip>
            )}

            <div className={`max-w-[85%] flex flex-col gap-2 ${m.role === 'user' ? 'items-end' : ''}`}>
              <div
                onClick={() => { if (m.role === 'assistant' && m.sources?.length && onActiveSources) onActiveSources(m.sources, m.content); }}
                title={m.role === 'assistant' && m.sources?.length ? 'Ver as fontes desta resposta no painel' : undefined}
                className={`rounded-2xl px-4 py-2 shadow-sm ${
                m.role === 'user'
                  ? 'bg-accent-blue text-white rounded-tr-none'
                  : 'bg-card text-card-foreground border border-border rounded-tl-none'
              } ${m.role === 'assistant' && m.sources?.length ? 'cursor-pointer hover:border-accent-blue/40 transition-colors' : ''}`}>
                {m.quoted && m.quoted.content && (
                  <QuotedBlock quoted={m.quoted} onUserBubble={m.role === 'user'} />
                )}
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

              {/* Botões de Cópia, Responder e Metadados/Fontes */}
              {m.role === 'user' && m.content && (
                <div className="px-1 flex justify-end gap-2">
                  <ReplyButton onClick={() => setReplyingTo({ role: 'user', content: m.content })} />
                  <CopyButton text={m.content} />
                </div>
              )}

              {m.role === 'assistant' && m.content && (
                <div className="px-1 space-y-2">
                  <div className="flex items-center gap-3">
                    <CopyButton text={m.content} />
                    <ReplyButton onClick={() => setReplyingTo({ role: 'assistant', content: m.content })} />
                    {m.genTime && (
                      <div className="text-[9px] text-muted-foreground italic">
                        Resposta gerada em {m.genTime.toFixed(2)}s
                      </div>
                    )}
                  </div>
                  {m.sources && m.sources.length > 0 && (
                    <div className="space-y-2 animate-in fade-in duration-500 mt-1">
                      <div className="flex items-center gap-2 text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                        <FileText size={10} /> Fontes Pesquisadas
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {m.sources.map((s, i) => (
                          <Button
                            key={i}
                            type="button"
                            variant="outline"
                            size="xs"
                            onClick={() => handleDownloadSource(s, m.content)}
                            title={`Baixar ${extractFilename(s)}`}
                            className="group/src text-[10px] bg-muted text-muted-foreground hover:bg-accent-blue/10 hover:text-accent-blue hover:border-accent-blue/30"
                          >
                            <Download className="opacity-60 group-hover/src:opacity-100" />
                            {extractFilename(s)}
                            {extractPagesLabel(s) && (
                              <span className="text-muted-foreground/70 group-hover/src:text-accent-blue/80">
                                · {extractPagesLabel(s)}
                              </span>
                            )}
                          </Button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {m.role === 'user' && (
              <Avatar className="size-8 shrink-0">
                <AvatarFallback className="bg-muted text-muted-foreground">
                  <User size={18} />
                </AvatarFallback>
              </Avatar>
            )}
          </div>
        ))}
        {/* Sentinela: alvo do scroll para o fim da conversa */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="relative p-4 bg-card border-t border-border shadow-[0_-4px_10px_rgba(0,0,0,0.02)]">
        {/* Setinha "ir para a última mensagem" (aparece ao rolar para cima) */}
        {showScrollToBottom && (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={() => scrollToBottom("smooth")}
                aria-label="Ir para a última mensagem"
                className="absolute -top-12 left-1/2 -translate-x-1/2 rounded-full bg-card text-muted-foreground shadow-lg hover:text-accent-blue hover:border-accent-blue/40 hover:bg-accent-blue/5 active:scale-95 animate-in fade-in slide-in-from-bottom-2 duration-200 z-40"
              >
                <ArrowDown size={18} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Ir para a última mensagem</TooltipContent>
          </Tooltip>
        )}
        {/* Barra de "respondendo a" (mensagem citada) */}
        {replyingTo && (
          <div className="max-w-4xl mx-auto mb-2 flex items-stretch gap-2 animate-in fade-in slide-in-from-bottom-2 duration-200">
            <div className="flex-1 flex items-start gap-2 rounded-lg border-l-[3px] border-accent-blue bg-accent-blue/5 px-3 py-2">
              <Reply size={14} className="text-accent-blue mt-0.5 shrink-0" />
              <div className="min-w-0">
                <div className="text-[10px] font-semibold text-accent-blue">
                  Respondendo a {replyingTo.role === 'assistant' ? 'Assistente' : 'Você'}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">{quotePreview(replyingTo.content)}</div>
              </div>
            </div>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setReplyingTo(null)}
                  aria-label="Cancelar"
                  className="self-stretch h-auto text-muted-foreground hover:text-foreground"
                >
                  <X size={16} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Cancelar</TooltipContent>
            </Tooltip>
          </div>
        )}
        <div className="max-w-4xl mx-auto flex gap-3 items-end relative">

          {/* Attachments Dropdown */}
          <div ref={attachmentRef} className="relative">
            {showAttachments && (
              <div className="absolute bottom-full left-0 mb-4 bg-card border border-border rounded-2xl shadow-2xl p-2 min-w-[200px] animate-in fade-in slide-in-from-bottom-4 duration-300 z-50">
                <div className="text-[10px] font-bold text-muted-foreground px-3 py-2 uppercase tracking-wider">Enviar para o Chat</div>
                <button className="w-full flex items-center gap-3 p-3 hover:bg-muted rounded-xl text-sm text-foreground transition-colors group">
                  <div className="w-8 h-8 bg-accent-blue/10 rounded-lg flex items-center justify-center group-hover:bg-accent-blue/20 transition-colors">
                    <FileText size={18} className="text-accent-blue" />
                  </div>
                  <span>Anexar Arquivo</span>
                </button>
                <button className="w-full flex items-center gap-3 p-3 hover:bg-muted rounded-xl text-sm text-foreground transition-colors group">
                  <div className="w-8 h-8 bg-fai-cyan/10 rounded-lg flex items-center justify-center group-hover:bg-fai-cyan/20 transition-colors">
                    {/* eslint-disable-next-line jsx-a11y/alt-text */}
                    <Image size={18} className="text-fai-cyan" />
                  </div>
                  <span>Anexar Imagem</span>
                </button>
              </div>
            )}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowAttachments(!showAttachments)}
                  aria-label="Anexar"
                  className={cn(
                    "rounded-full text-muted-foreground transition-all duration-300 hover:text-accent-blue",
                    showAttachments && "bg-muted text-foreground rotate-45"
                  )}
                >
                  <Plus size={22} />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Anexar</TooltipContent>
            </Tooltip>
          </div>

          {/* Main Input Field */}
          <div className="flex-1 flex gap-2 items-center bg-muted rounded-[24px] px-4 py-1.5 border border-border focus-within:border-accent-blue focus-within:bg-card focus-within:shadow-md transition-all">
            <Textarea
              rows={1}
              placeholder={isRecording ? "Gravando... fale sua dúvida" : isTranscribing ? "Transcrevendo áudio..." : "Digite sua dúvida aqui..."}
              className="flex-1 min-h-9 max-h-32 resize-none overflow-y-auto border-none bg-transparent shadow-none px-0 py-2 text-sm focus-visible:ring-0 focus-visible:border-none"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isTyping || isTranscribing}
            />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={toggleRecording}
                  aria-label={isRecording ? "Parar gravação" : isTranscribing ? "Transcrevendo..." : "Gravar pergunta por voz"}
                  className={cn(
                    "rounded-full transition-colors disabled:opacity-30",
                    isRecording
                      ? "text-destructive animate-pulse hover:text-destructive"
                      : "text-muted-foreground hover:text-accent-blue"
                  )}
                  disabled={isTyping || isTranscribing}
                >
                  {isTranscribing ? (
                    <Loader2 size={20} className="animate-spin" />
                  ) : isRecording ? (
                    <Square size={20} className="fill-current" />
                  ) : (
                    <Mic size={20} />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {isRecording ? "Parar gravação" : isTranscribing ? "Transcrevendo..." : "Gravar pergunta por voz"}
              </TooltipContent>
            </Tooltip>
          </div>

          {/* Send Button */}
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                onClick={handleSend}
                aria-label="Enviar"
                className="bg-accent-blue hover:bg-accent-blue-hover text-white p-3 rounded-full shadow-lg shadow-accent-blue/20 transition-all active:scale-95 disabled:opacity-50 disabled:grayscale disabled:shadow-none"
                disabled={!input.trim() || isTyping}
              >
                <Send size={20} />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Enviar</TooltipContent>
          </Tooltip>
        </div>
        <p className="text-[10px] text-muted-foreground text-center mt-3">
          O chatbot pode cometer erros. Considere verificar as fontes citadas.
        </p>
      </div>

      {/* Modal "Sobre a Lina" */}
      <Dialog open={showAbout} onOpenChange={setShowAbout}>
        <DialogContent className="max-w-sm" aria-label="Sobre a Lina">
          <DialogHeader className="items-center text-center sm:text-center">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/Lina.jpg"
              alt="Lina, assistente virtual da FAI-UFSCar"
              className="w-28 h-28 rounded-full object-cover shadow-md ring-4 ring-accent-blue/10"
            />
            <DialogTitle className="mt-4 text-lg font-bold text-foreground">Lina</DialogTitle>
            <p className="text-xs font-medium text-accent-blue uppercase tracking-wider">
              Assistente Virtual · FAI-UFSCar
            </p>
            {/* TODO: o texto "Sobre a Lina" será atualizado futuramente. */}
            <DialogDescription className="mt-3 text-sm text-muted-foreground leading-relaxed">
              Olá! Eu sou a Lina, sua assistente virtual da FAI-UFSCar. Estou aqui
              para ajudar você a consultar manuais, procedimentos e documentos
              institucionais de forma rápida e confiável.
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    </div>
  );
}
