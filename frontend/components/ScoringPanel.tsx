'use client';

import { useState, useEffect } from 'react';
import {
  Target, BarChart3, ChevronDown, ChevronUp,
  AlertCircle, RefreshCw, Layers, GitBranch,
  Database, TrendingUp, Zap
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SimilarPatient {
  patient_id: string;
  similarity: number;
  similarity_pct: number;
  risk_level: string;
  critical_flags: string[];
  interpretation: string;
}
interface ScoredPanel {
  test_date: string;
  test_type: string;
  es_score: number;
  risk_score: number;
  risk_level: string;
  critical_flags: string[];
  abnormal_flags: string[];
  result_count: number;
  priority: string;
}
interface PopStats {
  risk_percentiles: Record<string, number>;
  by_risk_level: Record<string, number>;
  avg_risk_score: number;
  patients_with_criticals: number;
}

function AnimatedNumber({ value, decimals = 0 }: { value: number; decimals?: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const inc = (value - start) / (900 / 16);
    const t = setInterval(() => {
      start += inc;
      if (start >= value) { setDisplay(value); clearInterval(t); }
      else setDisplay(start);
    }, 16);
    return () => clearInterval(t);
  }, [value]);
  return <>{display.toFixed(decimals)}</>;
}

function RiskGauge({ percentile }: { percentile: number }) {
  const angle = (percentile / 100) * 180 - 90;
  const color = percentile >= 90 ? '#ef4444' : percentile >= 75 ? '#f97316'
    : percentile >= 50 ? '#eab308' : '#22c55e';
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-60 h-32 overflow-hidden">
        <svg viewBox="0 0 200 100" className="w-full h-full">
          <path d="M 10 100 A 90 90 0 0 1 190 100" fill="none" stroke="#1f2937" strokeWidth="14" strokeLinecap="round" />
          <path d="M 10 100 A 90 90 0 0 1 100 10"  fill="none" stroke="#166534" strokeWidth="14" strokeOpacity="0.5" strokeLinecap="round" />
          <path d="M 100 10 A 90 90 0 0 1 163 27"  fill="none" stroke="#854d0e" strokeWidth="14" strokeOpacity="0.5" strokeLinecap="round" />
          <path d="M 163 27 A 90 90 0 0 1 190 100" fill="none" stroke="#991b1b" strokeWidth="14" strokeOpacity="0.5" strokeLinecap="round" />
          <g transform={`rotate(${angle}, 100, 100)`}>
            <line x1="100" y1="100" x2="100" y2="16" stroke={color} strokeWidth="3.5" strokeLinecap="round" />
            <circle cx="100" cy="100" r="6" fill={color} />
          </g>
          <text x="6"   y="98" fill="#6b7280" fontSize="10" fontFamily="monospace">0</text>
          <text x="91"  y="8"  fill="#6b7280" fontSize="10" fontFamily="monospace">50</text>
          <text x="174" y="98" fill="#6b7280" fontSize="10" fontFamily="monospace">100</text>
        </svg>
      </div>
      <div className="text-center -mt-2">
        <div className="text-6xl font-black font-mono leading-none" style={{ color }}>
          <AnimatedNumber value={percentile} /><span className="text-3xl">th</span>
        </div>
        <div className="text-sm font-mono text-gray-500 uppercase tracking-widest mt-2">percentile rank</div>
        <div className="text-base font-semibold font-mono mt-1.5" style={{ color }}>
          {percentile >= 95 ? '🔴 Top 5% Most Critical' :
           percentile >= 90 ? '🔴 Top 10% Critical' :
           percentile >= 75 ? '🟠 Top 25% High Risk' :
           percentile >= 50 ? '🟡 Above Average Risk' : '🟢 Below Average Risk'}
        </div>
      </div>
    </div>
  );
}

function SimilarityBar({ patient, delay }: { patient: SimilarPatient; delay: number }) {
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const t = setTimeout(() => setWidth(patient.similarity_pct), delay);
    return () => clearTimeout(t);
  }, [patient.similarity_pct, delay]);

  const riskColor = {
    CRITICAL: 'text-red-400', HIGH: 'text-orange-400',
    MODERATE: 'text-yellow-400', LOW: 'text-emerald-400',
  }[patient.risk_level] || 'text-gray-400';

  const barColor = patient.similarity_pct >= 90 ? '#8b5cf6' :
                   patient.similarity_pct >= 70 ? '#6366f1' : '#4f46e5';

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold font-mono text-gray-100">{patient.patient_id}</span>
          <span className={`text-sm font-bold font-mono ${riskColor}`}>{patient.risk_level}</span>
          {patient.critical_flags.length > 0 && (
            <span className="text-sm font-mono text-red-400 bg-red-500/10 border border-red-500/25 px-2.5 py-0.5 rounded-full">
              🔴 {patient.critical_flags.length} critical
            </span>
          )}
        </div>
        <span className="text-2xl font-black font-mono text-violet-300">{patient.similarity_pct}%</span>
      </div>
      <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-1000 ease-out"
          style={{ width: `${width}%`, backgroundColor: barColor }} />
      </div>
      <div className="text-sm font-mono text-gray-500">{patient.interpretation}</div>
    </div>
  );
}

