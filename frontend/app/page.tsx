'use client';

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Activity, Upload, MessageSquare, LayoutDashboard,
  RefreshCw, Zap, ChevronDown, Users,Terminal, Globe ,
  Database, AlertTriangle, X, WifiOff
} from 'lucide-react';
import ChatTab      from '@/components/ChatTab';
import DashboardTab from '@/components/DashboardTab';
import UploadTab    from '@/components/UploadTab';
import EsqlTab   from '@/components/EsqlTab';
import ScoringPanel from '@/components/ScoringPanel';
const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const TABS = [
  { id: 'dashboard', label: 'Dashboard',  Icon: LayoutDashboard },
  { id: 'chat',      label: 'AI Agent',   Icon: MessageSquare   },
  { id: 'esql',      label: 'ES|QL',      Icon: Terminal        },
  { id: 'elastic',    label: 'Elastic',     Icon: Globe           },
  { id: 'upload',    label: 'Upload PDF', Icon: Upload          },
] as const;
type TabId = (typeof TABS)[number]['id'];

interface Patient {
  patient_id: string;
  total_tests: number;
  abnormal: number;
  critical: number;
  last_test: string;
  first_test: string;
}
interface SysStatus {
  es_connected: boolean;
  doc_count: number;
  mcp_enabled: boolean;
  latency_ms: number;
  last_checked: string;
}

