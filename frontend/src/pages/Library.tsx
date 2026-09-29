import { useEffect, useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, FileText, Trash2, Search, ChevronRight,
  RefreshCw, FileQuestion, Shield,
} from 'lucide-react'
import { documentsApi } from '../services/api'
import type { Document } from '../types'
import StatusBadge from '../components/ui/StatusBadge'
import PrivacyBadge from '../components/ui/PrivacyBadge'
import Spinner from '../components/ui/Spinner'

const ICON_MAP: Record<string, string> = {
  pdf: '📄', docx: '📝', pptx: '📊', txt: '📃', md: '📃', markdown: '📃',
}

function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function DocCard({
  doc, onDelete, onSelect,
}: {
  doc: Document; onDelete: (id: number) => void; onSelect: (doc: Document) => void
}) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm(`Delete "${doc.filename}"?`)) return
    setDeleting(true)
    try { await onDelete(doc.id) } finally { setDeleting(false) }
  }

  return (
    <div
      className="card p-4 hover:border-white/20 transition-all cursor-pointer group"
      onClick={() => onSelect(doc)}
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl">{ICON_MAP[doc.file_type] ?? '📄'}</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">{doc.filename}</p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="badge bg-white/5 text-white/50 text-[10px]">{doc.file_type.toUpperCase()}</span>
            <span className="text-[11px] text-white/40">{fmtSize(doc.file_size)}</span>
            {doc.page_count > 0 && (
              <span className="text-[11px] text-white/40">{doc.page_count}p</span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-2">
            <StatusBadge status={doc.processing_status} />
          </div>
          {doc.processing_status === 'ready' && (
            <div className="flex items-center gap-1 mt-1.5">
              <Shield className="w-3 h-3 text-emerald-400" />
              <span className="text-[10px] text-emerald-400">Processed locally</span>
            </div>
          )}
          {doc.error_message && (
            <p className="text-xs text-red-400 mt-1 truncate">{doc.error_message}</p>
          )}
        </div>
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <ChevronRight className="w-4 h-4 text-white/30" />
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="p-1.5 rounded-lg hover:bg-red-500/10 text-white/30 hover:text-red-400 transition-all"
          >
            {deleting ? <Spinner className="w-3.5 h-3.5" /> : <Trash2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>
    </div>
  )
}

function DocDetail({ doc, onClose }: { doc: Document; onClose: () => void }) {
  const [summary, setSummary] = useState<string | null>(null)
  const [sumLoading, setSumLoading] = useState(false)
  const [sumType, setSumType] = useState<'quick' | 'exam' | 'simple'>('quick')

  const loadSummary = async (type: 'quick' | 'exam' | 'simple') => {
    if (doc.processing_status !== 'ready') return
    setSumType(type)
    setSumLoading(true)
    try {
      const res = await documentsApi.summary(doc.id, type)
      setSummary(res.content)
    } catch { setSummary('Failed to generate summary.') }
    finally { setSumLoading(false) }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="card w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6 animate-slide-up" onClick={e => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-5">
          <div>
            <h2 className="text-lg font-semibold text-white">{doc.filename}</h2>
            <div className="flex items-center gap-2 mt-1">
              <StatusBadge status={doc.processing_status} />
              <PrivacyBadge />
              <span className="text-xs text-white/40">{fmtSize(doc.file_size)}</span>
              {doc.page_count > 0 && <span className="text-xs text-white/40">{doc.page_count} pages</span>}
              {doc.chunk_count > 0 && <span className="text-xs text-white/40">{doc.chunk_count} chunks</span>}
            </div>
          </div>
          <button onClick={onClose} className="btn-ghost text-white/50 text-sm px-2 py-1">✕</button>
        </div>

        {doc.key_concepts?.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Key Concepts</p>
            <div className="flex flex-wrap gap-1.5">
              {doc.key_concepts.slice(0, 10).map(c => (
                <span key={c} className="badge bg-brand-600/10 text-brand-400 border border-brand-500/20">{c}</span>
              ))}
            </div>
          </div>
        )}

        {doc.processing_status === 'ready' && (
          <>
            <p className="text-xs text-white/40 uppercase tracking-wider mb-2">Generate Summary</p>
            <div className="flex gap-2 mb-3">
              {(['quick', 'exam', 'simple'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => loadSummary(t)}
                  className={`btn-secondary text-xs py-1.5 px-3 capitalize ${sumType === t && summary ? 'border-brand-500/40 text-brand-400' : ''}`}
                >
                  {t === 'quick' ? '⚡ Quick' : t === 'exam' ? '📚 Exam Notes' : '🌱 Simple'}
                </button>
              ))}
            </div>
            {sumLoading && <div className="flex items-center gap-2 text-white/50 text-sm py-3"><Spinner /><span>Generating…</span></div>}
            {summary && !sumLoading && (
              <div className="bg-white/5 rounded-xl p-4 text-sm text-white/80 leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
                {summary}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function Library() {
  const [docs, setDocs] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Document | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(() => {
    documentsApi.list().then(setDocs).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(() => {
      // Poll while any doc is processing
      setDocs(prev => {
        if (prev.some(d => d.processing_status === 'processing' || d.processing_status === 'pending')) {
          documentsApi.list().then(setDocs)
        }
        return prev
      })
    }, 3000)
    return () => clearInterval(interval)
  }, [refresh])

  const onDrop = useCallback(async (files: File[]) => {
    for (const file of files) {
      setUploading(true)
      setError(null)
      try {
        const doc = await documentsApi.upload(file, setUploadPct)
        setDocs(prev => [doc, ...prev])
      } catch (e: unknown) {
        const msg = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? (e as Error).message
        setError(msg)
      } finally {
        setUploading(false)
        setUploadPct(0)
      }
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md'],
    },
    multiple: true,
    disabled: uploading,
  })

  const handleDelete = async (id: number) => {
    await documentsApi.delete(id)
    setDocs(prev => prev.filter(d => d.id !== id))
    if (selected?.id === id) setSelected(null)
  }

  const filtered = docs.filter(d =>
    d.filename.toLowerCase().includes(search.toLowerCase()) ||
    d.file_type.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-8 max-w-5xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">My Library</h1>
          <p className="text-muted mt-0.5">{docs.length} document{docs.length !== 1 ? 's' : ''} · All processed locally</p>
        </div>
        <button onClick={refresh} className="btn-ghost">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Upload zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 mb-6 ${
          isDragActive ? 'border-brand-500 bg-brand-500/10' : 'border-white/10 hover:border-white/20 hover:bg-white/3'
        } ${uploading ? 'opacity-60 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-3">
          {uploading ? (
            <>
              <Spinner className="w-8 h-8" />
              <p className="text-white/70 text-sm">Uploading… {uploadPct}%</p>
            </>
          ) : (
            <>
              <div className="w-12 h-12 rounded-xl bg-brand-600/10 flex items-center justify-center">
                <Upload className="w-6 h-6 text-brand-400" />
              </div>
              <div>
                <p className="text-white/80 font-medium">
                  {isDragActive ? 'Drop files here' : 'Drop files or click to upload'}
                </p>
                <p className="text-white/40 text-sm mt-1">PDF, DOCX, PPTX, TXT, MD · Max 50 MB</p>
              </div>
              <PrivacyBadge />
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Search */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
        <input
          className="input pl-9"
          placeholder="Search documents…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {/* Document list */}
      {loading ? (
        <div className="flex justify-center py-12"><Spinner className="w-8 h-8" /></div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <FileQuestion className="w-12 h-12 text-white/20 mx-auto mb-3" />
          <p className="text-white/40">{search ? 'No matching documents' : 'No documents yet. Upload your study materials!'}</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {filtered.map(doc => (
            <DocCard key={doc.id} doc={doc} onDelete={handleDelete} onSelect={setSelected} />
          ))}
        </div>
      )}

      {selected && <DocDetail doc={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
