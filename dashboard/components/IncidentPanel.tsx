'use client'

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

export default function IncidentPanel({ incident = DEMO_INCIDENT }: { incident?: Incident }) {
  return (
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
      </div>
    </div>
  )
}
