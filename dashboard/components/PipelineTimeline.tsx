'use client'
import { useState } from 'react'
import type { PipelineTimeline } from '../hooks/useRippleSocket'

interface Props {
  timeline: PipelineTimeline
}

const ALL_SERVICES = [
  'http-monitor', 'ssl-monitor', 'api-monitor', 'github-monitor',
  'dns-checker', 'latency-monitor', 'slack-notifier', 'email-notifier',
  'webhook-dispatcher', 'incident-manager', 'metrics-collector', 'report-generator',
]

function fmt(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export default function PipelineTimeline({ timeline }: Props) {
  const [open, setOpen] = useState(false)

  const { startMs, intelligenceEndMs, services } = timeline
  if (!startMs) return null

  const now = Date.now()

  // Pipeline is complete when all known services have scanEnd set
  const settledCount = Object.values(services).filter(s => s.scanEndMs !== null).length
  const isComplete = settledCount >= ALL_SERVICES.length

  // Freeze totalMs once complete — don't let it grow after the run finishes
  const settledMax = Math.max(
    intelligenceEndMs ? intelligenceEndMs - startMs : 0,
    ...Object.values(services).map(s => (s.mrOpenedMs ?? s.scanEndMs ?? s.scanStartMs ?? startMs) - startMs),
    0,
  )
  const totalMs = isComplete ? settledMax : Math.max(settledMax, now - startMs)

  function pct(ms: number | null | undefined, fallback = now): number {
    if (ms == null) return Math.min((fallback - startMs!) / totalMs * 100, 100)
    return Math.min(((ms - startMs!) / totalMs) * 100, 100)
  }

  const intelDuration = intelligenceEndMs ? intelligenceEndMs - startMs : null

  return (
    <div className="rounded-lg border border-white/5 bg-ripple-surface">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left focus:outline-none"
      >
        <span className="font-mono text-[10px] text-ripple-subtle uppercase tracking-widest">
          Pipeline Trace
          {intelDuration && (
            <span className="ml-3 text-ripple-text/40">
              {isComplete ? `completed in ${fmt(settledMax)}` : `running ${fmt(now - startMs)}`}
            </span>
          )}
        </span>
        <span className="font-mono text-[10px] text-ripple-subtle">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 flex flex-col gap-1.5">
          {/* Legend */}
          <div className="flex items-center gap-4 mb-2">
            {[
              { color: 'bg-ripple-accent/70', label: 'Intelligence' },
              { color: 'bg-ripple-scan/70', label: 'Scan phase' },
              { color: 'bg-blue-500/70', label: 'Fix generation (hit)' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-sm ${color}`} />
                <span className="font-mono text-[8px] text-ripple-subtle uppercase tracking-wider">{label}</span>
              </div>
            ))}
          </div>

          {/* Intelligence row */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-[9px] text-ripple-subtle w-32 shrink-0 truncate">Intelligence</span>
            <div className="flex-1 relative h-4 bg-white/5 rounded overflow-hidden">
              {intelligenceEndMs && (
                <div
                  className="absolute top-0 left-0 h-full bg-ripple-accent/70 rounded"
                  style={{ width: `${pct(intelligenceEndMs)}%` }}
                />
              )}
              {!intelligenceEndMs && (
                <div className="absolute top-0 left-0 h-full bg-ripple-accent/40 animate-pulse rounded" style={{ width: '100%' }} />
              )}
            </div>
            <span className="font-mono text-[9px] text-ripple-subtle w-10 text-right shrink-0">
              {intelDuration ? fmt(intelDuration) : '…'}
            </span>
          </div>

          <div className="h-px bg-white/5 my-1" />

          {/* Service rows */}
          {ALL_SERVICES.map(name => {
            const svc = services[name]
            if (!svc && !Object.keys(services).length) return null

            const scanStart = svc?.scanStartMs
            const scanEnd = svc?.scanEndMs
            const mrOpened = svc?.mrOpenedMs
            const outcome = svc?.outcome

            const scanLeft = scanStart ? pct(scanStart) : 0
            const scanWidth = scanStart ? (scanEnd ? pct(scanEnd) - pct(scanStart) : pct(undefined, now) - pct(scanStart)) : 0
            const fixLeft = scanEnd ? pct(scanEnd) : 0
            const fixWidth = scanEnd ? (mrOpened ? pct(mrOpened) - pct(scanEnd) : 0) : 0

            return (
              <div key={name} className="flex items-center gap-2">
                <span className="font-mono text-[9px] text-ripple-subtle w-32 shrink-0 truncate">{name}</span>
                <div className="flex-1 relative h-4 bg-white/5 rounded overflow-hidden">
                  {scanWidth > 0 && (
                    <div
                      className={`absolute top-0 h-full rounded ${scanEnd ? 'bg-ripple-scan/70' : 'bg-ripple-scan/40 animate-pulse'}`}
                      style={{ left: `${scanLeft}%`, width: `${Math.max(scanWidth, 1)}%` }}
                    />
                  )}
                  {fixWidth > 0 && (
                    <div
                      className="absolute top-0 h-full bg-blue-500/60 rounded"
                      style={{ left: `${fixLeft}%`, width: `${Math.max(fixWidth, 1)}%` }}
                    />
                  )}
                </div>
                <span className="font-mono text-[9px] w-10 text-right shrink-0">
                  {!svc ? (
                    <span className="text-ripple-subtle/30">—</span>
                  ) : mrOpened ? (
                    <span className="text-blue-400">{fmt(mrOpened - (scanStart ?? startMs!))}</span>
                  ) : scanEnd ? (
                    <span className={outcome === 'clean' ? 'text-ripple-clean' : 'text-ripple-scan'}>{fmt(scanEnd - (scanStart ?? startMs!))}</span>
                  ) : (
                    <span className="text-ripple-scan">…</span>
                  )}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