function PriorityBadge({ score, priority }: { score: number; priority: string }) {
  const cfg = {
    IMMEDIATE: { cls: 'text-red-300    bg-red-500/10    border-red-500/30',    dot: 'bg-red-400'    },
    URGENT:    { cls: 'text-orange-300 bg-orange-500/10 border-orange-500/30', dot: 'bg-orange-400' },
    MONITOR:   { cls: 'text-yellow-300 bg-yellow-500/10 border-yellow-500/30', dot: 'bg-yellow-400' },
    ROUTINE:   { cls: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/30', dot: 'bg-emerald-400' },
  }[priority] || { cls: 'text-gray-400 bg-gray-500/10 border-gray-500/25', dot: 'bg-gray-400' };
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl border text-sm font-bold font-mono ${cfg.cls}`}>
      <span className={`w-2.5 h-2.5 rounded-full ${cfg.dot}`} />
      {score.toFixed(2)} · {priority}
    </div>
  );
}

function EsTag({ label, color }: { label: string; color: string }) {
  const cls: Record<string, string> = {
    violet:  'text-violet-300  border-violet-500/40  bg-violet-500/10',
    emerald: 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10',
    cyan:    'text-cyan-300    border-cyan-500/40    bg-cyan-500/10',
    blue:    'text-blue-300    border-blue-500/40    bg-blue-500/10',
    amber:   'text-amber-300   border-amber-500/40   bg-amber-500/10',
    rose:    'text-rose-300    border-rose-500/40    bg-rose-500/10',
  };
  return (
    <span className={`text-sm font-mono font-semibold px-3 py-1.5 rounded-full border ${cls[color]}`}>
      {label}
    </span>
  );
}

export default function ScoringPanel({ patientId }: { patientId: string }) {
  const [percentile, setPercentile] = useState<any>(null);
  const [similar,    setSimilar]    = useState<SimilarPatient[]>([]);
  const [panels,     setPanels]     = useState<ScoredPanel[]>([]);
  const [popStats,   setPopStats]   = useState<PopStats | null>(null);
  const [loading,    setLoading]    = useState(true);
  const [showPop,    setShowPop]    = useState(false);
  const [error,      setError]      = useState('');

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [pctRes, simRes, panRes, popRes] = await Promise.all([
        fetch(`${API}/api/patients/${patientId}/percentile`),
        fetch(`${API}/api/patients/${patientId}/similar?k=5`),
        fetch(`${API}/api/patients/${patientId}/scored-panels?limit=6`),
        fetch(`${API}/api/analytics/population`),
      ]);
      if (pctRes.ok) setPercentile(await pctRes.json());
      if (simRes.ok) setSimilar((await simRes.json()).similar || []);
      if (panRes.ok) setPanels((await panRes.json()).panels || []);
      if (popRes.ok) setPopStats(await popRes.json());
    } catch (e: any) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [patientId]);

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-600">
      <RefreshCw className="w-5 h-5 animate-spin mr-3" />
      <span className="text-sm font-mono uppercase tracking-widest">Querying Elasticsearch…</span>
    </div>
  );

  if (error) return (
    <div className="flex items-center gap-3 text-red-400 p-5">
      <AlertCircle className="w-5 h-5" />
      <span className="text-base font-mono">{error}</span>
    </div>
  );

  return (
    <div className="space-y-5">

      {/* ── Header ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/25
            flex items-center justify-center">
            <Database className="w-5 h-5 text-violet-400" />
          </div>
          <div>
            <div className="text-lg font-bold text-gray-100">Elasticsearch Intelligence</div>
            <div className="text-xs font-mono text-gray-600 mt-0.5">lab-results · {patientId}</div>
          </div>
        </div>
        <button onClick={load}
          className="p-2 rounded-xl text-gray-600 hover:text-gray-300 hover:bg-gray-800 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* ── Percentile + Aggregations ──────────────────────── */}
      <div className="grid grid-cols-2 gap-4">

        {/* Percentile Rank */}
        <div className="rounded-2xl border border-gray-800/60 bg-gray-900/30 p-6">
          <div className="flex items-center gap-2.5 mb-5">
            <Target className="w-5 h-5 text-violet-400" />
            <span className="text-base font-bold text-gray-100">Percentile Rank</span>
            <span className="ml-auto text-xs font-mono text-gray-600">terms agg · max bucket</span>
          </div>
          {percentile ? (
            <>
              <RiskGauge percentile={percentile.percentile || 0} />
              <p className="text-sm font-mono text-gray-500 text-center mt-4 leading-relaxed">
                {percentile.interpretation}
              </p>
              <div className="mt-4 flex justify-center">
                <span className={`text-base font-bold font-mono px-5 py-2 rounded-full border ${
                  percentile.urgency === 'immediate' ? 'text-red-300    border-red-500/40    bg-red-500/10'    :
                  percentile.urgency === 'urgent'    ? 'text-orange-300 border-orange-500/40 bg-orange-500/10' :
                  percentile.urgency === 'monitor'   ? 'text-yellow-300 border-yellow-500/40 bg-yellow-500/10' :
                                                       'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
                }`}>
                  {percentile.urgency?.toUpperCase()}
                </span>
              </div>
            </>
          ) : (
            <p className="text-base text-gray-600 font-mono text-center py-10">
              Upload more PDFs to compute rank
            </p>
          )}
        </div>

        {/* Index Aggregations */}
        <div className="rounded-2xl border border-gray-800/60 bg-gray-900/30 p-6">
          <div className="flex items-center gap-2.5 mb-5">
            <BarChart3 className="w-5 h-5 text-cyan-400" />
            <span className="text-base font-bold text-gray-100">Index Aggregations</span>
            <span className="ml-auto text-xs font-mono text-gray-600">bucket · percentiles</span>
            <button onClick={() => setShowPop(o => !o)}
              className="text-gray-600 hover:text-gray-400 transition-colors ml-1">
              {showPop ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          </div>
          {popStats ? (
            <div className="space-y-3.5">
              {Object.entries(popStats.by_risk_level || {}).map(([level, count]) => {
                const total = Object.values(popStats.by_risk_level).reduce((a, b) => a + b, 0);
                const pct   = total ? Math.round((count / total) * 100) : 0;
                const color = { CRITICAL: '#ef4444', HIGH: '#f97316', MODERATE: '#eab308', LOW: '#22c55e' }[level] || '#6b7280';
                return (
                  <div key={level}>
                    <div className="flex justify-between mb-1.5">
                      <span className="text-base font-mono font-semibold text-gray-300">{level}</span>
                      <span className="text-base font-mono text-gray-400">{count} docs</span>
                    </div>
                    <div className="h-2.5 bg-gray-800 rounded-full overflow-hidden">
                      <div className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, backgroundColor: color }} />
                    </div>
                  </div>
                );
              })}
              <div className="pt-3 border-t border-gray-800/50 grid grid-cols-2 gap-3">
                <div className="text-center bg-gray-900/60 rounded-xl py-3">
                  <div className="text-2xl font-black font-mono text-gray-200">{popStats.avg_risk_score}</div>
                  <div className="text-xs font-mono text-gray-600 mt-1">avg · value agg</div>
                </div>
                <div className="text-center bg-gray-900/60 rounded-xl py-3">
                  <div className="text-2xl font-black font-mono text-red-400">{popStats.patients_with_criticals}</div>
                  <div className="text-xs font-mono text-gray-600 mt-1">critical · filter agg</div>
                </div>
              </div>
              {showPop && (
                <div className="pt-3 border-t border-gray-800/50 space-y-2">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-cyan-400/60" />
                    <p className="text-xs font-mono text-gray-500 uppercase tracking-widest">
                      Percentiles Aggregation
                    </p>
                  </div>
                  {Object.entries(popStats.risk_percentiles || {}).map(([p, v]) => (
                    <div key={p} className="flex justify-between items-center">
                      <span className="text-sm font-mono text-gray-500">p{p}</span>
                      <div className="flex-1 mx-3 h-px bg-gray-800" />
                      <span className="text-sm font-bold font-mono text-gray-300">{v?.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <p className="text-base text-gray-600 font-mono text-center py-10">No index data yet</p>
          )}
        </div>
      </div>

      {/* ── k-Nearest Neighbours ───────────────────────────── */}
      <div className="rounded-2xl border border-violet-500/25 bg-gray-900/30 p-6">
        <div className="flex items-start gap-3 mb-5">
          <GitBranch className="w-5 h-5 text-violet-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-base font-bold text-gray-100">k-Nearest Neighbours Search</span>
              <span className="text-xs font-mono text-violet-500/80 bg-violet-500/8 border border-violet-500/20
                px-2.5 py-1 rounded-full">dense_vector</span>
              <span className="text-xs font-mono text-violet-500/80 bg-violet-500/8 border border-violet-500/20
                px-2.5 py-1 rounded-full">cosine similarity</span>
              <span className="text-xs font-mono text-violet-500/80 bg-violet-500/8 border border-violet-500/20
                px-2.5 py-1 rounded-full">HNSW index</span>
            </div>
          </div>
        </div>
        {similar.length > 0 ? (
          <div className="space-y-5">
            {similar.map((s, i) => (
              <SimilarityBar key={s.patient_id} patient={s} delay={i * 150} />
            ))}
            <div className="pt-3 border-t border-gray-800/50">
              <p className="text-xs font-mono text-gray-600">
                knn · field: <span className="text-violet-400">risk_vector</span>
                {' · '}dims: <span className="text-violet-400">8</span>
                {' · '}k: <span className="text-violet-400">{similar.length}</span>
                {' · '}num_candidates: <span className="text-violet-400">50</span>
                {' · '}similarity: <span className="text-violet-400">cosine</span>
              </p>
            </div>
          </div>
        ) : (
          <p className="text-base font-mono text-gray-500 text-center py-6">
            Need 2+ patients with indexed dense_vector
          </p>
        )}
      </div>

      {/* ── function_score Query ───────────────────────────── */}
      <div className="rounded-2xl border border-emerald-500/25 bg-gray-900/30 p-6">
        <div className="flex items-start gap-3 mb-5">
          <Layers className="w-5 h-5 text-emerald-400 mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-base font-bold text-gray-100">function_score Query</span>
              <span className="text-xs font-mono text-emerald-500/80 bg-emerald-500/8 border border-emerald-500/20
                px-2.5 py-1 rounded-full">field_value_factor</span>
              <span className="text-xs font-mono text-emerald-500/80 bg-emerald-500/8 border border-emerald-500/20
                px-2.5 py-1 rounded-full">weight filter</span>
              <span className="text-xs font-mono text-emerald-500/80 bg-emerald-500/8 border border-emerald-500/20
                px-2.5 py-1 rounded-full">gauss decay</span>
            </div>
          </div>
        </div>
        {panels.length > 0 ? (
          <div className="space-y-3">
            {panels.map((p, i) => (
              <div key={i} className="flex items-center gap-4 p-4 rounded-xl
                bg-gray-800/30 border border-gray-800/50 hover:border-gray-700/70 transition-colors">
                <div className="w-9 h-9 rounded-full bg-gray-800 border border-gray-700
                  flex items-center justify-center shrink-0">
                  <span className="text-base font-bold font-mono text-gray-400">{i + 1}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-base font-mono font-semibold text-gray-200 truncate">{p.test_type}</span>
                    {p.critical_flags.length > 0 && (
                      <span className="text-sm font-mono text-red-400">🔴 {p.critical_flags.length} critical</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm font-mono text-gray-500">{p.test_date}</span>
                    <span className="text-gray-700">·</span>
                    <span className="text-sm font-mono text-gray-500">{p.result_count} nested docs</span>
                  </div>
                </div>
                <PriorityBadge score={p.es_score} priority={p.priority} />
              </div>
            ))}
            <div className="pt-3 border-t border-gray-800/50">
              <p className="text-xs font-mono text-gray-600 text-center">
                score_mode: <span className="text-gray-500">sum</span>
                {' · '}boost_mode: <span className="text-gray-500">multiply</span>
                {' · '}critical_flags weight: <span className="text-emerald-400">10×</span>
                {' · '}gauss decay: <span className="text-emerald-400">30d scale</span>
              </p>
            </div>
          </div>
        ) : (
          <p className="text-base font-mono text-gray-500 text-center py-6">No documents for {patientId}</p>
        )}
      </div>

      {/* ── ES Features ────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-800/40 bg-gray-900/10 px-6 py-5">
        <div className="flex items-center gap-2.5 mb-4">
          <Zap className="w-4 h-4 text-gray-500" />
          <p className="text-sm font-mono font-semibold text-gray-500 uppercase tracking-widest">
            Elasticsearch Features in Use
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <EsTag label="dense_vector kNN"        color="violet"  />
          <EsTag label="HNSW index"              color="violet"  />
          <EsTag label="cosine similarity"       color="rose"    />
          <EsTag label="function_score"          color="emerald" />
          <EsTag label="field_value_factor"      color="emerald" />
          <EsTag label="gauss decay"             color="emerald" />
          <EsTag label="terms aggregation"       color="cyan"    />
          <EsTag label="percentiles aggregation" color="cyan"    />
          <EsTag label="filter aggregation"      color="cyan"    />
          <EsTag label="nested query"            color="blue"    />
          <EsTag label="date_histogram"          color="blue"    />
          <EsTag label="max bucket"              color="amber"   />
        </div>
      </div>
    </div>
  );
}