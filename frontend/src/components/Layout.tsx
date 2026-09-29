import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard, BookOpen, MessageSquare, Trophy,
  RefreshCw, BarChart2, Settings, Cpu, Zap,
} from 'lucide-react'
import clsx from 'clsx'
import PrivacyBadge from './ui/PrivacyBadge'

const nav = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/library',   icon: BookOpen,        label: 'My Library' },
  { to: '/tutor',     icon: MessageSquare,   label: 'AI Tutor' },
  { to: '/quiz',      icon: Trophy,          label: 'Quiz Lab' },
  { to: '/revision',  icon: RefreshCw,       label: 'Revision' },
  { to: '/analytics', icon: BarChart2,       label: 'Analytics' },
  { to: '/benchmark', icon: Cpu,             label: 'On-Device AI' },
  { to: '/settings',  icon: Settings,        label: 'Settings' },
]

export default function Layout() {
  return (
    <div className="flex h-screen overflow-hidden bg-[#0f1117]">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 flex flex-col border-r border-white/5 bg-[#12151f]">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-snap-purple flex items-center justify-center shrink-0">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="font-bold text-white text-base tracking-tight">SnapStudy</span>
              <p className="text-[10px] text-white/40 -mt-0.5">Private AI Tutor</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          {nav.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx('nav-item', isActive && 'nav-item-active')
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Bottom privacy */}
        <div className="px-4 py-4 border-t border-white/5">
          <PrivacyBadge size="sm" />
          <p className="text-[10px] text-white/30 mt-2 leading-relaxed">
            Study materials are processed locally on your device.
          </p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
