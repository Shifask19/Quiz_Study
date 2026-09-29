import { useState, useEffect } from 'react'
import { Trophy, CheckCircle, XCircle, ChevronRight, RotateCcw, BookOpen } from 'lucide-react'
import { quizApi, documentsApi } from '../services/api'
import type { Document, QuizQuestion, QuizResult } from '../types'
import Spinner from '../components/ui/Spinner'
import clsx from 'clsx'

type Phase = 'setup' | 'taking' | 'results'

export default function QuizLab() {
  const [phase, setPhase] = useState<Phase>('setup')
  const [docs, setDocs] = useState<Document[]>([])
  const [docId, setDocId] = useState<number | null>(null)
  const [topic, setTopic] = useState('')
  const [difficulty, setDifficulty] = useState('medium')
  const [numQ, setNumQ] = useState(5)
  const [qtypes, setQtypes] = useState<string[]>(['multiple_choice', 'true_false'])
  const [loading, setLoading] = useState(false)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [fullQuestions, setFullQuestions] = useState<QuizQuestion[]>([]) // with answers
  const [quizId, setQuizId] = useState('')
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [current, setCurrent] = useState(0)
  const [result, setResult] = useState<QuizResult | null>(null)
  const [history, setHistory] = useState<{ quiz_id: string; topic: string; score_percent: number; timestamp: string }[]>([])

  useEffect(() => {
    documentsApi.list().then(d => {
      const ready = d.filter(doc => doc.processing_status === 'ready')
      setDocs(ready)
      if (ready.length > 0) setDocId(ready[0].id)
    })
    quizApi.history(10).then(setHistory)
  }, [])

  const generate = async () => {
    if (!docId) return
    setLoading(true)
    try {
      const res = await quizApi.generate({
        document_id: docId,
        topic: topic || undefined,
        difficulty,
        num_questions: numQ,
        question_types: qtypes,
      })
      setQuestions(res.questions)
      setFullQuestions(res.questions) // will be filled with answers after evaluate
      setQuizId(res.quiz_id)
      setAnswers({})
      setCurrent(0)
      setPhase('taking')
    } catch (e: unknown) {
      alert('Failed to generate quiz: ' + ((e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? (e as Error).message))
    } finally {
      setLoading(false)
    }
  }

  const submit = async () => {
    if (!docId) return
    setLoading(true)
    try {
      // We need to send back questions WITH correct_answer for evaluation
      // The backend expects full question objects
      const res = await quizApi.evaluate({
        quiz_id: quizId,
        document_id: docId,
        questions: fullQuestions,
        user_answers: Object.fromEntries(Object.entries(answers).map(([k, v]) => [k, v])),
      })
      setResult(res)
      setPhase('results')
      quizApi.history(10).then(setHistory)
    } catch (e: unknown) {
      alert('Evaluation failed: ' + (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const toggleQtype = (t: string) => {
    setQtypes(prev => prev.includes(t) ? (prev.length > 1 ? prev.filter(x => x !== t) : prev) : [...prev, t])
  }

  const q = questions[current]
  const answered = Object.keys(answers).length
  const allAnswered = answered >= questions.length

  if (phase === 'setup') {
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in">
        <h1 className="text-2xl font-bold text-white mb-1">Quiz Lab</h1>
        <p className="text-muted mb-8">Generate a quiz from your study material</p>

        <div className="card p-6 space-y-5">
          {/* Document */}
          <div>
            <label className="text-sm text-white/60 mb-2 block">Document *</label>
            {docs.length === 0 ? (
              <p className="text-sm text-yellow-400">No processed documents. Upload and process a document first.</p>
            ) : (
              <select className="input" value={docId ?? ''} onChange={e => setDocId(parseInt(e.target.value))}>
                {docs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
              </select>
            )}
          </div>

          {/* Topic */}
          <div>
            <label className="text-sm text-white/60 mb-2 block">Topic <span className="text-white/30">(optional)</span></label>
            <input className="input" placeholder="e.g. Database Normalization" value={topic} onChange={e => setTopic(e.target.value)} />
          </div>

          {/* Difficulty */}
          <div>
            <label className="text-sm text-white/60 mb-2 block">Difficulty</label>
            <div className="flex gap-2">
              {['easy', 'medium', 'hard'].map(d => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={clsx('flex-1 py-2 rounded-xl text-sm capitalize transition-all border', difficulty === d
                    ? 'bg-brand-600 border-brand-500 text-white'
                    : 'bg-white/5 border-white/10 text-white/50 hover:text-white/80'
                  )}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          {/* Count */}
          <div>
            <label className="text-sm text-white/60 mb-2 block">Number of questions: <span className="text-white">{numQ}</span></label>
            <input type="range" min={2} max={15} value={numQ} onChange={e => setNumQ(parseInt(e.target.value))} className="w-full accent-brand-500" />
          </div>

          {/* Types */}
          <div>
            <label className="text-sm text-white/60 mb-2 block">Question types</label>
            <div className="flex gap-2 flex-wrap">
              {['multiple_choice', 'true_false', 'short_answer'].map(t => (
                <button
                  key={t}
                  onClick={() => toggleQtype(t)}
                  className={clsx('px-3 py-1.5 rounded-lg text-xs capitalize transition-all border', qtypes.includes(t)
                    ? 'bg-brand-600/20 border-brand-500/40 text-brand-400'
                    : 'bg-white/5 border-white/10 text-white/40 hover:text-white/70'
                  )}
                >
                  {t.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          <button onClick={generate} disabled={loading || !docId} className="btn-primary w-full justify-center py-3">
            {loading ? <Spinner /> : <Trophy className="w-4 h-4" />}
            Generate Quiz
          </button>
        </div>

        {/* History */}
        {history.length > 0 && (
          <div className="mt-8">
            <h2 className="section-title mb-3">Recent Quizzes</h2>
            <div className="space-y-2">
              {history.slice(0, 5).map(h => (
                <div key={h.quiz_id} className="card px-4 py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm text-white/80">{h.topic || 'General'}</p>
                    <p className="text-xs text-white/40">{h.timestamp ? new Date(h.timestamp).toLocaleDateString() : ''}</p>
                  </div>
                  <div className={clsx('font-bold text-lg', h.score_percent >= 70 ? 'text-snap-green' : h.score_percent >= 40 ? 'text-snap-orange' : 'text-snap-red')}>
                    {h.score_percent}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (phase === 'taking' && q) {
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in">
        {/* Progress */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-white/50">Question {current + 1} of {questions.length}</span>
          <span className="text-sm text-white/50">{answered} answered</span>
        </div>
        <div className="w-full h-1.5 bg-white/10 rounded-full mb-6 overflow-hidden">
          <div className="h-full bg-brand-500 rounded-full transition-all" style={{ width: `${((current + 1) / questions.length) * 100}%` }} />
        </div>

        <div className="card p-6">
          <p className="text-xs text-white/40 mb-1 uppercase tracking-wider">{q.topic} · {q.difficulty}</p>
          <p className="text-white font-medium mb-6 leading-relaxed">{q.question}</p>

          {/* Multiple choice */}
          {q.type === 'multiple_choice' && q.options && (
            <div className="space-y-2.5">
              {Object.entries(q.options).map(([key, val]) => (
                <button
                  key={key}
                  onClick={() => setAnswers(prev => ({ ...prev, [q.id]: key }))}
                  className={clsx(
                    'w-full text-left px-4 py-3 rounded-xl border text-sm transition-all',
                    answers[q.id] === key
                      ? 'bg-brand-600/20 border-brand-500 text-white'
                      : 'bg-white/3 border-white/10 text-white/70 hover:border-white/20 hover:text-white/90'
                  )}
                >
                  <span className="font-medium text-brand-400 mr-2">{key}.</span> {val}
                </button>
              ))}
            </div>
          )}

          {/* True/false */}
          {q.type === 'true_false' && (
            <div className="flex gap-3">
              {['True', 'False'].map(opt => (
                <button
                  key={opt}
                  onClick={() => setAnswers(prev => ({ ...prev, [q.id]: opt }))}
                  className={clsx(
                    'flex-1 py-3 rounded-xl border text-sm font-medium transition-all',
                    answers[q.id] === opt
                      ? 'bg-brand-600/20 border-brand-500 text-brand-400'
                      : 'bg-white/3 border-white/10 text-white/70 hover:border-white/20'
                  )}
                >
                  {opt}
                </button>
              ))}
            </div>
          )}

          {/* Short answer */}
          {q.type === 'short_answer' && (
            <textarea
              className="input resize-none"
              rows={3}
              placeholder="Type your answer…"
              value={answers[q.id] ?? ''}
              onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
            />
          )}
        </div>

        {/* Navigation */}
        <div className="flex justify-between mt-5">
          <button onClick={() => setCurrent(p => Math.max(0, p - 1))} disabled={current === 0} className="btn-secondary">← Back</button>
          <div className="flex gap-2">
            {current < questions.length - 1 ? (
              <button onClick={() => setCurrent(p => p + 1)} className="btn-primary">
                Next <ChevronRight className="w-4 h-4" />
              </button>
            ) : (
              <button onClick={submit} disabled={loading || !allAnswered} className="btn-primary bg-snap-green hover:bg-emerald-400">
                {loading ? <Spinner /> : <CheckCircle className="w-4 h-4" />}
                Submit Quiz
              </button>
            )}
          </div>
        </div>

        {/* Jump dots */}
        <div className="flex gap-1.5 justify-center mt-5">
          {questions.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              className={clsx('w-2 h-2 rounded-full transition-all', i === current ? 'bg-brand-400 scale-125' : answers[questions[i].id] ? 'bg-snap-green' : 'bg-white/20')}
            />
          ))}
        </div>
      </div>
    )
  }

  if (phase === 'results' && result) {
    const pct = result.score_percent
    const color = pct >= 80 ? 'text-snap-green' : pct >= 50 ? 'text-snap-orange' : 'text-snap-red'
    return (
      <div className="p-8 max-w-2xl mx-auto animate-fade-in">
        {/* Score header */}
        <div className="card p-8 text-center mb-6">
          <Trophy className={clsx('w-12 h-12 mx-auto mb-3', color)} />
          <p className={clsx('text-5xl font-bold mb-1', color)}>{pct}%</p>
          <p className="text-white/60">{result.correct} / {result.total_questions} correct</p>
          {result.recommendations[0] && (
            <p className="text-sm text-white/50 mt-3 italic">{result.recommendations[0]}</p>
          )}
          <div className="flex justify-center gap-3 mt-4">
            <button onClick={() => { setPhase('setup'); setResult(null) }} className="btn-secondary text-sm">
              <RotateCcw className="w-4 h-4" /> New Quiz
            </button>
          </div>
        </div>

        {/* Weak/strong */}
        {(result.weak_topics.length > 0 || result.strong_topics.length > 0) && (
          <div className="grid grid-cols-2 gap-4 mb-6">
            {result.weak_topics.length > 0 && (
              <div className="card p-4">
                <p className="text-xs text-snap-orange uppercase tracking-wider mb-2">Needs work</p>
                {result.weak_topics.map(t => (
                  <p key={t} className="text-sm text-white/70 flex items-center gap-1"><XCircle className="w-3.5 h-3.5 text-snap-orange" />{t}</p>
                ))}
              </div>
            )}
            {result.strong_topics.length > 0 && (
              <div className="card p-4">
                <p className="text-xs text-snap-green uppercase tracking-wider mb-2">Strong</p>
                {result.strong_topics.map(t => (
                  <p key={t} className="text-sm text-white/70 flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5 text-snap-green" />{t}</p>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Question review */}
        <h2 className="section-title mb-3">Review</h2>
        <div className="space-y-3">
          {result.questions.map((q, i) => (
            <div key={i} className={clsx('card p-4 border', q.is_correct ? 'border-emerald-500/20' : 'border-red-500/20')}>
              <div className="flex items-start gap-3">
                {q.is_correct
                  ? <CheckCircle className="w-4 h-4 text-snap-green shrink-0 mt-0.5" />
                  : <XCircle className="w-4 h-4 text-snap-red shrink-0 mt-0.5" />
                }
                <div className="flex-1">
                  <p className="text-sm text-white/90 mb-2">{q.question}</p>
                  <div className="text-xs space-y-1">
                    <p className="text-white/50">Your answer: <span className={q.is_correct ? 'text-snap-green' : 'text-snap-red'}>{q.user_answer || '—'}</span></p>
                    {!q.is_correct && <p className="text-white/50">Correct: <span className="text-snap-green">{q.correct_answer}</span></p>}
                    {q.explanation && <p className="text-white/40 mt-1 italic">{q.explanation}</p>}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return <div className="flex items-center justify-center h-full"><Spinner className="w-8 h-8" /></div>
}
