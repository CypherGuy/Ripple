'use client'
import { useState, useEffect } from 'react'
import type { ScanSummary } from '../hooks/useRippleSocket'

interface Props {
  summary: ScanSummary
  total: number
}

function Stat({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className={['font-mono text-2xl font-bold tabular-nums tracking-tight animate-count-up', color].join(' ')}>
        {value}
      </span>
      <span className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle">{label}</span>
    </div>
  )
}

export default function SummaryBar({ summary, total }: Props) {
  const [tick, setTick] = useState(Date.now())

  useEffect(() => {
    if (!summary.pipelineStartMs || summary.pipelineEndMs) return
    const id = setInterval(() => setTick(Date.now()), 1000)
    return () => clearInterval(id)
  }, [summary.pipelineStartMs, summary.pipelineEndMs])

  const progress = total > 0 ? (summary.scanned / total) * 100 : 0
  const elapsedMs = summary.pipelineEndMs
    ? summary.pipelineEndMs - summary.pipelineStartMs!
    : summary.pipelineStartMs ? tick - summary.pipelineStartMs : null

  return (
    <div className="flex flex-col gap-3">
      {/* Counters */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Stat value={summary.scanned} label={`/ ${total} scanned`} color="text-ripple-text" />

        <div className="h-8 w-px bg-white/5" aria-hidden="true" />
        <Stat value={summary.hits} label="hits found" color="text-ripple-hit" />

        <div className="h-8 w-px bg-white/5" aria-hidden="true" />
        <Stat value={summary.clean} label="clean" color="text-ripple-clean" />

        <div className="h-8 w-px bg-white/5" aria-hidden="true" />
        <Stat value={summary.mrsOpened} label="MRs opened" color="text-ripple-accent" />

        {/* Elapsed time */}
        {elapsedMs !== null && (
          <div className="flex flex-col items-center gap-0.5">
            <span className="font-mono text-2xl font-bold tabular-nums tracking-tight text-ripple-subtle">
              {`${(elapsedMs / 1000).toFixed(summary.pipelineEndMs ? 1 : 0)}s`}
            </span>
            <span className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle">
              {summary.pipelineEndMs ? 'completed in' : 'elapsed'}
            </span>
          </div>
        )}

        {/* Connection indicator */}
        <div className="ml-auto flex items-center gap-1.5">
          <span
            className={[
              'w-1.5 h-1.5 rounded-full',
              summary.connected
                ? 'bg-ripple-clean shadow-[0_0_6px_rgba(34,197,94,0.8)] animate-pulse'
                : 'bg-ripple-subtle',
            ].join(' ')}
            aria-hidden="true"
          />
          <span className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle">
            {summary.connected ? 'Live' : 'Reconnecting'}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="relative h-0.5 w-full bg-white/5 rounded-full overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full bg-ripple-accent transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
          role="progressbar"
          aria-valuenow={summary.scanned}
          aria-valuemin={0}
          aria-valuemax={total}
        />
        {progress > 0 && progress < 100 && (
          <div
            className="absolute top-0 h-full w-12 animate-glow-line"
            style={{
              left: `${progress}%`,
              background: 'linear-gradient(90deg, rgba(99,102,241,0.4), transparent)',
            }}
          />
        )}
      </div>
    </div>
  )
}
