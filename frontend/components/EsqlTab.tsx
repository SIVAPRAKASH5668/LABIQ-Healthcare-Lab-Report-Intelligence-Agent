'use client';

import { useState, useRef } from 'react';
import axios from 'axios';
import {
  Play, Loader2, Copy, Check, Zap,
  ChevronDown, ChevronUp, Database, AlertCircle,
  TerminalSquare, Clock, Hash
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const EXAMPLES = [
  {
    label: 'Risk Ranking',
    color: 'red',
    q: `FROM lab-results
| STATS
    total_panels = COUNT(*),
    abnormal     = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    critical     = COUNT(*) WHERE critical_flags IS NOT NULL,
    last_test    = MAX(test_date)
  BY patient_id
| EVAL risk_score = critical * 3 + abnormal
| SORT risk_score DESC`,
  },
  {
    label: 'Abnormal Panels',
    color: 'amber',
    q: `FROM lab-results
| WHERE abnormal_flags IS NOT NULL
| SORT test_date DESC
| LIMIT 10
| KEEP patient_id, test_date, test_type, abnormal_flags`,
  },
  {
    label: 'Critical Only',
    color: 'red',
    q: `FROM lab-results
| WHERE critical_flags IS NOT NULL
| SORT test_date DESC
| LIMIT 10
| KEEP patient_id, test_date, critical_flags`,
  },
  {
    label: 'PAT001 Summary',
    color: 'emerald',
    q: `FROM lab-results
| WHERE patient_id == "PAT001"
| STATS
    total    = COUNT(*),
    abnormal = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    critical = COUNT(*) WHERE critical_flags IS NOT NULL,
    first    = MIN(test_date),
    last     = MAX(test_date)`,
  },
  {
    label: 'Timeline',
    color: 'blue',
    q: `FROM lab-results
| STATS
    critical = COUNT(*) WHERE critical_flags IS NOT NULL,
    abnormal = COUNT(*) WHERE abnormal_flags IS NOT NULL
  BY test_date
| SORT test_date ASC`,
  },
  {
    label: 'System Stats',
    color: 'violet',
    q: `FROM lab-results
| STATS
    total_docs      = COUNT(*),
    total_patients  = COUNT_DISTINCT(patient_id),
    critical_panels = COUNT(*) WHERE critical_flags IS NOT NULL,
    abnormal_panels = COUNT(*) WHERE abnormal_flags IS NOT NULL,
    latest_upload   = MAX(test_date)`,
  },
];

const colorMap: Record<string, string> = {
  red:     'border-red-500/30 text-red-400 bg-red-500/6',
  amber:   'border-amber-500/30 text-amber-400 bg-amber-500/6',
  emerald: 'border-emerald-500/30 text-emerald-400 bg-emerald-500/6',
  blue:    'border-blue-500/30 text-blue-400 bg-blue-500/6',
  violet:  'border-violet-500/30 text-violet-400 bg-violet-500/6',
};

interface Col { name: string; type: string; }
interface EsqlResult {
  status: string;
  columns: Col[];
  rows: Record<string, any>[];
  row_count: number;
  ms: number;
  executed_at: string;
  error?: string;
}

function cellClass(col: Col, val: any): string {
  if (col.name === 'patient_id') return 'text-emerald-300 font-semibold';
  if (col.name.includes('critical') && typeof val === 'number' && val > 0) return 'text-red-400 font-bold';
  if (col.name.includes('abnormal') && typeof val === 'number' && val > 0) return 'text-amber-400 font-semibold';
  if (col.name === 'risk_score') {
    if (typeof val === 'number') {
      if (val >= 10) return 'text-red-400 font-bold';
      if (val >= 4)  return 'text-amber-400 font-semibold';
      return 'text-emerald-400';
    }
  }
  if (col.type === 'long' || col.type === 'double') return 'text-sky-300 tabular-nums';
  if (col.name.includes('date')) return 'text-blue-400/80';
  return 'text-gray-300';
}

function fmtVal(val: any): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'string' && val.includes('T') && val.endsWith('Z')) return val.slice(0, 10);
  if (Array.isArray(val)) return val.join(', ') || '—';
  return String(val);
}

