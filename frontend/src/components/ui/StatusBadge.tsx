import clsx from 'clsx'
import Spinner from './Spinner'

type Status = 'pending' | 'processing' | 'ready' | 'failed'

const config: Record<Status, { label: string; cls: string }> = {
  pending:    { label: 'Pending',    cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
  processing: { label: 'Processing', cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  ready:      { label: 'Ready',      cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  failed:     { label: 'Failed',     cls: 'bg-red-500/10 text-red-400 border-red-500/20' },
}

export default function StatusBadge({ status }: { status: Status }) {
  const c = config[status] ?? config.pending
  return (
    <span className={clsx('badge border', c.cls)}>
      {status === 'processing' && <Spinner className="w-2.5 h-2.5" />}
      {c.label}
    </span>
  )
}
