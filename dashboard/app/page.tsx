'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useRippleSocket } from '../hooks/useRippleSocket'
import ServiceGrid from '../components/ServiceGrid'
import SummaryBar from '../components/SummaryBar'
import IncidentPanel from '../components/IncidentPanel'

const TOTAL_SERVICES = 12
const ORCHESTRATOR_URL = process.env.NEXT_PUBLIC_ORCHESTRATOR_URL
  ?? (typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? 'https://ripple-orchestrator-mctjeick3a-nw.a.run.app'
    : 'http://localhost:8000')

export default function Dashboard() {
  const { services, summary, reset } = useRippleSocket()
  const [closing, setClosing] = useState(false)
  const [closeResult, setCloseResult] = useState<string | null>(null)
  const [triggering, setTriggering] = useState(false)
  const [triggerResult, setTriggerResult] = useState<string | null>(null)
  const [approvingServices, setApprovingServices] = useState<Set<string>>(new Set())

  async function triggerDemo() {
    setTriggering(true)
    setTriggerResult(null)
    reset()
    try {
      const r = await fetch(`${ORCHESTRATOR_URL}/demo/trigger`, { method: 'POST' })
      if (r.ok) {
        setTriggerResult('Pipeline triggered')
      } else {
        setTriggerResult(`Error ${r.status}`)
      }
    } catch {
      setTriggerResult('Failed to trigger')
    } finally {
      setTriggering(false)
      setTimeout(() => setTriggerResult(null), 4000)
    }
  }

  async function approveService(service: string) {
    setApprovingServices(prev => new Set(prev).add(service))
    try {
      const internalSecret = process.env.NEXT_PUBLIC_ADMIN_SECRET ?? ''
      await fetch(`${ORCHESTRATOR_URL}/internal/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Internal-Secret': internalSecret },
        body: JSON.stringify({ service }),
      })
    } finally {
      setApprovingServices(prev => { const s = new Set(prev); s.delete(service); return s })
    }
  }

  function skipService(service: string) {
    reset()
  }

  async function closeAllMrs() {
    setClosing(true)
    setCloseResult(null)
    try {
      const r = await fetch(`${ORCHESTRATOR_URL}/admin/close-mrs`, {
        method: 'POST',
        headers: { 'X-Admin-Secret': process.env.NEXT_PUBLIC_ADMIN_SECRET ?? '' },
      })
      const data = await r.json()
      setCloseResult(`Closed ${data.closed} MR${data.closed !== 1 ? 's' : ''}`)
      reset()
    } catch {
      setCloseResult('Failed to close MRs')
    } finally {
      setClosing(false)
      setTimeout(() => setCloseResult(null), 4000)
    }
  }

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
            {/* Close all MRs button */}
            <div className="flex items-center gap-2">
              <button
                onClick={closeAllMrs}
                disabled={closing}
                className={[
                  'font-mono text-[9px] uppercase tracking-widest px-2 py-1 rounded border transition-all duration-150 cursor-pointer',
                  'border-ripple-hit/40 text-ripple-hit/70 hover:border-ripple-hit/70 hover:text-ripple-hit',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                  'focus:outline-none focus:ring-1 focus:ring-ripple-hit/30',
                ].join(' ')}
                aria-label="Close all open Ripple MRs in GitLab"
              >
                {closing ? 'Closing…' : 'Close MRs'}
              </button>
              {closeResult && (
                <span className="font-mono text-[9px] text-ripple-clean animate-slide-in">
                  {closeResult}
                </span>
              )}
            </div>

            {/* Trigger Demo button */}
            <div className="flex items-center gap-2">
              <button
                onClick={triggerDemo}
                disabled={triggering}
                className={[
                  'font-mono text-[9px] uppercase tracking-widest px-2 py-1 rounded border transition-all duration-150 cursor-pointer',
                  'border-ripple-accent/60 text-ripple-accent hover:border-ripple-accent hover:bg-ripple-accent/10',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                  'focus:outline-none focus:ring-1 focus:ring-ripple-accent/40',
                ].join(' ')}
                aria-label="Trigger demo pipeline run"
              >
                {triggering ? 'Triggering…' : 'Trigger Demo'}
              </button>
              {triggerResult && (
                <span className="font-mono text-[9px] text-ripple-accent animate-slide-in">
                  {triggerResult}
                </span>
              )}
            </div>

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

            {/* About link */}
            <Link
              href="/about"
              className="font-mono text-[9px] uppercase tracking-widest px-2 py-1 rounded border border-white/10 text-ripple-subtle hover:border-white/20 hover:text-ripple-text transition-colors"
            >
              About
            </Link>

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
        <ServiceGrid services={services} onApprove={approveService} onSkip={skipService} />

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