export default function EsqlTab() {
  const [query,   setQuery]   = useState(EXAMPLES[0].q);
  const [result,  setResult]  = useState<EsqlResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const [copied,  setCopied]  = useState(false);
  const [active,  setActive]  = useState(0);
  const [rawOpen, setRawOpen] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);

  const run = async () => {
    if (!query.trim() || running) return;
    setRunning(true); setError(null); setResult(null); setRawOpen(false);
    try {
      const { data } = await axios.post(`${API}/api/esql/run`, { query, limit: 100 });
      if (data.status === 'error') setError(data.error);
      else setResult(data);
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Query failed');
    } finally { setRunning(false); }
  };

  const copy = () => {
    navigator.clipboard.writeText(query);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  const pick = (i: number) => {
    setActive(i); setQuery(EXAMPLES[i].q);
    setResult(null); setError(null); setRawOpen(false);
  };

  const lineCount = query.split('\n').length;

  return (
    <div className="flex flex-col gap-4 h-[calc(100vh-180px)] max-w-7xl mx-auto">

      {/* ── Top bar ────────────────────────────────────────── */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20
          flex items-center justify-center">
          <TerminalSquare className="w-4 h-4 text-emerald-400" />
        </div>
        <div>
          <p className="text-sm font-semibold text-white tracking-wide">ES|QL Console</p>
          <p className="text-[10px] font-mono text-gray-600">
            Direct queries · lab-results index · Elasticsearch 8.11
          </p>
        </div>
        {result && (
          <div className="ml-auto flex items-center gap-3 text-[11px] font-mono">
            <span className="flex items-center gap-1.5 text-emerald-400
              bg-emerald-500/8 border border-emerald-500/20 px-2.5 py-1 rounded-full">
              <Hash className="w-3 h-3" />{result.row_count} rows
            </span>
            <span className="flex items-center gap-1.5 text-gray-500">
              <Clock className="w-3 h-3" />{result.ms}ms
            </span>
          </div>
        )}
      </div>

      {/* ── Example chips ──────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 shrink-0">
        {EXAMPLES.map(({ label, color }, i) => (
          <button key={i} onClick={() => pick(i)}
            className={`text-[11px] font-mono px-3 py-1.5 rounded-lg border transition-all ${
              active === i
                ? colorMap[color]
                : 'border-gray-800/60 text-gray-500 hover:border-gray-700 hover:text-gray-300 bg-gray-900/30'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Main split ─────────────────────────────────────── */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* Editor */}
        <div className="flex flex-col w-[52%] shrink-0 rounded-2xl border border-gray-800/60
          bg-gray-900/20 overflow-hidden">

          {/* Editor toolbar */}
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-gray-800/60
            bg-black/20 shrink-0">
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500/50" />
              <div className="w-2.5 h-2.5 rounded-full bg-amber-500/50" />
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500/50" />
            </div>
            <span className="text-[10px] font-mono text-gray-700 ml-1">query.esql</span>
            <div className="ml-auto flex items-center gap-2">
              <span className="text-[9px] font-mono text-gray-700">{lineCount} lines</span>
              <button onClick={copy}
                className="flex items-center gap-1 text-[10px] font-mono px-2 py-1
                  rounded-md text-gray-600 hover:text-gray-300 hover:bg-gray-800
                  transition-colors">
                {copied
                  ? <><Check className="w-3 h-3 text-emerald-400" /><span className="text-emerald-400">Copied</span></>
                  : <><Copy className="w-3 h-3" />Copy</>}
              </button>
              <button onClick={run} disabled={running || !query.trim()}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500 text-gray-950
                  rounded-lg font-bold text-[11px] hover:bg-emerald-400 transition-all
                  disabled:opacity-25 disabled:cursor-not-allowed shadow-[0_0_12px_#10b98125]">
                {running
                  ? <><Loader2 className="w-3 h-3 animate-spin" />Running…</>
                  : <><Play className="w-3 h-3" />Run</>}
              </button>
            </div>
          </div>

          {/* Code area */}
          <div className="flex flex-1 min-h-0 overflow-hidden">
            {/* Line numbers */}
            <div className="select-none shrink-0 pt-3 pb-3 px-2 bg-black/20
              border-r border-gray-800/40 text-right min-w-[38px] overflow-hidden">
              {query.split('\n').map((_, i) => (
                <div key={i} className="text-[11px] font-mono text-gray-700 leading-[22px]">
                  {i + 1}
                </div>
              ))}
            </div>
            <textarea
              ref={textRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                  e.preventDefault(); run();
                }
              }}
              className="flex-1 px-4 py-3 bg-transparent text-[13px] text-emerald-200/80
                font-mono resize-none focus:outline-none leading-[22px] overflow-auto"
              placeholder="FROM lab-results | LIMIT 10"
              spellCheck={false}
            />
          </div>

          {/* Hint bar */}
          <div className="px-4 py-1.5 border-t border-gray-800/40 bg-black/10 shrink-0">
            <span className="text-[9px] font-mono text-gray-700 tracking-wider">
              ⌘+Enter to run · FROM lab-results · pipe with |
            </span>
          </div>
        </div>

        {/* Results panel */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">

          {/* Error */}
          {error && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-xl
              bg-red-500/8 border border-red-500/20 shrink-0">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-semibold text-red-300">Query Error</p>
                <pre className="text-[11px] font-mono text-red-400/60 mt-1 whitespace-pre-wrap">
                  {error}
                </pre>
              </div>
            </div>
          )}

          {/* Results table */}
          {result?.status === 'ok' && (
            <div className="flex-1 min-h-0 rounded-2xl border border-gray-800/60
              bg-gray-900/20 overflow-hidden flex flex-col">

              {/* Table header */}
              <div className="flex items-center gap-3 px-4 py-2.5 border-b border-gray-800/60
                bg-black/20 shrink-0">
                <Database className="w-3.5 h-3.5 text-emerald-400/60" />
                <span className="text-[11px] font-mono font-semibold text-emerald-400">
                  {result.row_count} rows
                </span>
                <span className="text-[10px] font-mono text-gray-600">{result.ms}ms</span>
                <span className="text-[10px] font-mono text-gray-700">·</span>
                <span className="text-[10px] font-mono text-gray-600">
                  {new Date(result.executed_at).toLocaleTimeString()}
                </span>
                <div className="ml-auto flex flex-wrap gap-1">
                  {result.columns.slice(0, 5).map(c => (
                    <span key={c.name} className="text-[9px] font-mono text-gray-700
                      bg-gray-800/50 px-1.5 py-0.5 rounded border border-gray-700/30">
                      {c.name}
                    </span>
                  ))}
                  {result.columns.length > 5 && (
                    <span className="text-[9px] font-mono text-gray-700">
                      +{result.columns.length - 5}
                    </span>
                  )}
                </div>
              </div>

              {/* Scrollable table */}
              <div className="overflow-auto flex-1">
                <table className="w-full text-[12px] border-collapse">
                  <thead className="sticky top-0 z-10">
                    <tr className="bg-[#0b0e1a]">
                      <th className="px-3 py-2 text-left font-mono text-gray-700
                        text-[9px] uppercase tracking-wider w-7 border-b border-gray-800/60">
                        #
                      </th>
                      {result.columns.map(c => (
                        <th key={c.name}
                          className="px-3 py-2 text-left font-mono text-gray-500
                            text-[10px] uppercase tracking-wider whitespace-nowrap
                            border-b border-gray-800/60 border-l border-gray-800/30">
                          {c.name}
                          <span className="text-gray-700 normal-case ml-1 text-[9px] font-normal">
                            {c.type}
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr key={i}
                        className={`border-b border-gray-800/20 transition-colors
                          hover:bg-emerald-500/3 ${i % 2 === 1 ? 'bg-gray-900/20' : ''}`}>
                        <td className="px-3 py-2 text-[10px] font-mono text-gray-700 select-none">
                          {i + 1}
                        </td>
                        {result.columns.map(col => (
                          <td key={col.name}
                            className={`px-3 py-2 font-mono whitespace-nowrap
                              border-l border-gray-800/20 ${cellClass(col, row[col.name])}`}>
                            {fmtVal(row[col.name])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Raw JSON toggle */}
              <div className="border-t border-gray-800/40 shrink-0">
                <button onClick={() => setRawOpen(r => !r)}
                  className="flex items-center gap-2 px-4 py-2 w-full text-left
                    text-[10px] font-mono text-gray-700 hover:text-gray-400 transition-colors">
                  {rawOpen
                    ? <ChevronUp className="w-3 h-3" />
                    : <ChevronDown className="w-3 h-3" />}
                  Raw JSON
                </button>
                {rawOpen && (
                  <pre className="px-4 py-3 text-[10px] font-mono text-emerald-300/40
                    bg-black/30 overflow-x-auto max-h-36 border-t border-gray-800/40">
                    {JSON.stringify({ columns: result.columns, rows: result.rows.slice(0, 3) }, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}

          {/* Empty state */}
          {!result && !error && !running && (
            <div className="flex-1 rounded-2xl border border-dashed border-gray-800/40
              flex flex-col items-center justify-center gap-3 text-center">
              <div className="w-12 h-12 rounded-2xl bg-gray-800/30 border border-gray-700/30
                flex items-center justify-center">
                <Zap className="w-6 h-6 text-gray-700" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Pick a query and hit Run</p>
                <p className="text-[10px] font-mono text-gray-700 mt-1">or Ctrl+Enter in the editor</p>
              </div>
            </div>
          )}

          {/* Running skeleton */}
          {running && (
            <div className="flex-1 rounded-2xl border border-gray-800/60 bg-gray-900/20
              flex flex-col items-center justify-center gap-3">
              <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
              <p className="text-sm font-mono text-gray-500">Querying Elasticsearch…</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}