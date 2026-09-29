import { useState, useEffect } from 'react'
import { RefreshCw, CheckCircle, XCircle, BookOpen, TrendingUp, Play } from 'lucide-react'
import { analyticsApi, documentsApi } from '../services/api'
import type { Document, RevisionSession } from '../types'
import Spinner from '../components/ui/Spinner'
import clsx from 'clsx'

type Phase = 'setup' | 'study' | 'quiz' | 'complete'

export default function Revision() {
  const [docs, setDocs] = useState<Document[]>([])
  const [docId, setDocId] = useState<number | null>(null)
  const [topic, setTopic] = useState('')
  const [loading, setLoading] = useState(false)
  const [session, setSession] = useState<RevisionSession | null>(null)
  const [phase, setPhase] = useState<Phase>('setup')
  const [current, setCurrent] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [completed, setCompleted] = useState<{ mastery_before: number; mastery_after: number; improvement: number; next_step: string } | null>(null)

  useEffect(() => {
    documentsApi.list().then(d => {
      const ready = d.filter(doc => doc.processing_status === 'ready')
      setDocs(ready)
      if (ready.length > 0) setDocId(ready[0].id)
    })
  }, [])

  const startSession = async () => {
    setLoading(true)
    try {
      const s = await analyticsApi.startRevision({
        topic: topic || undefined,
        document_id: docId ?? undefined,
        num_rounds: 5,
      })
      setSession(s)
      setAnswers({})
      setCurrent(0)
      setPhase('study')
    } catch (e: unknown) {
      alert('Failed to start revision: ' + (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const finishRevision = async () => {
    if (!session) return
    const total = session.questions.length
    const correct = session.questions.filter((q, i) => {
      const ans = answers[i] ?? ''
      return ans.toLowerCase().trim() === q.correct_answer.toLowerCase().trim()
    }).length

    setLoading(true)
    try {
      const res = await analyticsApi.completeRevision({
        session_id: session.session_id,
        topic: session.topic,
        correct_answers: correct,
        total_questions: total,
      })
      setCompleted(res)
      setPhase('complete')
    } finally {
      setLoading(false)
    }
  }

  if (phase === 'setup') {
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in">
        <h1 className="text-2xl font-bold text-white mb-1">Smart Revision</h1>
        <p className="text-muted mb-8">Adaptive study sessions focused on your weak areas</p>

        <div className="card p-6 space-y-5">
          <div>
            <label className="text-sm text-white/60 mb-2 block">Document</label>
            {docs.length === 0 ? (
              <p className="text-sm text-yellow-400">No processed documents yet.</p>
            ) : (
              <select className="input" value={docId ?? ''} onChange={e => setDocId(parseInt(e.target.value))}>
                {docs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
              </select>
            )}
          </div>
          <div>
            <label className="text-sm text-white/60 mb-2 block">Topic <span className="text-white/30">(leave blank for weakest topic)</span></label>
            <input className="input" placeholder="e.g. Database Normalization" value={topic} onChange={e => setTopic(e.target.value)} />
          </div>
          <button onClick={startSession} disabled={loading} className="btn-primary w-full justify-center py-3">
            {loading ? <Spinner /> : <Play className="w-4 h-4" />}
            Start Revision Session
          </button>
        </div>
      </div>
    )
  }

  if (!session) return null

  if (phase === 'study') {
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-brand-600/20 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h1 className="font-bold text-white">{session.topic}</h1>
            <p className="text-xs text-white/40">Starting mastery: {session.mastery_before}%</p>
          </div>
        </div>

        <div className="card p-6 mb-4">
          <p className="text-xs text-brand-400 uppercase tracking-wider mb-2">Explanation</p>
          <p className="text-white/80 text-sm leading-relaxed">{session.explanation}</p>
        </div>

        {session.example && (
          <div className="card p-5 mb-6 border-snap-purple/20">
            <p className="text-xs text-snap-purple uppercase tracking-wider mb-2">Example</p>
            <p className="text-white/70 text-sm leading-relaxed italic">{session.example}</p>
          </div>
        )}

        {session.sources.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-6">
            {session.sources.map((s, i) => (
              <span key={i} className="badge bg-white/5 text-white/40 border border-white/10 text-xs">
                📄 {s.document} · p{s.page}
              </span>
            ))}
          </div>
        )}

        <button onClick={() => setPhase('quiz')} className="btn-primary w-full justify-center py-3">
          I'm ready — Start Quiz
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>
    )
  }

  if (phase === 'quiz') {
    const q = session.questions[current]
    if (!q) {
      return (
        <div className="p-8 max-w-2xl mx-auto text-center">
          <button onClick={finishRevision} disabled={loading} className="btn-primary">
            {loading ? <Spinner /> : 'Finish & See Results'}
          </button>
        </div>
      )
    }
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-white/50">Question {current + 1} / {session.questions.length}</span>
          <span className="text-sm text-brand-400">{session.topic}</span>
        </div>
        <div className="w-full h-1.5 bg-white/10 rounded-full mb-6">
          <div className="h-full bg-brand-500 rounded-full" style={{ width: `${((current) / session.questions.length) * 100}%` }} />
        </div>

        <div className="card p-6">
          <p className="text-white font-medium mb-5 leading-relaxed">{q.question}</p>

          {q.type === 'multiple_choice' && q.options && (
            <div className="space-y-2.5">
              {Object.entries(q.options).map(([key, val]) => (
                <button
                  key={key}
                  onClick={() => setAnswers(prev => ({ ...prev, [current]: key }))}
                  className={clsx(
                    'w-full text-left px-4 py-3 rounded-xl border text-sm transition-all',
                    answers[current] === key ? 'bg-brand-600/20 border-brand-500 text-white' : 'bg-white/3 border-white/10 text-white/70 hover:border-white/20'
                  )}
                >
                  <span className="font-medium text-brand-400 mr-2">{key}.</span>{val}
                </button>
              ))}
            </div>
          )}

          {q.type === 'true_false' && (
            <div className="flex gap-3">
              {['True', 'False'].map(opt => (
                <button key={opt} onClick={() => setAnswers(prev => ({ ...prev, [current]: opt }))}
                  className={clsx('flex-1 py-3 rounded-xl border text-sm font-medium transition-all',
                    answers[current] === opt ? 'bg-brand-600/20 border-brand-500 text-brand-400' : 'bg-white/3 border-white/10 text-white/70 hover:border-white/20'
                  )}>{opt}</button>
              ))}
            </div>
          )}

          {q.type === 'short_answer' && (
            <textarea className="input resize-none" rows={3} placeholder="Your answer…"
              value={answers[current] ?? ''}
              onChange={e => setAnswers(prev => ({ ...prev, [current]: e.target.value }))}
            />
          )}
        </div>

        <div className="flex justify-between mt-5">
          <button onClick={() => setCurrent(p => Math.max(0, p - 1))} disabled={current === 0} className="btn-secondary">← Back</button>
          {current < session.questions.length - 1 ? (
            <button onClick={() => setCurrent(p => p + 1)} disabled={!answers[current]} className="btn-primary">Next →</button>
          ) : (
            <button onClick={finishRevision} disabled={loading} className="btn-primary bg-snap-green hover:bg-emerald-400">
              {loading ? <Spinner /> : <CheckCircle className="w-4 h-4" />} Finish
            </button>
          )}
        </div>
      </div>
    )
  }

  if (phase === 'complete' && completed) {
    const improved = completed.improvement > 0
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in text-center">
        <div className="card p-8">
          <div className="w-16 h-16 rounded-2xl bg-snap-green/10 flex items-center justify-center mx-auto mb-4">
            <TrendingUp className="w-8 h-8 text-snap-green" />
          </div>
          <h2 className="text-xl font-bold text-white mb-1">Revision Complete!</h2>
          <p className="text-white/50 mb-6">{session.topic}</p>

          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-white/5 rounded-xl p-4">
              <p className="text-xs text-white/40 mb-1">Before</p>
              <p className="text-2xl font-bold text-white/70">{completed.mastery_before}%</p>
            </div>
            <div className="bg-white/5 rounded-xl p-4">
              <p className="text-xs text-white/40 mb-1">After</p>
              <p className={clsx('text-2xl font-bold', improved ? 'text-snap-green' : 'text-white')}>{completed.mastery_after}%</p>
            </div>
          </div>

          {improved && (
            <p className="text-snap-green text-sm mb-4">+{completed.improvement}% improvement 🎉</p>
          )}
          <p className="text-white/50 text-sm italic mb-6">{completed.next_step}</p>

          <button onClick={() => { setPhase('setup'); setSession(null); setCompleted(null) }} className="btn-primary justify-center">
            <RefreshCw className="w-4 h-4" /> Another Session
          </button>
        </div>
      </div>
    )
  }

  return null
}
