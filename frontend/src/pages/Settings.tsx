import { useEffect, useState } from 'react'
import { Shield, Cpu, Database, Trash2, RefreshCw, AlertTriangle } from 'lucide-react'
import { analyticsApi, healthApi } from '../services/api'
import type { ModelInfo } from '../types'
import Spinner from '../components/ui/Spinner'
import PrivacyBadge from '../components/ui/PrivacyBadge'

export default function Settings() {
  const [modelInfo, setModelInfo] = useState<ModelInfo | null>(null)
  const [health, setHealth] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([analyticsApi.modelInfo(), healthApi.check()])
      .then(([m, h]) => { setModelInfo(m); setHealth(h) })
      .finally(() => setLoading(false))
  }, [])

  const clearData = async () => {
    if (!confirm('This will delete all local quiz history and mastery data. Documents will NOT be deleted. Continue?')) return
    alert('To fully clear data, stop the server and delete data/snapstudy.db, then restart.')
  }

  if (loading) return <div className="flex justify-center items-center h-full"><Spinner className="w-8 h-8" /></div>

  return (
    <div className="p-8 max-w-3xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold text-white mb-1">Settings</h1>
      <p className="text-muted mb-8">App configuration and privacy information</p>

      {/* Status */}
      <div className="card p-6 mb-5">
        <h2 className="section-title mb-4 flex items-center gap-2"><Cpu className="w-4 h-4 text-brand-400" />AI Model</h2>
        <div className="space-y-3">
          {[
            { label: 'Model name', value: modelInfo?.model },
            { label: 'Provider', value: modelInfo?.provider },
            { label: 'Backend', value: modelInfo?.backend },
            { label: 'Inference device', value: modelInfo?.device },
            { label: 'Status', value: modelInfo?.is_available ? '✓ Available' : '✗ Unavailable' },
            { label: 'NPU support', value: modelInfo?.supports_npu ? 'Yes' : 'No' },
          ].map(r => (
            <div key={r.label} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
              <span className="text-sm text-white/50">{r.label}</span>
              <span className="text-sm text-white font-medium">{r.value ?? '—'}</span>
            </div>
          ))}
        </div>

        <div className="mt-4 p-4 rounded-xl bg-brand-600/10 border border-brand-500/20">
          <p className="text-sm text-brand-300 font-medium mb-1">Want real AI answers?</p>
          <p className="text-xs text-white/50 leading-relaxed">
            Set <code className="bg-white/10 px-1 rounded">AI_PROVIDER=local_llm</code> in <code className="bg-white/10 px-1 rounded">.env</code> and install{' '}
            <a href="https://ollama.com" target="_blank" rel="noopener noreferrer" className="text-brand-400 underline">Ollama</a>.
            Then run: <code className="bg-white/10 px-1 rounded">ollama pull llama3.2:3b</code>
          </p>
        </div>
      </div>

      {/* Privacy */}
      <div className="card p-6 mb-5">
        <h2 className="section-title mb-4 flex items-center gap-2"><Shield className="w-4 h-4 text-emerald-400" />Privacy</h2>
        <PrivacyBadge size="md" className="mb-4" />
        <div className="space-y-3 text-sm text-white/60 leading-relaxed">
          <p>SnapStudy processes your uploaded documents on this device. Text extraction, embedding, and vector indexing all run locally.</p>
          <p>When AI_PROVIDER=mock, no data leaves your device at all. When using local_llm (Ollama), inference also runs locally.</p>
          <p className="text-yellow-400 flex items-start gap-1.5"><AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />If you configure AI_PROVIDER=qualcomm_ai_hub, inference is submitted to Qualcomm's AI Hub service. Review their privacy policy before enabling.</p>
        </div>
        <div className="mt-4 space-y-2">
          {[
            { label: 'Text extraction', status: 'Local only' },
            { label: 'Embeddings', status: 'Local only (sentence-transformers)' },
            { label: 'Vector search', status: 'Local only (FAISS)' },
            { label: 'AI generation', status: `${modelInfo?.provider === 'mock' ? 'Local only (mock)' : modelInfo?.provider === 'local_llm' ? 'Local only (Ollama)' : modelInfo?.provider ?? 'See config'}` },
            { label: 'Analytics data', status: 'Local only (SQLite)' },
          ].map(r => (
            <div key={r.label} className="flex items-center justify-between text-xs">
              <span className="text-white/40">{r.label}</span>
              <span className="text-emerald-400">🔒 {r.status}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Storage */}
      <div className="card p-6 mb-5">
        <h2 className="section-title mb-4 flex items-center gap-2"><Database className="w-4 h-4 text-snap-purple" />Local Storage</h2>
        <div className="space-y-2 text-sm text-white/60 mb-4">
          <p>Database: <code className="text-white/80">data/snapstudy.db</code> (SQLite)</p>
          <p>Uploads: <code className="text-white/80">data/uploads/</code></p>
          <p>Vector index: <code className="text-white/80">data/vector_db/</code></p>
        </div>
        <button onClick={clearData} className="btn-secondary text-red-400 border-red-500/20 hover:bg-red-500/10">
          <Trash2 className="w-4 h-4" />
          Clear Study History
        </button>
      </div>

      {/* Health */}
      <div className="card p-6">
        <h2 className="section-title mb-4 flex items-center gap-2"><RefreshCw className="w-4 h-4 text-snap-cyan" />System Status</h2>
        <pre className="text-xs text-white/50 bg-black/20 rounded-xl p-4 overflow-x-auto">
          {JSON.stringify(health, null, 2)}
        </pre>
      </div>
    </div>
  )
}
