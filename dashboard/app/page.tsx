'use client'
import { useRippleSocket } from '../hooks/useRippleSocket'
import ServiceGrid from '../components/ServiceGrid'
import SummaryBar from '../components/SummaryBar'
import IncidentPanel from '../components/IncidentPanel'

const TOTAL_SERVICES = 20

export default function Dashboard() {
  const { services, summary, reset } = useRippleSocket()

  return (
    <div className="min-h-dvh bg-ripple-bg text-ripple-text flex flex-col">
      {/* Header */}
      <header className="border-b border-white/5 bg-ripple-surface/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            {/* Logo mark */}
            <div className="relative w-7 h-7 shrink-0">
              <div className="absolute inset-0 rounded border border-ripple-accent/40 rotate-45 scale-75" />
              <div className="absolute inset-0 rounded border border-ripple-hit/30 rotate-12 scale-90" />
              <div className="absolute inset-1 rounded-sm bg-ripple-accent/10" />
            </div>
            <div>
              <h1 className="font-mono text-sm font-bold text-ripple-text tracking-wider uppercase">
                Ripple
              </h1>
              <p className="font-mono text-[9px] text-ripple-subtle tracking-widest uppercase">
                Live Pattern Scan
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Reset button */}
            <button
              onClick={reset}
              className={[
                'font-mono text-[9px] uppercase tracking-widest px-2 py-1 rounded border transition-all duration-150 cursor-pointer',
                'border-white/10 text-ripple-subtle hover:border-white/20 hover:text-ripple-text',
                'focus:outline-none focus:ring-1 focus:ring-white/20',
              ].join(' ')}
              aria-label="Reset scan state"
            >
              Reset
            </button>

            {/* Live badge */}
            {summary.connected && (
              <div className="flex items-center gap-1.5 border border-ripple-clean/30 bg-ripple-clean/5 rounded px-2 py-1 animate-slide-in">
                <span className="w-1.5 h-1.5 rounded-full bg-ripple-clean animate-pulse" />
                <span className="font-mono text-[9px] font-semibold text-ripple-clean uppercase tracking-widest">
                  Streaming
                </span>
              </div>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 py-6 flex flex-col gap-5">
        {/* Incident context */}
        <IncidentPanel />

        {/* Summary */}
        <div className="rounded-lg border border-white/5 bg-ripple-surface p-4">
          <SummaryBar summary={summary} total={TOTAL_SERVICES} />
        </div>

        {/* Grid label */}
        <div className="flex items-center gap-3">
          <span className="font-mono text-[9px] text-ripple-subtle uppercase tracking-widest">
            Services — {TOTAL_SERVICES} total
          </span>
          <div className="flex-1 h-px bg-white/5" />
          {/* Legend */}
          <div className="flex items-center gap-4">
            {[
              { color: 'bg-ripple-subtle', label: 'Idle' },
              { color: 'bg-ripple-scan', label: 'Scanning' },
              { color: 'bg-ripple-hit', label: 'Hit' },
              { color: 'bg-ripple-clean', label: 'Clean' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1">
                <span className={['w-1.5 h-1.5 rounded-full', color].join(' ')} aria-hidden="true" />
                <span className="font-mono text-[9px] text-ripple-subtle uppercase tracking-wider">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Service grid */}
        <ServiceGrid services={services} />

        {/* Footer */}
        <footer className="mt-auto pt-4 border-t border-white/5">
          <p className="font-mono text-[9px] text-ripple-subtle text-center tracking-wider">
            Ripple · Google Cloud Rapid Agent Hackathon · Dynatrace Track
          </p>
        </footer>
      </main>
    </div>
  )
}
