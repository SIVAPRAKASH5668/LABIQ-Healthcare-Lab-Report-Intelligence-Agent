'use client';

import { useState } from 'react';
import { ExternalLink, Bot, Zap, LayoutDashboard, RefreshCw, AlertCircle, Globe } from 'lucide-react';

// Add to your .env.local:
// NEXT_PUBLIC_KIBANA_URL=https://my-elasticsearch-project-b7649b.kb.us-east1.gcp.elastic.cloud
const KIBANA_BASE = process.env.NEXT_PUBLIC_KIBANA_URL || '';
console.log("KIBANA:", process.env.NEXT_PUBLIC_KIBANA_URL);
const VIEWS = [
  {
    id:    'agent',
    label: 'AI Agent',
    Icon:  Bot,
    desc:  'Kibana Agent Builder — same LLM powering your chat',
    path:  '/app/agent_builder',
  },
  {
    id:    'discover',
    label: 'Discover',
    Icon:  Zap,
    desc:  'Browse the lab-results index live',
    path:  '/app/discover',
  },
  {
    id:    'dashboards',
    label: 'Dashboards',
    Icon:  LayoutDashboard,
    desc:  'ES|QL-powered visualizations',
    path:  '/app/dashboards',
  },
];

export default function KibanaTab() {
  const [active,  setActive]  = useState(0);
  const [loading, setLoading] = useState(true);
  const [blocked, setBlocked] = useState(false);
  const [key,     setKey]     = useState(0);

  const view    = VIEWS[active];
  const fullUrl = KIBANA_BASE ? `${KIBANA_BASE}${view.path}` : '';

  const switchView = (i: number) => {
    setActive(i); setLoading(true); setBlocked(false); setKey(k => k + 1);
  };

  const reload = () => { setLoading(true); setBlocked(false); setKey(k => k + 1); };

  // No URL configured
  if (!KIBANA_BASE) {
    return (
      <div className="max-w-xl mx-auto mt-24 text-center space-y-5">
        <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/20
          flex items-center justify-center mx-auto">
          <AlertCircle className="w-7 h-7 text-amber-400" />
        </div>
        <h2 className="text-base font-semibold text-white">Kibana URL not configured</h2>
        <p className="text-sm text-gray-400">
          Add this to your <code className="text-emerald-400 bg-emerald-500/8 px-1.5 py-0.5 rounded">
          .env.local</code> file and restart:
        </p>
        <div className="bg-black/40 border border-gray-800/60 rounded-xl px-5 py-4 text-left space-y-2">
          <p className="text-[10px] font-mono text-gray-600 uppercase tracking-widest">.env.local</p>
          <code className="block text-sm font-mono text-emerald-300 break-all">
            NEXT_PUBLIC_KIBANA_URL=https://my-elasticsearch-project-b7649b.kb.us-east1.gcp.elastic.cloud
          </code>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-160px)] gap-3">

      {/* Toolbar */}
      <div className="flex items-center gap-3 shrink-0">

        {/* View tabs */}
        <div className="flex p-1 bg-gray-900/50 border border-gray-800/60 rounded-xl gap-1">
          {VIEWS.map(({ id, label, Icon }, i) => (
            <button key={id} onClick={() => switchView(i)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs
                font-mono transition-all ${
                active === i
                  ? 'bg-emerald-500/12 border border-emerald-500/20 text-emerald-400'
                  : 'text-gray-500 hover:text-gray-300'
              }`}>
              <Icon className="w-3.5 h-3.5" />{label}
            </button>
          ))}
        </div>

        <span className="text-[10px] font-mono text-gray-600 hidden md:block">
          {view.desc}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <button onClick={reload}
            className="p-2 rounded-lg text-gray-600 hover:text-emerald-400
              hover:bg-gray-800 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <a href={fullUrl} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-mono
              border border-gray-800/60 text-gray-500 hover:text-gray-200
              hover:border-gray-700 transition-all">
            <ExternalLink className="w-3.5 h-3.5" />Open in Kibana
          </a>
        </div>
      </div>

      {/* URL bar */}
      <div className="flex items-center gap-2.5 px-3 py-2 rounded-xl bg-black/30
        border border-gray-800/50 shrink-0">
        <div className="flex gap-1.5">
          <div className="w-2 h-2 rounded-full bg-red-500/50" />
          <div className="w-2 h-2 rounded-full bg-amber-500/50" />
          <div className="w-2 h-2 rounded-full bg-emerald-500/50" />
        </div>
        <Globe className="w-3 h-3 text-gray-700 ml-1" />
        <span className="text-[11px] font-mono text-gray-500 truncate flex-1">{fullUrl}</span>
        {loading && !blocked && (
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse shrink-0" />
        )}
        {!loading && !blocked && (
          <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0" />
        )}
      </div>

      {/* iframe area */}
      <div className="flex-1 rounded-2xl border border-gray-800/60 overflow-hidden
        relative bg-black/10 min-h-0">

        {/* Loading overlay */}
        {loading && !blocked && (
          <div className="absolute inset-0 z-10 bg-[#07090f] flex flex-col
            items-center justify-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20
              flex items-center justify-center">
              <Zap className="w-5 h-5 text-emerald-400 animate-pulse" />
            </div>
            <p className="text-sm text-gray-500 font-mono">Loading {view.label}…</p>
          </div>
        )}

        {/* Blocked by X-Frame-Options fallback */}
        {blocked ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 text-center px-10">
            <div className="w-14 h-14 rounded-2xl bg-amber-500/8 border border-amber-500/20
              flex items-center justify-center">
              <Globe className="w-7 h-7 text-amber-400" />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-semibold text-gray-200">
                Kibana blocks iframe embedding
              </p>
              <p className="text-xs text-gray-500 font-mono max-w-md">
                Elastic Cloud sets <code className="text-amber-400/70">X-Frame-Options: SAMEORIGIN</code> by
                default. You can still use all Kibana features directly.
              </p>
            </div>
            <div className="flex flex-col items-center gap-3">
              <a href={fullUrl} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-6 py-3 bg-emerald-500 text-gray-950
                  rounded-xl font-bold text-sm hover:bg-emerald-400 transition-all
                  shadow-[0_0_20px_#10b98125]">
                <ExternalLink className="w-4 h-4" />
                Open {view.label} in Kibana
              </a>
              <div className="flex gap-2">
                {VIEWS.map(({ label, path }, i) => (
                  <a key={i}
                    href={`${KIBANA_BASE}${path}`}
                    target="_blank" rel="noopener noreferrer"
                    className="text-[11px] font-mono px-3 py-1.5 border border-gray-700
                      rounded-lg text-gray-400 hover:text-gray-200 hover:border-gray-600
                      transition-colors">
                    {label} ↗
                  </a>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <iframe
            key={key}
            src={fullUrl}
            className="w-full h-full border-0"
            title={`Kibana ${view.label}`}
            onLoad={() => setLoading(false)}
            onError={() => { setLoading(false); setBlocked(true); }}
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-top-navigation"
          />
        )}
      </div>
    </div>
  );
}