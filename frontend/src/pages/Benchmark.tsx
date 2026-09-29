import { useEffect, useState } from 'react'
import { Cpu, Play, Zap, MemoryStick, Clock, Activity } from 'lucide-react'
import { analyticsApi } from '../services/api'
import type { BenchmarkResult, ModelInfo } from '../types'
import Spinner from '../components/ui/Spinner'
import PrivacyBadge from '../components/ui/PrivacyBadge'

function Metric({ label, value, unit, icon: Icon, color }: {
  label: string; value: string | number | null; unit?: string; icon: React.ElementType; color: string
}) {
  return (
    <div className="card p-5">
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 ${color}`}>
        <Icon className="w-4 h-4 text-white" />
      </div>
      <p className="text-muted text-xs mb-1">{label}</p>
      <p className="text-xl font-bold text-white">
        {value !== null && value !== undefined ? `${value}` : '—'}
        {value !== null && unit && <span className="text-sm font-normal text-white/40 ml-1">{unit}</span>}
      </p>
    </div>
  )
}

export default function Benchmark() {
  const [info, setInfo] = useState<{ current_model: ModelInfo; history: BenchmarkResult[] } | null>(null)
  const [result, setResult] = useState<BenchmarkResult | null>(null)
  const [running, setRunning] = useState(false)
  const [iterations, setIterations] = useState(3)
  const [deviceInfo, setDeviceInfo] = useState<Record<string, string>>({})

  useEffect(() => {
    analyticsApi.benchmark().then(setInfo)
    analyticsApi.modelInfo().then(d => setDeviceInfo((d as { device_info?: Record<string, string> }).device_info ?? {}))
  }, [])

  const runBenchmark = async () => {
    setRunning(true)
    try {
      const res = await analyticsApi.runBenchmark(iterations)
      setResult(res)
      analyticsApi.benchmark().then(setInfo)
    } catch (e: unknown) {
      alert('Benchmark failed: ' + (e as Error).message)
    } finally {
      setRunning(false)
    }
  }

  const current = info?.current_model

  return (
    <div className="p-8 max-w-5xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Cpu className="w-5 h-5 text-brand-400" />
            <h1 className="text-2xl font-bold text-white">On-Device AI</h1>
          </div>
          <p className="text-muted">Real measured inference performance on this device</p>
        </div>
        <PrivacyBadge size="md" />
      </div>

      {/* Model info */}
      <div className="card p-6 mb-6">
        <h2 className="section-title mb-4">Current Configuration</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Model', value: current?.model ?? '—' },
            { label: 'Provider', value: current?.provider ?? '—' },
            { label: 'Backend', value: current?.backend ?? '—' },
            { label: 'Device', value: current?.device ?? '—' },
          ].map(item => (
            <div key={item.label}>
              <p className="text-xs text-white/40 mb-1">{item.label}</p>
              <p className="text-sm font-medium text-white truncate">{item.value}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2 mt-4">
          <span className={`badge ${current?.is_available ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20'} border`}>
            {current?.is_available ? '✓ Available' : '✗ Unavailable'}
          </span>
          {current?.supports_npu && (
            <span className="badge bg-snap-purple/10 text-snap-purple border border-snap-purple/20">NPU Support</span>
          )}
          {current?.supports_gpu && (
            <span className="badge bg-blue-500/10 text-blue-400 border border-blue-500/20">GPU Support</span>
          )}
        </div>
      </div>

      {/* Run benchmark */}
      <div className="card p-6 mb-6">
        <h2 className="section-title mb-4">Run Benchmark</h2>
        <p className="text-sm text-white/50 mb-4">
          Runs embedding and generation tests on-device. Results reflect actual measured performance.
          No numbers are fabricated or estimated.
        </p>
        <div className="flex items-center gap-4 mb-4">
          <label className="text-sm text-white/60">Iterations:</label>
          <select className="input w-24 py-2" value={iterations} onChange={e => setIterations(parseInt(e.target.value))}>
            {[1, 2, 3, 5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <button onClick={runBenchmark} disabled={running} className="btn-primary">
          {running ? <Spinner /> : <Play className="w-4 h-4" />}
          {running ? 'Running…' : 'Run Benchmark'}
        </button>
        {running && (
          <p className="text-xs text-white/40 mt-2 animate-pulse">
            Running {iterations} iteration{iterations > 1 ? 's' : ''}… this may take a moment.
          </p>
        )}
      </div>

      {/* Latest result */}
      {result && (
        <div className="mb-6">
          <h2 className="section-title mb-4">Latest Results</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <Metric icon={Clock} label="Avg Generation" value={result.avg_generation_latency_ms?.toFixed(0) ?? null} unit="ms" color="bg-brand-600" />
            <Metric icon={Zap} label="Tokens / sec" value={result.avg_tokens_per_second?.toFixed(1) ?? null} color="bg-snap-purple" />
            <Metric icon={Activity} label="Avg Embedding" value={result.avg_embedding_latency_ms?.toFixed(0) ?? null} unit="ms" color="bg-snap-cyan" />
            <Metric icon={MemoryStick} label="Memory Usage" value={result.memory_usage_mb?.toFixed(0) ?? null} unit="MB" color="bg-snap-green" />
          </div>
          {result.note && (
            <div className="px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 text-xs">
              ⚠ {result.note}
            </div>
          )}
        </div>
      )}

      {/* Architecture diagram */}
      <div className="card p-6 mb-6">
        <h2 className="section-title mb-4">On-Device Architecture</h2>
        <pre className="text-xs text-white/50 font-mono leading-relaxed overflow-x-auto">{`
STUDENT
   │
   ▼
┌──────────────────────────────┐
│          SnapStudy           │
│    (FastAPI + React UI)      │
└──────────────┬───────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
Study Documents      Student Query
    │                     │
    ▼                     ▼
Text Extraction       Embedding Model
(PyMuPDF/DOCX/PPTX)  (sentence-transformers)
    │                     │
    ▼                     ▼
  Chunking            FAISS Vector DB
(512-word chunks)    (cosine similarity)
    │                     │
    └──────────┬──────────┘
               ▼
         Top-K Retrieval
         (relevant chunks)
               │
               ▼
      Local AI Model (LLM)
      [mock / ollama / onnx /
       Qualcomm AI Hub]
               │
               ▼
    Grounded Answer + Citations
               │
    ┌──────────┴──────────┐
    ▼                     ▼
 Student             Analytics
 (answer)         (mastery tracking)
        `}</pre>
      </div>

      {/* Why Snapdragon section */}
      <div className="card p-6 mb-6">
        <h2 className="section-title mb-3">Why Snapdragon?</h2>
        <div className="grid md:grid-cols-3 gap-4 text-sm text-white/60 leading-relaxed">
          {[
            { title: 'Efficient Edge Inference', body: 'Snapdragon SoCs integrate CPU, GPU, and NPU on a single chip. Quantized models (INT4/INT8) can run inference with substantially lower latency than general-purpose cloud endpoints for supported workloads.' },
            { title: 'Privacy by Design', body: 'Running AI locally means student study materials — potentially including sensitive personal notes and exam materials — do not need to leave the device to reach a cloud API.' },
            { title: 'NPU Acceleration Path', body: 'The architecture is structured so that ONNX Runtime with QNNExecutionProvider or Qualcomm AI Hub exported models can replace the mock/ollama provider with minimal code changes.' },
          ].map(item => (
            <div key={item.title} className="bg-white/3 rounded-xl p-4">
              <p className="font-medium text-white mb-2">{item.title}</p>
              <p>{item.body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Device info */}
      {Object.keys(deviceInfo).length > 0 && (
        <div className="card p-6">
          <h2 className="section-title mb-4">Device Information</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2">
            {Object.entries(deviceInfo).map(([k, v]) => (
              <div key={k} className="flex justify-between text-sm border-b border-white/5 py-2">
                <span className="text-white/40 capitalize">{k.replace(/_/g, ' ')}</span>
                <span className="text-white/70 font-mono text-xs">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* History */}
      {(info?.history?.length ?? 0) > 0 && (
        <div className="card overflow-hidden mt-6">
          <div className="px-6 py-4 border-b border-white/5">
            <h2 className="section-title">Benchmark History</h2>
          </div>
          <div className="divide-y divide-white/5">
            {info!.history.map((h, i) => (
              <div key={i} className="px-6 py-3 flex items-center gap-4 text-sm">
                <span className="text-white/30 text-xs w-32 shrink-0">{h.run_at ? new Date(h.run_at).toLocaleString() : '—'}</span>
                <span className="text-white/60 flex-1 truncate">{h.model}</span>
                <span className="text-white/50 w-20 text-right">{(h as any).avg_gen_latency_ms?.toFixed(0) ?? '—'} ms</span>
                <span className="text-brand-400 w-20 text-right">{(h as any).tokens_per_second?.toFixed(1) ?? h.avg_tokens_per_second?.toFixed(1) ?? '—'} tok/s</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
