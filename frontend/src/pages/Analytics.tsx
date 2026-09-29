import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { analyticsApi } from '../services/api'
import type { TopicMastery } from '../types'
import Spinner from '../components/ui/Spinner'

export default function Analytics() {
  const [mastery, setMastery] = useState<TopicMastery[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    analyticsApi.mastery()
      .then(res => setMastery(res.mastery))
      .finally(() => setLoading(false))
  }, [])

  const getColor = (score: number) => {
    if (score >= 80) return '#10B981'
    if (score >= 60) return '#F59E0B'
    return '#EF4444'
  }

  const getIcon = (score: number) => {
    if (score >= 80) return <TrendingUp className="w-4 h-4 text-snap-green" />
    if (score >= 60) return <Minus className="w-4 h-4 text-snap-orange" />
    return <TrendingDown className="w-4 h-4 text-snap-red" />
  }

  if (loading) return <div className="flex justify-center items-center h-full"><Spinner className="w-8 h-8" /></div>

  return (
    <div className="p-8 max-w-5xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold text-white mb-1">Analytics</h1>
      <p className="text-muted mb-8">Your topic mastery and learning progress</p>

      {mastery.length === 0 ? (
        <div className="card p-12 text-center">
          <p className="text-white/40">No data yet. Complete some quizzes to see your analytics!</p>
        </div>
      ) : (
        <>
          {/* Bar chart */}
          <div className="card p-6 mb-6">
            <h2 className="section-title mb-4">Topic Mastery Overview</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={mastery.slice(0, 12)} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <XAxis
                  dataKey="topic"
                  tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }}
                  tickFormatter={v => v.length > 12 ? v.slice(0, 12) + '…' : v}
                />
                <YAxis domain={[0, 100]} tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: '#1e2235', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }}
                  labelStyle={{ color: 'white' }}
                  formatter={(v: number) => [`${v}%`, 'Mastery']}
                />
                <Bar dataKey="score" radius={[6, 6, 0, 0]}>
                  {mastery.slice(0, 12).map((entry, i) => (
                    <Cell key={i} fill={getColor(entry.score)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Topic table */}
          <div className="card overflow-hidden">
            <div className="px-6 py-4 border-b border-white/5">
              <h2 className="section-title">All Topics</h2>
            </div>
            <div className="divide-y divide-white/5">
              {mastery.map(t => (
                <div key={t.topic} className="px-6 py-4 flex items-center gap-4">
                  <div className="w-5 shrink-0">{getIcon(t.score)}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white/90 font-medium truncate">{t.topic}</p>
                    <p className="text-xs text-white/40">{t.questions_attempted} questions attempted</p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="w-32 h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${t.score}%`, background: getColor(t.score) }}
                      />
                    </div>
                    <span className="w-12 text-right text-sm font-semibold" style={{ color: getColor(t.score) }}>
                      {t.score}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