export default function App() {
  const [tab,             setTab]             = useState<TabId>('dashboard');
  const [patientId,       setPatientId]       = useState('PAT001');
  const [patients,        setPatients]        = useState<Patient[]>([]);
  const [patientsLoading, setPatientsLoading] = useState(true);
  const [showMenu,        setShowMenu]        = useState(false);
  const [customInput,     setCustomInput]     = useState('');
  const [status,          setStatus]          = useState<SysStatus | null>(null);
  const [esqlFeed,        setEsqlFeed]        = useState<{label: string; ms: number; rows: number}[]>([]);
  const [refreshKey,      setRefreshKey]      = useState(0);
  const [criticalAlert,   setCriticalAlert]   = useState<string | null>(null);

  useEffect(() => {
    const reqId = axios.interceptors.request.use(config => {
      const url = (config.url || '').replace(API, '').split('?')[0];
      if (url.startsWith('/api/') && !url.includes('health')) {
        setEsqlFeed(prev => [{ label: url, ms: 0, rows: 0 }, ...prev].slice(0, 6));
      }
      return config;
    });
    const resId = axios.interceptors.response.use(response => {
      const url = (response.config.url || '').replace(API, '').split('?')[0];
      if (url.startsWith('/api/') && !url.includes('health')) {
        const rows = response.data?.row_count ?? response.data?.total
          ?? response.data?.biomarkers?.length ?? response.data?.alerts?.length ?? 0;
        const ms = response.data?.esql_ms ?? response.data?.ms ?? response.data?.execution_ms ?? 0;
        setEsqlFeed(prev => {
          const copy = [...prev];
          if (copy.length && copy[0].label === url) copy[0] = { label: url, ms, rows };
          return copy;
        });
      }
      return response;
    });
    return () => {
      axios.interceptors.request.eject(reqId);
      axios.interceptors.response.eject(resId);
    };
  }, []);

  const checkStatus = useCallback(async () => {
    const t0 = Date.now();
    try {
      const { data } = await axios.get(`${API}/health`);
      setStatus({
        es_connected: data.elasticsearch === 'connected',
        doc_count:    data.lab_results_count ?? 0,
        mcp_enabled:  data.mcp_enabled ?? false,
        latency_ms:   Date.now() - t0,
        last_checked: new Date().toLocaleTimeString(),
      });
    } catch {
      setStatus(s => s ? { ...s, es_connected: false } : null);
    }
  }, []);

  const loadPatients = useCallback(async () => {
    setPatientsLoading(true);
    try {
      const { data } = await axios.get(`${API}/api/patients`);
      const rows: Patient[] = (data.patients || []).map((r: any) => ({
        patient_id:  r.patient_id,
        total_tests: r.total_tests ?? 0,
        abnormal:    r.abnormal   ?? 0,
        critical:    r.critical   ?? 0,
        last_test:   String(r.last_test  || '').slice(0, 10),
        first_test:  String(r.first_test || '').slice(0, 10),
      }));
      setPatients(rows);
      if (rows.length && !rows.find(p => p.patient_id === patientId)) {
        setPatientId(rows[0].patient_id);
      }
      const current = rows.find(p => p.patient_id === patientId);
      setCriticalAlert(current && current.critical > 0
        ? `Patient ${patientId} has ${current.critical} critical lab panels — immediate review needed`
        : null);
    } catch { /* backend not up */ }
    finally { setPatientsLoading(false); }
  }, [patientId]);

  useEffect(() => {
    checkStatus();
    loadPatients();
    const iv = setInterval(() => { checkStatus(); loadPatients(); }, 20_000);
    return () => clearInterval(iv);
  }, [checkStatus, loadPatients]);

  const switchPatient = (id: string) => {
    setPatientId(id); setShowMenu(false);
    setCustomInput(''); setRefreshKey(k => k + 1);
  };

  const handleUploadSuccess = () => {
    loadPatients();
    setTimeout(() => { setRefreshKey(k => k + 1); setTab('dashboard'); }, 800);
  };

  const current = patients.find(p => p.patient_id === patientId);

  return (
    <div className="min-h-screen bg-[#07090f] text-gray-200 flex flex-col"
      style={{ fontFamily: "'IBM Plex Mono','Courier New',monospace" }}>

      {/* ── TOP HEADER ─────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-[#090d1a]/95 backdrop-blur border-b border-gray-700/40">
        <div className="max-w-screen-2xl mx-auto px-5 py-3 flex items-center gap-4 justify-between">

          {/* Logo — bigger and more visible */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30
              flex items-center justify-center">
              <Activity className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="leading-none">
              <div className="text-[15px] font-bold tracking-widest text-white">
                LAB<span className="text-emerald-400">IQ</span>
              </div>
              <div className="text-[10px] text-gray-500 tracking-widest mt-0.5">
                ELASTIC AGENT BUILDER
              </div>
            </div>
          </div>

          {/* Patient Switcher */}
          <div className="relative ml-1">
            <button onClick={() => setShowMenu(m => !m)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-900/80
                border border-gray-700 hover:border-emerald-500/50 transition-all text-sm group">
              <Users className="w-3.5 h-3.5 text-gray-500 group-hover:text-emerald-400 transition-colors shrink-0" />
              <span className="font-bold text-emerald-400 tracking-wider">{patientId}</span>
              {current && (
                <>
                  <span className="text-gray-600 mx-0.5">·</span>
                  <span className="text-gray-400 text-xs">{current.total_tests} panels</span>
                  {current.abnormal > 0 && <span className="text-amber-400 text-xs">⚠{current.abnormal}</span>}
                  {current.critical > 0 && <span className="text-red-400 text-xs">🚨{current.critical}</span>}
                </>
              )}
              <ChevronDown className="w-3.5 h-3.5 text-gray-500 ml-0.5" />
            </button>

            {showMenu && (
              <div className="absolute top-full left-0 mt-2 w-[320px] rounded-2xl border border-gray-700
                bg-[#0c1020]/98 backdrop-blur-lg shadow-2xl z-50 overflow-hidden">
                <div className="px-4 py-3 bg-gray-900/60 border-b border-gray-700/60 flex items-center gap-2">
                  <Database className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-[11px] text-gray-400 tracking-wide">
                    {patientsLoading ? 'Querying Elasticsearch…'
                      : `${patients.length} patient${patients.length !== 1 ? 's' : ''} in index`}
                  </span>
                  <button onClick={loadPatients} className="ml-auto text-gray-500 hover:text-emerald-400 transition-colors">
                    <RefreshCw className={`w-3.5 h-3.5 ${patientsLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
                <div className="max-h-64 overflow-y-auto divide-y divide-gray-800/50">
                  {!patientsLoading && patients.length === 0 && (
                    <div className="px-4 py-8 text-center text-sm text-gray-500">
                      No patients yet.<br />
                      <span className="text-xs text-gray-600">Upload a lab report to get started.</span>
                    </div>
                  )}
                  {patients.map(p => (
                    <button key={p.patient_id} onClick={() => switchPatient(p.patient_id)}
                      className={`w-full flex items-center justify-between px-4 py-3 text-left
                        hover:bg-emerald-500/5 transition-colors
                        ${p.patient_id === patientId
                          ? 'bg-emerald-500/8 border-l-2 border-l-emerald-500/60'
                          : 'border-l-2 border-l-transparent'}`}>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-bold ${
                            p.patient_id === patientId ? 'text-emerald-400' : 'text-gray-200'
                          }`}>{p.patient_id}</span>
                          {p.patient_id === patientId && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-500/15
                              border border-emerald-500/25 text-emerald-400 tracking-widest">ACTIVE</span>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-500 mt-0.5">
                          {p.first_test} → {p.last_test}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-mono text-gray-400">{p.total_tests} panels</div>
                        <div className="flex gap-2 justify-end mt-0.5">
                          {p.abnormal > 0 && <span className="text-xs text-amber-400">⚠{p.abnormal}</span>}
                          {p.critical > 0 && <span className="text-xs text-red-400">🚨{p.critical}</span>}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
                <div className="px-3 py-3 border-t border-gray-700/60 bg-gray-900/40 flex gap-2">
                  <input value={customInput}
                    onChange={e => setCustomInput(e.target.value.toUpperCase())}
                    placeholder="Type patient ID manually…"
                    className="flex-1 px-3 py-2 text-xs bg-gray-800/80 border border-gray-700
                      rounded-lg text-gray-200 placeholder:text-gray-500 focus:outline-none
                      focus:border-emerald-500/50 font-mono tracking-widest"
                    onKeyDown={e => e.key === 'Enter' && customInput.trim() && switchPatient(customInput.trim())}
                  />
                  <button onClick={() => customInput.trim() && switchPatient(customInput.trim())}
                    className="px-3 py-2 bg-emerald-500 text-gray-950 rounded-lg text-xs font-bold
                      hover:bg-emerald-400 transition-colors">
                    Go
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Live ES|QL feed */}
          <div className="hidden xl:flex items-center gap-2 flex-1 min-w-0 mx-3">
            <Zap className="w-3.5 h-3.5 text-emerald-500/40 shrink-0" />
            <div className="flex gap-1.5 overflow-hidden items-center">
              {esqlFeed.length === 0
                ? <span className="text-[11px] text-gray-600">awaiting ES|QL queries…</span>
                : esqlFeed.slice(0, 4).map((f, i) => (
                  <span key={i} className={`text-[11px] font-mono px-2.5 py-0.5 rounded-full border
                    whitespace-nowrap transition-all ${
                    i === 0
                      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/25'
                      : 'text-gray-500 bg-transparent border-gray-800'
                  }`}>
                    {f.label.replace('/api/', '')}
                    {f.ms > 0 ? ` · ${f.ms}ms` : ''}
                    {f.rows > 0 ? ` · ${f.rows}r` : ''}
                  </span>
                ))
              }
            </div>
          </div>

          {/* System status */}
          <div className="flex items-center gap-3 ml-auto shrink-0">
            {status && (
              <div className="hidden md:flex items-center gap-3 text-[11px] font-mono">
                {status.es_connected
                  ? <span className="flex items-center gap-1.5 text-emerald-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400
                        shadow-[0_0_5px_#34d399] animate-pulse" />
                      ES Online
                    </span>
                  : <span className="flex items-center gap-1.5 text-red-400">
                      <WifiOff className="w-3.5 h-3.5" />ES Offline
                    </span>
                }
                <span className="text-gray-400">{status.doc_count} docs</span>
                <span className="text-gray-500">{status.latency_ms}ms</span>
                {status.mcp_enabled && (
                  <span className="text-emerald-400 bg-emerald-500/10 border border-emerald-500/25
                    px-2 py-0.5 rounded-full">MCP●</span>
                )}
              </div>
            )}
            <button
              onClick={() => { checkStatus(); loadPatients(); setRefreshKey(k => k + 1); }}
              title="Refresh all data"
              className="p-2 rounded-lg hover:bg-gray-800 text-gray-500
                hover:text-emerald-400 transition-colors">
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="max-w-screen-2xl mx-auto px-5 flex border-t border-gray-800/40">
          {TABS.map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTab(id)}
              className={`flex items-center gap-2 px-6 py-3 text-[12px] font-mono tracking-widest
                border-b-2 transition-all ${
                tab === id
                  ? 'border-emerald-400 text-emerald-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300 hover:border-gray-600'
              }`}>
              <Icon className="w-3.5 h-3.5" />
              {label.toUpperCase()}
            </button>
          ))}
        </div>
      </header>

      {/* Critical alert */}
      {criticalAlert && (
        <div className="bg-red-500/8 border-b border-red-500/25">
          <div className="max-w-screen-2xl mx-auto px-5 py-2.5 flex items-center gap-3">
            <AlertTriangle className="w-4 h-4 text-red-400 animate-pulse shrink-0" />
            <span className="text-sm font-mono text-red-300">{criticalAlert}</span>
            <button onClick={() => setTab('chat')}
              className="ml-3 text-xs font-mono text-red-400 hover:text-red-300
                underline underline-offset-2">
              Review with AI →
            </button>
            <button onClick={() => setCriticalAlert(null)}
              className="ml-auto text-red-700 hover:text-red-400 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Main */}
<main className="flex-1 max-w-screen-2xl mx-auto w-full px-5 py-5">

  {tab === 'dashboard' && (
    <DashboardTab
      key={`dash-${patientId}-${refreshKey}`}
      patientId={patientId}
    />
  )}

  {tab === 'chat' && (
    <ChatTab
      key={`chat-${patientId}`}
      patientId={patientId}
    />
  )}

  {tab === 'upload' && (
    <UploadTab
      patientId={patientId}
      onSuccess={handleUploadSuccess}
      onPatientIdChange={setPatientId}
    />
  )}

  {tab === 'esql' && (
    <EsqlTab />
  )}

  {tab === 'elastic' && (
    <ScoringPanel patientId={patientId} />
  )}
  

</main>

      <footer className="border-t border-gray-800/30 px-5 py-2.5">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between text-[10px] font-mono text-gray-600">
          <span>LABIQ · ELASTIC AGENT BUILDER HACKATHON · REAL-TIME ES|QL · MCP PROTOCOL</span>
          {status && <span>LAST SYNC {status.last_checked}</span>}
        </div>
      </footer>

      {showMenu && <div className="fixed inset-0 z-30" onClick={() => setShowMenu(false)} />}
    </div>
  );
}