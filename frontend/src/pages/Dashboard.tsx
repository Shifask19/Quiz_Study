import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen, Trophy, Flame, TrendingUp, AlertTriangle,
  Play, Upload, Zap, ChevronRight, CheckCircle, XCircle,
} from 'lucide-react'
import { analyticsApi, documentsApi } from '../services/api'
import type { DashboardStats } from '../types'
import Spinner from '../components/ui/Spinner'
import PrivacyBadge from '../components/ui/PrivacyBadge'

function StatCard({
  icon: Icon, label, value, color, sub,
}: {
  icon: React.ElementType; label: string; value: string | number; color: string; sub?: string
}) {
  return (
    <div className="card p-5 flex items-start gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
        <Icon className="w-5 h-5 text-white" />
      </div>
      <div>
        <p className="text-muted">{label}</p>
        <p className="text-2xl font-bold text-white mt-0.5">{value}</p>
        {sub && <p className="text-xs text-white/30 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [demoLoading, setDemoLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    analyticsApi.dashboard()
      .then(setStats)
      .finally(() => setLoading(false))
  }, [])

  const handleDemo = async () => {
    setDemoLoading(true)
    try {
      await documentsApi.loadDemo()
      await new Promise(r => setTimeout(r, 800))
      const s = await analyticsApi.dashboard()
      setStats(s)
      navigate('/library')
    } catch (e: unknown) {
      alert('Demo load failed: ' + (e as Error).message)
    } finally {
      setDemoLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="w-8 h-8" />
      </div>
    )
  }

  return (
    <div className="p-8 max-w-6xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Welcome back 👋</h1>
          <p className="text-white/50 mt-1">Your private AI study assistant is ready.</p>
        </div>
        <div className="flex items-center gap-3">
          <PrivacyBadge size="md" />
          <button
            onClick={handleDemo}
            disabled={demoLoading}
            className="btn-secondary text-sm"
          >
            {demoLoading ? <Spinner className="w-4 h-4" /> : <Zap className="w-4 h-4" />}
            Load Demo Data
          </button>
          <button
            onClick={() => navigate('/tutor')}
            className="btn-primary"
          >
            <Play className="w-4 h-4" />
            Start Study Session
          </button>
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          icon={BookOpen} label="Documents" color="bg-brand-600"
          value={stats?.documents_uploaded ?? 0}
          sub="uploaded"
        />
        <StatCard
          icon={TrendingUp} label="Topics Studied" color="bg-snap-purple"
          value={stats?.topics_studied ?? 0}
          sub="unique topics"
        />
        <StatCard
          icon={Trophy} label="Quiz Accuracy" color="bg-snap-green"
          value={`${stats?.quiz_accuracy ?? 0}%`}
          sub={`${stats?.total_questions_attempted ?? 0} questions`}
        />
        <StatCard
          icon={Flame} label="Study Streak" color="bg-snap-orange"
          value={`${stats?.study_streak ?? 0} days`}
          sub="keep it going!"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Weak topics */}
        <div className="card p-5 lg:col-span-1">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-snap-orange" />
              Needs Attention
            </h2>
          </div>
          {(stats?.weak_topics?.length ?? 0) === 0 ? (
            <p className="text-muted text-center py-6">No weak topics yet.<br />Complete a quiz to get started.</p>
          ) : (
            <div className="space-y-3">
              {stats!.weak_topics.map(t => (
                <div key={t.topic} className="flex items-center justify-between">
                  <span className="text-sm text-white/80 truncate flex-1 mr-3">{t.topic}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-snap-orange rounded-full"
                        style={{ width: `${t.score}%` }}
                      />
                    </div>
                    <span className="text-xs text-snap-orange font-medium w-9 text-right">{t.score}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {(stats?.weak_topics?.length ?? 0) > 0 && (
            <button
              onClick={() => navigate('/revision')}
              className="btn-primary w-full mt-4 text-sm justify-center"
            >
              Start Revision
            </button>
          )}
        </div>

        {/* Recent activity */}
        <div className="card p-5 lg:col-span-2">
          <h2 className="section-title mb-4">Recent Activity</h2>
          {(stats?.recent_activity?.length ?? 0) === 0 ? (
            <div className="text-center py-8">
              <p className="text-muted mb-4">No activity yet. Let's get started!</p>
              <div className="flex gap-3 justify-center">
                <button onClick={() => navigate('/library')} className="btn-secondary text-sm">
                  <Upload className="w-4 h-4" /> Upload Document
                </button>
                <button onClick={handleDemo} disabled={demoLoading} className="btn-primary text-sm">
                  <Zap className="w-4 h-4" /> Try Demo
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {stats!.recent_activity.map((a, i) => (
                <div key={i} className="flex items-center gap-3 py-2.5 border-b border-white/5 last:border-0">
                  {a.is_correct
                    ? <CheckCircle className="w-4 h-4 text-snap-green shrink-0" />
                    : <XCircle className="w-4 h-4 text-snap-red shrink-0" />
                  }
                  <span className="text-sm text-white/70 flex-1">
                    Quiz question on <span className="text-white/90">{a.topic || 'General'}</span>
                  </span>
                  <span className="text-xs text-white/30">
                    {a.timestamp ? new Date(a.timestamp).toLocaleDateString() : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-3 gap-4 mt-6">
        {[
          { label: 'Upload Study Material', desc: 'Add PDFs, notes, slides', icon: Upload, to: '/library', color: 'text-brand-400' },
          { label: 'Ask the AI Tutor', desc: 'Get grounded answers', icon: Zap, to: '/tutor', color: 'text-snap-purple' },
          { label: 'Generate Quiz', desc: 'Test your knowledge', icon: Trophy, to: '/quiz', color: 'text-snap-green' },
        ].map(a => (
          <button
            key={a.to}
            onClick={() => navigate(a.to)}
            className="card p-5 text-left hover:border-white/20 hover:bg-white/5 transition-all duration-200 group"
          >
            <a.icon className={`w-6 h-6 mb-3 ${a.color}`} />
            <p className="font-medium text-white text-sm">{a.label}</p>
            <p className="text-xs text-white/40 mt-1">{a.desc}</p>
            <ChevronRight className="w-4 h-4 text-white/20 group-hover:text-white/50 mt-2 transition-colors" />
          </button>
        ))}
      </div>
    </div>
  )
}
