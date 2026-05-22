'use client'

import { useState } from 'react'
import type { DtEvidence } from '../hooks/useRippleSocket'
import DtEvidenceModal from './DtEvidenceModal'

interface Incident {
  id: string
  title: string
  duration: number
  cost: string
}

const DEMO_INCIDENT: Incident = {
  id: 'P-26051',
  title: 'PulseCheck ssl-monitor hung on slow cert check',
  duration: 47,
  cost: '£23,000',
}

export default function IncidentPanel({
  incident = DEMO_INCIDENT,
  riskScore = null,
  dtEvidence = null,
}: {
  incident?: Incident
  riskScore?: number | null
  dtEvidence?: DtEvidence | null
}) {
  const [showModal, setShowModal] = useState(false)

  return (
    <>
      <div className="flex items-center gap-3 px-3 py-2 rounded-lg border border-ripple-hit/20 bg-ripple-hit/5">
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-ripple-hit animate-pulse" aria-hidden="true" />
          <span className="font-mono text-[10px] font-bold text-ripple-hit tracking-wider">{incident.id}</span>
        </div>

        <div className="h-4 w-px bg-white/10" aria-hidden="true" />

        <p className="font-mono text-[10px] text-ripple-text/60 truncate flex-1 hidden sm:block">
          {incident.title}
        </p>

        <div className="flex items-center gap-3 shrink-0 ml-auto">
          <span className="font-mono text-[10px] text-ripple-subtle">
            <span className="text-ripple-scan font-semibold">{incident.duration}m</span> outage
          </span>
          <span className="font-mono text-[10px] text-ripple-subtle">
            <span className="text-ripple-hit font-semibold">{incident.cost}</span> est. cost
          </span>
          {riskScore !== null && (
            <span className="font-mono text-[10px] text-ripple-subtle">
              risk{' '}
              <span className="text-ripple-hit font-semibold">{riskScore}/10</span>
            </span>
          )}
          {dtEvidence && (
            <button
              onClick={() => setShowModal(true)}
              className="relative font-mono text-[10px] font-bold uppercase tracking-wider text-white bg-ripple-accent/80 hover:bg-ripple-accent transition-all rounded px-2.5 py-1 shadow-[0_0_12px_rgba(99,102,241,0.5)] hover:shadow-[0_0_20px_rgba(99,102,241,0.8)] animate-pulse-subtle"
              title="View raw Dynatrace MCP response"
            >
              <span className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-white/80 animate-ping absolute left-2 top-1/2 -translate-y-1/2" aria-hidden="true" />
                <span className="pl-2">View DT Evidence ↗</span>
              </span>
            </button>
          )}
        </div>
      </div>

      {showModal && dtEvidence && (
        <DtEvidenceModal evidence={dtEvidence} onClose={() => setShowModal(false)} />
      )}
    </>
  )
}
