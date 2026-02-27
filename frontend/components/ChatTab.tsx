'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Send, Loader2, ChevronDown, ChevronUp, Zap,
  Brain, Activity, User, Terminal, AlertCircle,
  Cpu, Wrench, RefreshCw, CheckCircle, XCircle,
  Sparkles
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ReasoningStep {
  step: string;
  tool?: string;
  rows?: number;
  error?: string;
}

interface Message {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  source?: string;
  tools_used?: string[];
  esql_query?: string;
  reasoning_trace?: ReasoningStep[];
  execution_ms?: number;
  error?: boolean;
}

interface McpStatus {
  connected: boolean;
  tool_count: number;
  checked: boolean;
}

function fmtDate(s: string) {
  const d = new Date(s);
  return isNaN(d.getTime()) ? s : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function renderMd(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/`(.+?)`/g, '<code class="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded text-[13px]">$1</code>')
    .replace(/^### (.+)$/gm, '<p class="text-xs font-mono text-gray-500 uppercase tracking-widest mt-4 mb-1">$1</p>')
    .replace(/^## (.+)$/gm, '<p class="text-base font-semibold text-gray-200 mt-3 mb-1">$1</p>')
    .replace(/🔴 \*\*(.+?)\*\*/g, '🔴 <strong class="text-red-400">$1</strong>')
    .replace(/🟡 \*\*(.+?)\*\*/g, '🟡 <strong class="text-amber-400">$1</strong>')
    .replace(/✅ \*\*(.+?)\*\*/g, '✅ <strong class="text-emerald-400">$1</strong>')
    .replace(
      /(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)/g,
      (_, d) => `<span class="text-blue-400/80 font-mono text-xs">${fmtDate(d)}</span>`
    )
    .replace(/\n\n/g, '</p><p class="mt-2">')
    .replace(/\n/g, '<br/>');
}

function ToolPill({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1
      rounded-full border border-violet-500/25 bg-violet-500/8 text-violet-400">
      <Wrench className="w-3 h-3" />{name.replace(/_/g, ' ')}
    </span>
  );
}

function SourceBadge({ source }: { source?: string }) {
  const cfg: Record<string, { label: string; icon: React.ReactNode; cls: string }> = {
    kibana_agent: { label: 'Kibana Agent Builder + MCP', icon: <Sparkles className="w-3 h-3" />, cls: 'text-emerald-400 bg-emerald-500/8 border-emerald-500/25' },
    mcp:          { label: 'Elastic MCP',                icon: <Zap       className="w-3 h-3" />, cls: 'text-cyan-400   bg-cyan-500/8   border-cyan-500/25'   },
    esql_direct:  { label: 'ES|QL Direct',               icon: <Terminal  className="w-3 h-3" />, cls: 'text-blue-400  bg-blue-500/8   border-blue-500/25'   },
    fallback:     { label: 'Local Analyzer',             icon: <Cpu       className="w-3 h-3" />, cls: 'text-amber-400 bg-amber-500/8  border-amber-500/25'  },
    error:        { label: 'Unavailable',                icon: <AlertCircle className="w-3 h-3"/>, cls: 'text-red-400   bg-red-500/8    border-red-500/25'    },
  };
  const b = cfg[source ?? 'fallback'] ?? cfg.fallback;
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded-full border ${b.cls}`}>
      {b.icon}{b.label}
    </span>
  );
}

function EsqlBlock({ query }: { query: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 rounded-lg overflow-hidden border border-emerald-500/10 bg-black/30">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-4 py-2 text-xs font-mono
          text-emerald-500/50 hover:text-emerald-400/70 transition-colors">
        <Terminal className="w-3.5 h-3.5 shrink-0" />
        <span className="tracking-widest uppercase">ES|QL</span>
        <span className="ml-auto">{open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}</span>
      </button>
      {open && (
        <pre className="text-emerald-300/50 text-xs px-5 py-3 overflow-x-auto
          whitespace-pre-wrap leading-relaxed font-mono border-t border-emerald-500/8">
          {query}
        </pre>
      )}
    </div>
  );
}

function ReasoningTrace({ steps }: { steps: ReasoningStep[] }) {
  const [open, setOpen] = useState(false);
  if (!steps?.length) return null;
  return (
    <div className="mt-2 rounded-lg overflow-hidden border border-violet-500/10 bg-black/30">
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-4 py-2 text-xs font-mono
          text-violet-500/50 hover:text-violet-400/70 transition-colors">
        <Brain className="w-3.5 h-3.5 shrink-0" />
        <span className="tracking-widest uppercase">Agent Reasoning</span>
        <span className="ml-1 text-violet-700">({steps.length} steps)</span>
        <span className="ml-auto">{open ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}</span>
      </button>
      {open && (
        <div className="border-t border-violet-500/8 px-4 py-3 space-y-2">
          {steps.map((s, i) => (
            <div key={i} className="flex items-start gap-2.5 text-xs font-mono">
              <span className="text-violet-600/50 shrink-0 mt-0.5">·</span>
              <div className="text-violet-400/50 flex-1 leading-relaxed">
                <span className="text-violet-300/60">{s.step}</span>
                {s.tool && <span className="ml-2 text-[10px] bg-violet-500/8 text-violet-400/60 px-1.5 py-0.5 rounded border border-violet-500/15">{s.tool}</span>}
                {s.rows !== undefined && <span className="ml-2 text-violet-700">{s.rows} rows</span>}
                {s.error && <span className="ml-2 text-red-400/50">{s.error}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TypingDots({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex gap-1.5">
        {[0, 150, 300].map(d => (
          <div key={d} className="w-2 h-2 rounded-full bg-emerald-400/30 animate-bounce"
            style={{ animationDelay: `${d}ms` }} />
        ))}
      </div>
      <span className="text-xs font-mono text-gray-600">{label}</span>
    </div>
  );
}

const CHIPS = [
  { label: 'Lab summary',      q: 'Give me a complete lab summary'             },
  { label: 'Latest results',   q: 'Show my latest lab results with all values' },
  { label: 'Abnormal values',  q: 'What are my abnormal results?'              },
  { label: 'Critical flags',   q: 'Are there any critical values?'             },
  { label: 'Trends over time', q: 'How have my values changed over time?'      },
  { label: 'Risk assessment',  q: 'Assess my overall health risk'              },
  { label: 'Explain results',  q: 'Explain what my results mean for my health' },
  { label: 'Compare patients', q: 'Which patient has the highest risk?'        },
];

interface ChatTabProps { patientId: string; }

export default function ChatTab({ patientId }: ChatTabProps) {
  const [messages,   setMessages]   = useState<Message[]>([]);
  const [input,      setInput]      = useState('');
  const [loading,    setLoading]    = useState(false);
  const [history,    setHistory]    = useState<{ role: string; content: string }[]>([]);
  const [mcpStatus,  setMcpStatus]  = useState<McpStatus>({ connected: false, tool_count: 0, checked: false });
  const [thinkLabel, setThinkLabel] = useState('Agent Builder reasoning…');
  const bottomRef = useRef<HTMLDivElement>(null);
  const msgId     = useRef(0);

  const checkMcp = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/mcp/discover`);
      setMcpStatus({ connected: data.status === 'connected', tool_count: data.total_tools ?? 0, checked: true });
    } catch {
      setMcpStatus({ connected: false, tool_count: 0, checked: true });
    }
  }, []);

  useEffect(() => {
    checkMcp();
    setMessages([{
      id:      ++msgId.current,
      role:    'assistant',
      content: `Hello! I'm LabIQ — connected to **Elastic Agent Builder** via MCP.\n\nI autonomously select ES|QL tools registered in Kibana, query your Elasticsearch index in real time, and reason over the results to give you clinical-quality answers.\n\nCurrently analyzing patient **${patientId}**. Ask me anything.`,
      source:  'kibana_agent',
    }]);
  }, [patientId, checkMcp]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    if (!loading) return;
    const steps = [
      'Calling Kibana Agent Builder…',
      'Agent selecting MCP tools…',
      'Running ES|QL via MCP…',
      'Reasoning over results…',
      'Generating clinical response…',
    ];
    let i = 0;
    const iv = setInterval(() => { i = (i + 1) % steps.length; setThinkLabel(steps[i]); }, 1800);
    return () => clearInterval(iv);
  }, [loading]);

  const send = async (text?: string) => {
    const msg = (text ?? input).trim();
    if (!msg || loading) return;
    setMessages(p => [...p, { id: ++msgId.current, role: 'user', content: msg }]);
    setInput('');
    setLoading(true);
    const newHistory = [...history, { role: 'user', content: msg }];
    try {
      const { data } = await axios.post(`${API}/api/llm/chat`, {
        message: msg, patient_id: patientId, conversation_history: history,
      });
      const m: Message = {
        id: ++msgId.current, role: 'assistant', content: data.response,
        source: data.source, tools_used: data.tools_used,
        esql_query: data.esql_query, reasoning_trace: data.reasoning_trace,
        execution_ms: data.execution_ms, error: data.source === 'error',
      };
      setMessages(p => [...p, m]);
      setHistory([...newHistory, { role: 'assistant', content: data.response }]);
    } catch {
      setMessages(p => [...p, {
        id: ++msgId.current, role: 'assistant', source: 'error', error: true,
        content: '⚠️ Could not reach the backend. Make sure FastAPI is running on port 8000.',
      }]);
    } finally { setLoading(false); }
  };

  const clearChat = () => {
    setHistory([]);
    setMessages([{ id: ++msgId.current, role: 'assistant', source: 'kibana_agent',
      content: `Chat cleared. Still analyzing patient **${patientId}**. Ask me anything.` }]);
  };

  return (
    <div className="flex w-full gap-5" style={{ height: 'calc(100vh - 168px)' }}>

      {/* ── LEFT: Chat column ───────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 gap-4">

        {/* Status bar */}
        <div className="flex items-center gap-4 px-5 py-3 rounded-xl
          bg-gray-900/40 border border-gray-800/50 shrink-0">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              mcpStatus.connected ? 'bg-emerald-400 shadow-[0_0_6px_#34d399] animate-pulse'
              : mcpStatus.checked ? 'bg-amber-400' : 'bg-gray-600'
            }`} />
            <span className="text-xs font-mono text-gray-400 uppercase tracking-widest">
              {mcpStatus.connected ? `MCP · ${mcpStatus.tool_count} tools`
               : mcpStatus.checked ? 'MCP offline · ES|QL direct' : 'Checking MCP…'}
            </span>
          </div>
          <div className="w-px h-4 bg-gray-800 mx-1" />
          <span className="text-xs font-mono text-gray-600 uppercase tracking-widest hidden sm:block">
            Elastic Agent Builder · LLM Reasoning
          </span>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs font-mono text-emerald-400/80 bg-emerald-500/6
              border border-emerald-500/12 px-3 py-1 rounded-full">{patientId}</span>
            <button onClick={clearChat} title="Clear chat"
              className="p-2 rounded-lg text-gray-700 hover:text-gray-400 hover:bg-gray-800 transition-colors">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto rounded-xl border border-gray-800/50
          bg-gray-950/30 px-6 py-6 space-y-6 min-h-0">
          {messages.map(msg => (
            <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>

              {msg.role === 'assistant' && (
                <div className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 mt-1 ${
                  msg.error ? 'bg-red-500/8 border-red-500/20' : 'bg-emerald-500/8 border-emerald-500/15'
                }`}>
                  <Activity className={`w-4 h-4 ${msg.error ? 'text-red-400' : 'text-emerald-400'}`} />
                </div>
              )}

              <div className={`flex flex-col min-w-0 ${
                msg.role === 'user' ? 'items-end max-w-[65%]' : 'items-start flex-1 max-w-[88%]'
              }`}>
                <div className={`w-full rounded-2xl px-5 py-4 ${
                  msg.role === 'user'
                    ? 'bg-gray-800/80 border border-gray-700/60 rounded-tr-sm text-base text-gray-100'
                    : msg.error
                      ? 'bg-red-500/5 border border-red-500/15 rounded-tl-sm'
                      : 'bg-gray-900/50 border border-gray-800/50 rounded-tl-sm'
                }`}>
                  {msg.role === 'assistant' ? (
                    <div className="text-base text-gray-200 leading-8"
                      dangerouslySetInnerHTML={{ __html: renderMd(msg.content) }} />
                  ) : (
                    <p className="text-base leading-relaxed">{msg.content}</p>
                  )}
                </div>

                {msg.role === 'assistant' && (
                  <div className="w-full mt-3 space-y-2">
                    {msg.tools_used?.length ? (
                      <div className="flex flex-wrap gap-2">
                        {msg.tools_used.map(t => <ToolPill key={t} name={t} />)}
                      </div>
                    ) : null}
                    {msg.esql_query && <EsqlBlock query={msg.esql_query} />}
                    {msg.reasoning_trace?.length ? <ReasoningTrace steps={msg.reasoning_trace} /> : null}
                    <div className="flex items-center gap-3">
                      <SourceBadge source={msg.source} />
                      {msg.execution_ms && msg.execution_ms > 0 && (
                        <span className="text-xs font-mono text-gray-700">{msg.execution_ms}ms</span>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="w-9 h-9 rounded-xl bg-gray-800/60 border border-gray-700/50
                  flex items-center justify-center shrink-0 mt-1">
                  <User className="w-4 h-4 text-gray-400" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-4 justify-start">
              <div className="w-9 h-9 rounded-xl bg-emerald-500/8 border border-emerald-500/15
                flex items-center justify-center shrink-0">
                <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
              </div>
              <div className="bg-gray-900/50 border border-gray-800/50 rounded-2xl rounded-tl-sm px-5 py-4">
                <TypingDots label={thinkLabel} />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="rounded-xl border border-gray-800/50 bg-gray-900/40 p-4 space-y-3 shrink-0">
          <div className="flex flex-wrap gap-2">
            {CHIPS.map(({ label, q }) => (
              <button key={label} onClick={() => send(q)} disabled={loading}
                className="text-xs font-mono px-3 py-1.5 bg-gray-900/60 border border-gray-800
                  rounded-full text-gray-600 hover:border-emerald-500/30 hover:text-emerald-400
                  hover:bg-emerald-500/4 disabled:opacity-30 transition-all tracking-wide">
                {label}
              </button>
            ))}
          </div>
          <div className="flex gap-3">
            <input
              type="text" value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
              placeholder={`Ask about ${patientId}'s lab results…`}
              disabled={loading}
              className="flex-1 px-5 py-3 bg-gray-800/50 border border-gray-700/50
                rounded-xl text-base text-gray-200 placeholder:text-gray-600 font-mono
                focus:outline-none focus:border-emerald-500/30 focus:ring-1 focus:ring-emerald-500/8
                disabled:opacity-40 transition-colors"
            />
            <button onClick={() => send()} disabled={loading || !input.trim()}
              className="px-5 py-3 bg-emerald-500 text-gray-950 rounded-xl font-bold text-base
                hover:bg-emerald-400 disabled:opacity-20 disabled:cursor-not-allowed
                flex items-center gap-2 transition-all shadow-[0_0_20px_#10b98112]">
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>
          <p className="text-[10px] font-mono text-gray-800 text-center tracking-widest uppercase">
            Elastic Agent Builder · MCP Protocol · ES|QL Real-Time · Multi-turn
          </p>
        </div>
      </div>

      {/* ── RIGHT: Side panel ───────────────────────────────── */}
      <div className="w-72 shrink-0 flex-col gap-4 hidden lg:flex">

        {/* MCP Connection */}
        <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-800/50 flex items-center gap-2.5">
            <Zap className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-semibold text-gray-300">MCP Connection</span>
            <button onClick={checkMcp} className="ml-auto text-gray-600 hover:text-emerald-400 transition-colors p-1">
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="px-5 py-4 space-y-3">
            <div className="flex items-center gap-2.5">
              {mcpStatus.connected
                ? <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                : <XCircle    className="w-4 h-4 text-red-400    shrink-0" />}
              <span className={`text-sm font-mono ${mcpStatus.connected ? 'text-emerald-400' : 'text-red-400'}`}>
                {mcpStatus.connected ? 'Connected' : mcpStatus.checked ? 'Offline' : 'Checking…'}
              </span>
            </div>
            {mcpStatus.connected && (
              <div className="px-4 py-3 bg-emerald-500/5 border border-emerald-500/10 rounded-xl">
                <div className="text-[10px] font-mono text-emerald-700 uppercase tracking-widest">Tools Available</div>
                <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">{mcpStatus.tool_count}</div>
              </div>
            )}
            <div className="text-xs font-mono text-gray-700 break-all leading-relaxed">
              /api/agent_builder/mcp
            </div>
          </div>
        </div>

        {/* Pipeline */}
        <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 overflow-hidden flex-1">
          <div className="px-5 py-4 border-b border-gray-800/50 flex items-center gap-2.5">
            <Brain className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-semibold text-gray-300">Agent Pipeline</span>
          </div>
          <div className="px-5 py-4 space-y-3">
            {[
              { label: 'LLM (Agent Builder)', color: 'emerald', desc: 'Kibana reasoning model' },
              { label: 'MCP Tools',           color: 'violet',  desc: 'ES|QL tool selection'  },
              { label: 'Elasticsearch',       color: 'cyan',    desc: 'lab-results index'     },
              { label: 'Clinical Response',   color: 'emerald', desc: 'Formatted for patient' },
            ].map(({ label, color, desc }, i) => (
              <div key={i} className="flex items-start gap-3">
                <div className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${
                  color === 'emerald' ? 'bg-emerald-400/60' :
                  color === 'violet'  ? 'bg-violet-400/60'  : 'bg-cyan-400/60'
                }`} />
                <div>
                  <div className="text-sm font-mono text-gray-400">{label}</div>
                  <div className="text-xs font-mono text-gray-700 mt-0.5">{desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Session stats */}
        <div className="rounded-xl border border-gray-800/60 bg-gray-900/20 px-5 py-4 space-y-3">
          <p className="text-xs font-mono text-gray-600 uppercase tracking-widest">Session</p>
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center bg-gray-900/40 rounded-xl py-3">
              <div className="text-2xl font-bold font-mono text-gray-300">
                {messages.filter(m => m.role === 'user').length}
              </div>
              <div className="text-xs font-mono text-gray-700 mt-0.5">messages</div>
            </div>
            <div className="text-center bg-gray-900/40 rounded-xl py-3">
              <div className="text-2xl font-bold font-mono text-gray-300">
                {messages.filter(m => m.source === 'kibana_agent').length}
              </div>
              <div className="text-xs font-mono text-gray-700 mt-0.5">via LLM</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}