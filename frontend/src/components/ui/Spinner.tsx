import clsx from 'clsx'

export default function Spinner({ className }: { className?: string }) {
  return (
    <div className={clsx(
      'inline-block rounded-full border-2 border-white/10 border-t-brand-500 animate-spin',
      className ?? 'w-5 h-5'
    )} />
  )
}
