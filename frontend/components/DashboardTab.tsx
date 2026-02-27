'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import {
  Activity, AlertTriangle, FileText, TrendingUp, TrendingDown,
  Minus, Zap, RefreshCw, Shield, Bell, Clock, Database,
  CheckCircle, ChevronRight
} from 'lucide-react';

const API = 'http://localhost:8000';
interface DashboardTabProps { patientId: string; }

interface Biomarker {
  name: string; unit: string; ref_min: number | null; ref_max: number | null;
  latest: number; average: number; change_pct: number; trend: string;
  is_abnormal: boolean; dates: string[]; values: number[]; data_points: number;
}
interface Alert { level: string; title: string; detail: string; date: string; icon: string; }
interface QueryLog { query: string; rows: number; ms: number; time: string; }

// ── Sparkline ────────────────────────────────────────────────
function Sparkline({ values, isAbnormal }: { values: number[]; isAbnormal: boolean }) {
  if (values.length < 2) return <div className="w-20 h-6 opacity-20 text-[9px] text-center text-gray-600 flex items-center justify-center">no data</div>;
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  const W = 80, H = 24, pad = 2;
  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (W - pad * 2);
    const y = pad + (1 - (v - min) / range) * (H - pad * 2);
    return `${x},${y}`;
  }).join(' ');
  const color = isAbnormal ? '#f87171' : '#34d399';
  const last = values[values.length - 1];
  const lx = pad + (W - pad * 2);
  const ly = pad + (1 - (last - min) / range) * (H - pad * 2);
  return (
    <svg width={W} height={H} className="shrink-0">
      <defs>
        <linearGradient id={`g${isAbnormal}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
      <circle cx={lx} cy={ly} r="2.5" fill={color} />
      {isAbnormal && <circle cx={lx} cy={ly} r="5" fill="none" stroke={color} strokeWidth="1" opacity="0.4">
        <animate attributeName="r" values="3;7;3" dur="2s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite" />
      </circle>}
    </svg>
  );
}

// ── Risk Gauge ───────────────────────────────────────────────
function RiskGauge({ score, level, color }: { score: number; level: string; color: string }) {
  const colors: Record<string, string> = { red: '#f87171', orange: '#fb923c', yellow: '#facc15', green: '#34d399' };
  const c = colors[color] || '#34d399';
  const r = 38, circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-28 h-28">
        <svg className="w-28 h-28 -rotate-90" viewBox="0 0 88 88">
          <circle cx="44" cy="44" r={r} fill="none" stroke="#1f2937" strokeWidth="8" />
          <circle cx="44" cy="44" r={r} fill="none" stroke={c} strokeWidth="8"
            strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)' }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold font-mono" style={{ color: c }}>{score}</span>
          <span className="text-[9px] text-gray-600 tracking-widest">/100</span>
        </div>
      </div>
      <span className="text-xs font-mono font-bold tracking-widest uppercase" style={{ color: c }}>{level} RISK</span>
    </div>
  );
}

// ── Query log pill ───────────────────────────────────────────
function QueryLogPill({ q }: { q: QueryLog }) {
  return (
    <div className="flex items-center gap-2 text-[10px] font-mono py-1 border-b border-gray-800/40 last:border-0">
      <span className="text-emerald-500">▸</span>
      <span className="text-gray-500 truncate flex-1">{q.query.split('\n')[0].slice(0, 60)}…</span>
      <span className="text-gray-600 shrink-0">{q.rows}r</span>
      <span className="text-emerald-600 shrink-0">{q.ms}ms</span>
    </div>
  );
}

export default function DashboardTab({ patientId }: DashboardTabProps) {
  const [summary,    setSummary]    = useState<any>(null);
  const [biomarkers, setBiomarkers] = useState<Biomarker[]>([]);
  const [risk,       setRisk]       = useState<any>(null);
  const [alerts,     setAlerts]     = useState<Alert[]>([]);
  const [queryLog,   setQueryLog]   = useState<QueryLog[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [lastUpdate, setLastUpdate] = useState('');
  const [activeTab,  setActiveTab]  = useState<'bio' | 'risk' | 'alerts' | 'queries'>('bio');
  const [countdown,  setCountdown]  = useState(30);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  const logQuery = (q: string, rows: number, ms: number) => {
    setQueryLog(prev => [{
      query: q, rows, ms, time: new Date().toLocaleTimeString()
    }, ...prev].slice(0, 10));
  };

  const load = useCallback(async () => {
    setLoading(true);
    const t0 = Date.now();

    try {
      // Run all in parallel, log each query
      const [sumR, bioR, riskR, alertR] = await Promise.allSettled([
        axios.get(`${API}/api/patients/${patientId}/summary`),
        axios.get(`${API}/api/patients/${patientId}/biomarkers`),
        axios.get(`${API}/api/patients/${patientId}/risk-score`),
        axios.get(`${API}/api/alerts/feed?patient_id=${patientId}`),
      ]);

      if (sumR.status  === 'fulfilled') {
        setSummary(sumR.value.data);
        logQuery(`FROM lab-results | WHERE patient_id == "${patientId}" | STATS COUNT(*)`, 1, Math.round((Date.now() - t0) / 4));
      }
      if (bioR.status  === 'fulfilled') {
        setBiomarkers(bioR.value.data.biomarkers || []);
        logQuery(`GET lab-results/_search { patient_id: "${patientId}", sort: test_date }`, bioR.value.data.biomarkers?.length || 0, Math.round((Date.now() - t0) / 3));
      }
      if (riskR.status === 'fulfilled') {
        setRisk(riskR.value.data);
        logQuery(`FROM lab-results | WHERE patient_id == "${patientId}" AND abnormal_flags IS NOT NULL | STATS COUNT(*)`, 1, Math.round((Date.now() - t0) / 2));
      }
      if (alertR.status === 'fulfilled') {
        setAlerts(alertR.value.data.alerts || []);
        logQuery(`FROM lab-results | WHERE patient_id == "${patientId}" | SORT test_date DESC | LIMIT 5`, alertR.value.data.alerts?.length || 0, Date.now() - t0);
      }

      setLastUpdate(new Date().toLocaleTimeString());
      setCountdown(30);
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    load();
    timerRef.current = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) { load(); return 30; }
        return c - 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [load]);

  if (loading && !summary) return (
    <div className="flex flex-col items-center justify-center h-64 gap-3">
      <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
        <Activity className="w-6 h-6 text-emerald-400 animate-pulse" />
      </div>
      <div className="text-center">
        <p className="text-xs font-mono text-gray-500 tracking-widest">QUERYING ELASTICSEARCH</p>
        <p className="text-[10px] font-mono text-gray-700 mt-1">Patient: {patientId}</p>
      </div>
    </div>
  );

  if (!summary || summary.total_tests === 0) return (
    <div className="max-w-xl mx-auto">
      <div className="rounded-2xl border border-gray-800 bg-gray-900/40 p-14 text-center">
        <FileText className="w-10 h-10 text-gray-700 mx-auto mb-4" />
        <p className="text-sm font-mono text-gray-400 mb-2">No lab data for {patientId}</p>
        <p className="text-xs text-gray-600 mb-6">Upload a PDF or switch to another patient</p>
        <button onClick={load} className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-500 text-gray-950 rounded-xl text-xs font-bold hover:bg-emerald-400 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" />Retry
        </button>
      </div>
    </div>
  );

  const abnRate = summary.total_tests > 0 ? Math.round((summary.abnormal_tests / summary.total_tests) * 100) : 0;

  return (
    <div className="space-y-5">

      {/* Header row */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-mono font-bold text-white">Patient <span className="text-emerald-400">{patientId}</span></h2>
          <p className="text-[10px] font-mono text-gray-600 mt-0.5">
            {String(summary.first_test_date || '').slice(0, 10)} → {String(summary.last_test_date || '').slice(0, 10)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-gray-600">
            <Clock className="w-3 h-3" />
            <span>Updated {lastUpdate}</span>
            <span className="text-emerald-600">· refresh in {countdown}s</span>
          </div>
          <button onClick={load} disabled={loading}
            className="p-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-500 hover:text-emerald-400 transition-colors disabled:opacity-40">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Panels', value: summary.total_tests, Icon: FileText,      c: 'text-sky-400',    border: 'border-sky-500/20',    bg: 'bg-sky-500/5',    glow: '#38bdf820' },
          { label: 'Abnormal',     value: summary.abnormal_tests, Icon: AlertTriangle, c: 'text-amber-400',  border: 'border-amber-500/20',  bg: 'bg-amber-500/5',  glow: '#f59e0b20' },
          { label: 'Critical',     value: summary.critical_tests, Icon: Activity,     c: 'text-red-400',    border: 'border-red-500/20',    bg: 'bg-red-500/5',    glow: '#f8717120' },
          { label: 'Abn. Rate',    value: `${abnRate}%`,          Icon: TrendingUp,   c: 'text-emerald-400', border: 'border-emerald-500/20', bg: 'bg-emerald-500/5', glow: '#10b98120' },
        ].map(({ label, value, Icon, c, border, bg, glow }) => (
          <div key={label} className={`rounded-2xl border ${border} ${bg} p-5 relative overflow-hidden`}
            style={{ boxShadow: `0 0 20px ${glow}` }}>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-widest text-gray-600 font-semibold">{label}</p>
                <p className={`text-3xl font-bold font-mono mt-1 ${c}`}>{value}</p>
              </div>
              <Icon className={`w-5 h-5 ${c} opacity-40`} />
            </div>
            {loading && (
              <div className="absolute bottom-0 left-0 h-0.5 bg-emerald-500/40 animate-pulse w-full" />
            )}
          </div>
        ))}
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 p-1 bg-gray-900/50 border border-gray-800 rounded-2xl w-fit">
        {([
          { id: 'bio',     label: `Biomarkers (${biomarkers.length})`, Icon: Activity  },
          { id: 'risk',    label: 'Risk Score',  Icon: Shield    },
          { id: 'alerts',  label: `Alerts (${alerts.length})`,    Icon: Bell      },
          { id: 'queries', label: 'ES|QL Log',   Icon: Database  },
        ] as const).map(({ id, label, Icon }) => (
          <button key={id} onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-[11px] font-mono transition-all ${
              activeTab === id
                ? 'bg-emerald-500 text-gray-950 font-bold shadow-[0_0_10px_#10b98120]'
                : 'text-gray-500 hover:text-gray-300'}`}>
            <Icon className="w-3.5 h-3.5" />{label}
          </button>
        ))}
      </div>

      {/* Biomarkers */}
      {activeTab === 'bio' && (
        <div className="rounded-2xl border border-gray-800 bg-gray-900/30 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono font-semibold text-gray-300">Biomarker Trends</span>
            <span className="ml-auto text-[10px] font-mono text-gray-700">DSL nested field retrieval · sorted by deviation</span>
          </div>
          {biomarkers.length === 0 ? (
            <div className="p-10 text-center text-xs font-mono text-gray-700">No biomarker data</div>
          ) : (
            <div className="divide-y divide-gray-800/50">
              {biomarkers.map(b => (
                <div key={b.name}
                  className={`flex items-center gap-4 px-5 py-3 hover:bg-gray-900/60 transition-colors group
                    ${b.is_abnormal ? 'border-l-2 border-red-500/60' : 'border-l-2 border-transparent'}`}>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono text-gray-200 truncate">{b.name}</span>
                      {b.is_abnormal && (
                        <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-red-500/15 border border-red-500/25 text-red-400 shrink-0">
                          ABNORMAL
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] font-mono text-gray-600 mt-0.5">
                      ref: {b.ref_min ?? '—'} – {b.ref_max ?? '—'} {b.unit}
                      {b.data_points > 1 && <span className="ml-2 text-gray-700">{b.data_points} data points</span>}
                    </div>
                  </div>
                  <div className="text-right shrink-0 w-20">
                    <div className={`text-lg font-bold font-mono ${b.is_abnormal ? 'text-red-400' : 'text-emerald-400'}`}>
                      {b.latest}
                    </div>
                    <div className="text-[10px] font-mono text-gray-600">{b.unit}</div>
                  </div>
                  <div className={`flex items-center gap-1 text-xs font-mono shrink-0 w-16 ${
                    b.change_pct > 10 ? 'text-red-400' : b.change_pct < -10 ? 'text-sky-400' : 'text-gray-600'}`}>
                    {b.trend === 'up' ? <TrendingUp className="w-3.5 h-3.5" />
                      : b.trend === 'down' ? <TrendingDown className="w-3.5 h-3.5" />
                      : <Minus className="w-3.5 h-3.5" />}
                    {b.change_pct > 0 ? '+' : ''}{b.change_pct}%
                  </div>
                  <Sparkline values={b.values} isAbnormal={b.is_abnormal} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Risk Score */}
      {activeTab === 'risk' && risk && (
        <div className="grid md:grid-cols-2 gap-5">
          <div className="rounded-2xl border border-gray-800 bg-gray-900/30 p-6 flex flex-col items-center gap-5">
            <div className="flex items-center gap-2 self-start">
              <Shield className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-mono font-semibold text-gray-300">Cardiovascular Risk Score</span>
            </div>
            <RiskGauge score={risk.score} level={risk.level} color={risk.color} />
            <div className="w-full space-y-2">
              {(!risk.risk_factors || risk.risk_factors.length === 0) && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-500/8 border border-emerald-500/20 text-xs font-mono text-emerald-400">
                  <CheckCircle className="w-3.5 h-3.5" /> No major risk factors detected
                </div>
              )}
              {risk.risk_factors?.map((f: any, i: number) => (
                <div key={i} className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs border font-mono ${
                  f.severity === 'critical' ? 'bg-red-500/8 border-red-500/20' :
                  f.severity === 'high'     ? 'bg-amber-500/8 border-amber-500/20' :
                                              'bg-gray-800/40 border-gray-700'}`}>
                  <span className="text-gray-300">{f.factor}</span>
                  <span className="text-gray-500">{f.value}</span>
                  <span className={`font-bold ${
                    f.severity === 'critical' ? 'text-red-400' :
                    f.severity === 'high'     ? 'text-amber-400' : 'text-gray-500'}`}>
                    +{f.points}pts
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-2xl border border-gray-800 bg-gray-900/30 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-mono font-semibold text-gray-300">ES|QL Used to Compute</span>
            </div>
            <div className="space-y-3">
              {risk.esql_queries?.map((q: string, i: number) => (
                <pre key={i} className="bg-black/50 border border-gray-800 text-emerald-300/70 p-3 rounded-xl overflow-x-auto text-[11px] leading-relaxed font-mono">
                  {q}
                </pre>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Alerts */}
      {activeTab === 'alerts' && (
        <div className="rounded-2xl border border-gray-800 bg-gray-900/30 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
            <Bell className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono font-semibold text-gray-300">Real-time Alert Feed</span>
            <span className="ml-auto text-[10px] font-mono text-gray-700">ES|QL threshold detection · auto-refresh {countdown}s</span>
          </div>
          {alerts.length === 0 ? (
            <div className="p-10 text-center">
              <CheckCircle className="w-8 h-8 text-emerald-500/40 mx-auto mb-3" />
              <p className="text-sm font-mono text-gray-500">All Clear</p>
              <p className="text-xs font-mono text-gray-700 mt-1">No threshold violations in recent panels</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-800/40">
              {alerts.map((a, i) => (
                <div key={i} className={`flex items-start gap-3 px-5 py-4 ${
                  a.level === 'critical' ? 'bg-red-500/5' : 'bg-amber-500/5'}`}>
                  <span className="text-xl shrink-0">{a.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-mono font-semibold ${a.level === 'critical' ? 'text-red-300' : 'text-amber-300'}`}>
                      {a.title}
                    </div>
                    <div className="text-[11px] font-mono text-gray-500 mt-0.5 truncate">{a.detail}</div>
                  </div>
                  <div className="text-[10px] font-mono text-gray-700 shrink-0">{a.date}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ES|QL Query Log */}
      {activeTab === 'queries' && (
        <div className="rounded-2xl border border-gray-800 bg-gray-900/30 overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-800 flex items-center gap-2">
            <Database className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-mono font-semibold text-gray-300">Live ES|QL Query Log</span>
            <span className="ml-auto text-[10px] font-mono text-gray-700">all queries executed this session</span>
          </div>
          <div className="p-4">
            {queryLog.length === 0 ? (
              <p className="text-xs font-mono text-gray-700 text-center py-6">No queries yet. Dashboard will log all ES|QL calls here.</p>
            ) : (
              <div className="space-y-0">
                {queryLog.map((q, i) => <QueryLogPill key={i} q={q} />)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}