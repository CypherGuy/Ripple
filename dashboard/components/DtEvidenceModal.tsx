'use client'

import { useEffect, useRef } from 'react'
import type { DtEvidence } from '../hooks/useRippleSocket'

// Strip Dynatrace internal metadata from the raw MCP problem description,
// leaving only the plain-English root cause sentences.
function cleanRootCause(raw: string): string {
  // Take only text after "Availability:" if present - that's where DT puts the actual description
  const afterAvailability = raw.split(/Availability:/i).pop() ?? raw
  // Strip markdown: headers (#), bold (**text**), and excess whitespace
  return afterAvailability
    .replace(/#+\s*/g, '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

const DT_ENV = 'jfr54188.apps.dynatrace.com'
const MCP_ENDPOINT = `https://${DT_ENV}/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp`

interface Props {
  evidence: DtEvidence
  onClose: () => void
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle/50">{label}</span>
      <span className="font-mono text-[11px] text-ripple-text/80">{value}</span>
    </div>
  )
}

export default function DtEvidenceModal({ evidence, onClose }: Props) {
  const backdropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const ctx = evidence.incidentContext
  const incidentId = (ctx.incident_id ?? ctx.display_id ?? '') as string
  const rawTitle = (ctx.root_cause_summary ?? ctx['event.description'] ?? '') as string
  const title = cleanRootCause(rawTitle)
  const duration = ctx.duration_minutes as number | undefined
  const cost = (ctx.estimated_cost ?? '') as string
  const argsJson = JSON.stringify(evidence.toolCall.arguments, null, 2)

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => { if (e.target === backdropRef.current) onClose() }}
    >
      <div className="relative w-full max-w-xl mx-4 rounded-xl border border-ripple-hit/30 bg-ripple-bg shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5 bg-ripple-hit/5">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className="text-ripple-hit shrink-0">
            <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.2"/>
            <path d="M4 7h6M4 4.5h6M4 9.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
          <span className="font-mono text-[11px] font-bold text-ripple-hit tracking-wider uppercase">
            Dynatrace MCP Evidence
          </span>
          <button
            onClick={onClose}
            className="ml-auto text-ripple-subtle hover:text-ripple-text transition-colors"
            aria-label="Close"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className="p-5 flex flex-col gap-5">
          {/* Gemini's plain-English interpretation — lead with this */}
          {evidence.rationale && (
            <section className="flex flex-col gap-2">
              <h3 className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle/50">Gemini Risk Assessment</h3>
              <p className="font-mono text-[11px] text-ripple-text/80 bg-ripple-accent/5 rounded-lg border border-ripple-accent/20 px-3 py-2 leading-relaxed">
                {evidence.rationale}
              </p>
            </section>
          )}

          {evidence.pattern && (
            <section className="flex flex-col gap-2">
              <h3 className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle/50">Pattern Flagged</h3>
              <p className="font-mono text-[11px] text-ripple-text/80 bg-black/30 rounded-lg border border-white/5 px-3 py-2">
                {evidence.pattern}
              </p>
            </section>
          )}

          {/* Raw DT incident evidence */}
          {incidentId && (
            <section className="flex flex-col gap-2">
              <h3 className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle/50">Dynatrace Incident</h3>
              <div className="rounded-lg border border-ripple-hit/20 bg-ripple-hit/5 p-3 flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-ripple-hit shrink-0" />
                  <span className="font-mono text-[11px] font-bold text-ripple-hit">{incidentId}</span>
                </div>
                {title && (
                  <div className="flex flex-col gap-0.5">
                    <span className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle/50">root cause</span>
                    <ul className="flex flex-col gap-1.5 mt-0.5">
                      {title.split(/\s+[-—]\s+/).filter(s => s.trim().length > 0).map((line, i) => (
                        <li key={i} className="flex items-center gap-2">
                          <span className="text-ripple-hit leading-none shrink-0">&#8226;</span>
                          <span className="font-mono text-[11px] text-ripple-text/80 leading-snug">{line.trim()}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex gap-6">
                  {duration !== undefined && <Field label="duration" value={`${duration} min`} />}
                  {cost && <Field label="est. cost" value={cost} />}
                </div>
              </div>
            </section>
          )}

          {/* Raw MCP call — technical detail at bottom */}
          <section className="flex flex-col gap-2">
            <h3 className="font-mono text-[9px] uppercase tracking-widest text-ripple-subtle/50">MCP Tool Call</h3>
            <div className="rounded-lg border border-white/5 bg-black/30 p-3 flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[9px] text-ripple-subtle/40 w-16 shrink-0">tool</span>
                <span className="font-mono text-[11px] text-ripple-scan">{evidence.toolCall.tool}</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="font-mono text-[9px] text-ripple-subtle/40 w-16 shrink-0 pt-0.5">args</span>
                <pre className="font-mono text-[10px] text-ripple-text/70 whitespace-pre-wrap">{argsJson}</pre>
              </div>
              <div className="flex items-start gap-2 mt-1 pt-2 border-t border-white/5">
                <span className="font-mono text-[9px] text-ripple-subtle/40 w-16 shrink-0 pt-0.5">endpoint</span>
                <span className="font-mono text-[9px] text-ripple-text/40 break-all">{MCP_ENDPOINT}</span>
              </div>
            </div>
          </section>
        </div>

        <div className="px-5 py-3 border-t border-white/5 bg-black/20">
          <p className="font-mono text-[9px] text-ripple-subtle/40">
            Data fetched live via Dynatrace MCP during this scan · tenant {DT_ENV}
          </p>
        </div>
      </div>
    </div>
  )
}
