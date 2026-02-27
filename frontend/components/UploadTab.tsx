'use client';

import { useState, useCallback } from 'react';
import axios from 'axios';
import {
  Upload, FileText, CheckCircle, AlertCircle,
  Loader2, Zap, Database, FlaskConical,
  TrendingUp, AlertTriangle, ArrowRight
} from 'lucide-react';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface UploadTabProps {
  patientId: string;
  onSuccess: () => void;
  onPatientIdChange: (id: string) => void;
  onGoToEsql?: () => void;
}

export default function UploadTab({ patientId, onSuccess, onPatientIdChange, onGoToEsql }: UploadTabProps) {
  const [file,      setFile]      = useState<File | null>(null);
  const [dragging,  setDragging]  = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result,    setResult]    = useState<any>(null);
  const [error,     setError]     = useState<string | null>(null);
  const [localId,   setLocalId]   = useState(patientId);

  const handleFile = (f: File) => {
    if (!f.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported'); return;
    }
    setFile(f); setResult(null); setError(null);
  };

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true); setError(null); setResult(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('patient_id', localId.trim().toUpperCase() || 'PAT001');
      const { data } = await axios.post(`${API}/api/upload-lab-report`, fd,
        { headers: { 'Content-Type': 'multipart/form-data' } });
      setResult(data);
      onPatientIdChange(data.patient_id);
      onSuccess();
    } catch (e: any) {
      setError(e.response?.data?.detail || e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const PIPELINE = [
    { Icon: FileText,     label: 'PDF Extraction',      sub: 'pdfplumber parses raw text'               },
    { Icon: FlaskConical, label: 'Lab Result Parsing',  sub: 'Regex extracts test values & refs'        },
    { Icon: TrendingUp,   label: 'Severity Flagging',   sub: 'Critical / abnormal threshold detection'  },
    { Icon: Database,     label: 'Elasticsearch Index', sub: 'Nested document stored to lab-results'    },
    { Icon: Zap,          label: 'ES|QL Ready',         sub: 'Agent Builder tools can query now'        },
  ];

  return (
    <div className="w-full h-full">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">

        {/* ── LEFT COLUMN: Upload card ─────────────────── */}
        <div className="rounded-2xl border border-gray-800/60 bg-gray-900/20 overflow-hidden flex flex-col">

          {/* Header */}
          <div className="px-8 py-5 border-b border-gray-800/60 flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20
              flex items-center justify-center shrink-0">
              <Upload className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <div className="text-lg font-semibold text-gray-200">Upload Lab Report</div>
              <div className="text-xs text-gray-500 font-mono mt-0.5">
                PDF → Extract → Index → Query
              </div>
            </div>
          </div>

          <div className="p-8 space-y-6 flex-1 flex flex-col">

            {/* Patient ID */}
            <div>
              <label className="block text-xs font-mono text-gray-500 uppercase tracking-widest mb-2">
                Patient ID
              </label>
              <div className="relative">
                <input
                  value={localId}
                  onChange={e => setLocalId(e.target.value.toUpperCase())}
                  placeholder="PAT001"
                  className="w-full px-5 py-3.5 bg-gray-800/60 border border-gray-700/60 rounded-xl
                    text-xl text-emerald-400 font-mono tracking-widest placeholder:text-gray-600
                    focus:outline-none focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/10
                    transition-colors"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2
                  text-[10px] font-mono text-gray-600 tracking-wider">
                  PATIENT
                </span>
              </div>
              <p className="text-xs font-mono text-gray-600 mt-2">
                Creates new patient if ID doesn't exist in index
              </p>
            </div>

            {/* Drop zone — grows to fill space */}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onClick={() => !file && document.getElementById('file-upload')?.click()}
              className={`relative rounded-2xl border-2 border-dashed flex-1 min-h-[220px]
                flex flex-col items-center justify-center p-12 text-center
                transition-all select-none ${
                dragging ? 'border-emerald-400/60 bg-emerald-500/8 scale-[1.01] cursor-copy' :
                file     ? 'border-emerald-500/30 bg-emerald-500/4 cursor-default' :
                           'border-gray-700/60 hover:border-gray-600 hover:bg-gray-900/30 cursor-pointer'
              }`}>
              <input type="file" accept=".pdf" id="file-upload" className="hidden"
                onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />

              {file ? (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/20
                    flex items-center justify-center">
                    <FileText className="w-8 h-8 text-emerald-400" />
                  </div>
                  <div>
                    <p className="text-base font-semibold text-gray-200">{file.name}</p>
                    <p className="text-sm font-mono text-gray-500 mt-1">
                      {(file.size / 1024).toFixed(1)} KB · PDF ready to index
                    </p>
                  </div>
                  <label htmlFor="file-upload" onClick={e => e.stopPropagation()}
                    className="text-sm font-mono text-gray-600 hover:text-emerald-400
                      cursor-pointer transition-colors underline underline-offset-2">
                    Change file
                  </label>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-gray-800/60 border border-gray-700/60
                    flex items-center justify-center">
                    <Upload className="w-8 h-8 text-gray-500" />
                  </div>
                  <div>
                    <p className="text-base font-medium text-gray-300">
                      Drop your PDF here or{' '}
                      <label htmlFor="file-upload" onClick={e => e.stopPropagation()}
                        className="text-emerald-400 hover:text-emerald-300 cursor-pointer transition-colors">
                        browse files
                      </label>
                    </p>
                    <p className="text-sm text-gray-600 mt-1.5 font-mono">
                      Lab reports · Blood panels · Metabolic panels
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Upload button */}
            <button onClick={handleUpload} disabled={!file || uploading}
              className="w-full py-4 rounded-xl font-bold text-base flex items-center justify-center gap-2.5
                bg-emerald-500 text-gray-950 hover:bg-emerald-400 active:scale-[0.99]
                disabled:opacity-25 disabled:cursor-not-allowed transition-all
                shadow-[0_0_24px_#10b98120]">
              {uploading
                ? <><Loader2 className="w-5 h-5 animate-spin" />Extracting & Indexing…</>
                : <><Zap className="w-5 h-5" />Index to Elasticsearch</>
              }
            </button>

            {error && (
              <div className="flex items-start gap-3 px-5 py-4 rounded-xl
                bg-red-500/8 border border-red-500/15">
                <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                <p className="text-sm font-mono text-red-300">{error}</p>
              </div>
            )}
          </div>
        </div>

        {/* ── RIGHT COLUMN: Pipeline + Result ──────────── */}
        <div className="flex flex-col gap-6">

          {/* Processing pipeline */}
          <div className="rounded-2xl border border-gray-800/60 bg-gray-900/20 px-8 py-6">
            <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-5">
              Processing Pipeline
            </p>
            <div className="space-y-3">
              {PIPELINE.map(({ Icon, label, sub }, i) => (
                <div key={i} className={`flex items-center gap-4 px-4 py-3.5 rounded-xl
                  transition-all duration-300 ${
                  result
                    ? 'bg-emerald-500/5 border border-emerald-500/10'
                    : 'border border-transparent'
                }`}>
                  <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0
                    transition-all duration-300 ${
                    result
                      ? 'bg-emerald-500/15 border border-emerald-500/20'
                      : 'bg-gray-800/60 border border-gray-700/40'
                  }`}>
                    <Icon className={`w-4 h-4 transition-colors duration-300 ${
                      result ? 'text-emerald-400' : 'text-gray-600'
                    }`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className={`text-sm font-medium transition-colors duration-300 ${
                      result ? 'text-emerald-300' : 'text-gray-500'
                    }`}>{label}</div>
                    <div className="text-xs font-mono text-gray-600 truncate mt-0.5">{sub}</div>
                  </div>
                  <div className={`transition-all duration-300 ${result ? 'opacity-100' : 'opacity-0'}`}>
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Success result */}
          {result && (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/4 overflow-hidden flex-1">
              <div className="px-8 py-4 border-b border-emerald-500/12 flex items-center gap-3">
                <CheckCircle className="w-5 h-5 text-emerald-400" />
                <span className="text-base font-semibold text-emerald-300">Indexed Successfully</span>
                <span className="ml-auto text-xs font-mono text-emerald-700">
                  {result.results_count} tests extracted
                </span>
              </div>
              <div className="p-6 space-y-4">

                {/* Stats grid */}
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { k: 'Patient ID',  v: result.patient_id },
                    { k: 'Test Date',   v: String(result.test_date || '').slice(0, 10) },
                    { k: 'Tests Found', v: String(result.results_count) },
                    { k: 'Document ID', v: (result.document_id || '').slice(0, 10) + '…' },
                  ].map(({ k, v }) => (
                    <div key={k} className="bg-emerald-500/6 border border-emerald-500/12 rounded-xl px-4 py-3">
                      <div className="text-[10px] uppercase tracking-widest text-emerald-700 font-mono">{k}</div>
                      <div className="text-base font-mono font-semibold text-emerald-300 mt-1 truncate">{v}</div>
                    </div>
                  ))}
                </div>

                {/* Flags */}
                {result.critical_flags?.length > 0 && (
                  <div className="flex items-start gap-3 px-4 py-3.5 rounded-xl
                    bg-red-500/8 border border-red-500/15">
                    <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-mono font-bold text-red-400 uppercase tracking-wider">
                        Critical Values
                      </div>
                      <div className="text-sm font-mono text-red-300/70 mt-1">
                        {Array.isArray(result.critical_flags)
                          ? result.critical_flags.join(', ')
                          : result.critical_flags}
                      </div>
                    </div>
                  </div>
                )}

                {result.abnormal_flags?.length > 0 && (
                  <div className="flex items-start gap-3 px-4 py-3.5 rounded-xl
                    bg-amber-500/8 border border-amber-500/15">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="text-xs font-mono font-bold text-amber-400 uppercase tracking-wider">
                        Abnormal Values
                      </div>
                      <div className="text-sm font-mono text-amber-300/70 mt-1">
                        {Array.isArray(result.abnormal_flags)
                          ? result.abnormal_flags.join(', ')
                          : result.abnormal_flags}
                      </div>
                    </div>
                  </div>
                )}

                {onGoToEsql && (
                  <button onClick={onGoToEsql}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl
                      border border-emerald-500/20 text-emerald-400 text-sm font-mono
                      hover:bg-emerald-500/8 hover:border-emerald-500/30 transition-all">
                    Query this data in ES|QL Console
                    <ArrowRight className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Placeholder when no result yet */}
          {!result && (
            <div className="rounded-2xl border border-gray-800/40 bg-gray-900/10 flex-1
              flex flex-col items-center justify-center p-10 text-center min-h-[200px]">
              <Database className="w-10 h-10 text-gray-700 mb-4" />
              <p className="text-base text-gray-600 font-mono">Upload a PDF to see results</p>
              <p className="text-xs text-gray-700 font-mono mt-1.5">
                Extracted data will appear here after indexing
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}