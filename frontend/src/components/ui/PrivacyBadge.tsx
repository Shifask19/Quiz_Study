import { Shield } from 'lucide-react'
import clsx from 'clsx'

interface Props {
  size?: 'sm' | 'md'
  className?: string
}

export default function PrivacyBadge({ size = 'sm', className }: Props) {
  return (
    <span className={clsx(
      'badge bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
      size === 'md' && 'text-sm px-3 py-1.5',
      className
    )}>
      <Shield className={clsx('shrink-0', size === 'sm' ? 'w-3 h-3' : 'w-4 h-4')} />
      Private / On-Device
    </span>
  )
}
