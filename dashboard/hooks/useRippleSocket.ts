'use client'
import { useEffect, useRef, useState } from 'react'

export type ServiceStatus = 'idle' | 'scanning' | 'hit' | 'clean' | 'requires_approval'

export interface ServiceState {
  status: ServiceStatus
  mrUrl: string | null
  fileHit: string | null
  confidence: number | null
  timestamp: string | null
  riskScore: number | null
  pattern: string | null
  evaluatedOn: 'incident_context' | 'technical_merit' | null
  correctionIterations: number | null
  incidentId: string | null
  feedbackOutcome: 'merged' | 'closed' | null
}

export interface ScanSummary {
  scanned: number
  hits: number
  clean: number
  mrsOpened: number
  connected: boolean
  riskScore: number | null
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL
  ?? (typeof window !== 'undefined' && window.location.hostname !== 'localhost'
    ? 'wss://ripple-orchestrator-mctjeick3a-nw.a.run.app/ws'
    : 'ws://localhost:8000/ws')

export function useRippleSocket() {
  const [services, setServices] = useState<Map<string, ServiceState>>(new Map())
  const [summary, setSummary] = useState<ScanSummary>({
    scanned: 0, hits: 0, clean: 0, mrsOpened: 0, connected: false, riskScore: null,
  })
  const ws = useRef<WebSocket | null>(null)
  const settled = useRef<Set<string>>(new Set())
  // Deduplicate mr_opened by URL so double-connection or duplicate events don't inflate the counter
  const settledMrUrls = useRef<Set<string>>(new Set())

  useEffect(() => {
    let destroyed = false
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    function connect() {
      if (destroyed) return
      const socket = new WebSocket(WS_URL)
      ws.current = socket

      socket.onopen = () => {
        if (destroyed) { socket.close(); return }
        setSummary(s => ({ ...s, connected: true }))
      }

      socket.onclose = () => {
        setSummary(s => ({ ...s, connected: false }))
        if (!destroyed) reconnectTimer = setTimeout(connect, 2000)
      }

      socket.onerror = () => socket.close()

      socket.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          const svc: string = event.service

          setServices(prev => {
            const next = new Map(prev)
            const current = next.get(svc) ?? {
              status: 'idle' as ServiceStatus,
              mrUrl: null, fileHit: null, confidence: null, timestamp: null,
              riskScore: null, pattern: null, evaluatedOn: null, correctionIterations: null, incidentId: null,
              feedbackOutcome: null,
            }

            if (event.event === 'agent_started') {
              next.set(svc, { ...current, status: 'scanning', timestamp: event.timestamp })
            } else if (event.event === 'hit_found') {
              next.set(svc, {
                status: 'hit',
                mrUrl: event.data?.mr_url ?? null,
                fileHit: event.data?.file_path ?? null,
                confidence: event.data?.confidence ?? null,
                timestamp: event.timestamp,
                riskScore: null,
                pattern: null,
                evaluatedOn: null,
                correctionIterations: null,
                incidentId: null,
                feedbackOutcome: null,
              })
              if (!settled.current.has(svc)) {
                settled.current.add(svc)
                setSummary(s => ({ ...s, scanned: s.scanned + 1, hits: s.hits + 1 }))
              }
            } else if (event.event === 'no_hit') {
              next.set(svc, { ...current, status: 'clean', timestamp: event.timestamp })
              if (!settled.current.has(svc)) {
                settled.current.add(svc)
                setSummary(s => ({ ...s, scanned: s.scanned + 1, clean: s.clean + 1 }))
              }
            } else if (event.event === 'risk_scored') {
              setSummary(s => ({ ...s, riskScore: event.risk_score ?? null }))
            } else if (event.event === 'requires_approval') {
              next.set(svc, {
                ...current,
                status: 'requires_approval',
                riskScore: event.risk_score ?? null,
                pattern: event.pattern ?? null,
                timestamp: event.timestamp ?? null,
              })
            } else if (event.event === 'feedback_recorded') {
              next.set(svc, {
                ...current,
                feedbackOutcome: event.outcome ?? null,
              })
            } else if (event.event === 'mr_opened') {
              next.set(svc, {
                ...current,
                mrUrl: event.mr_url,
                evaluatedOn: event.evaluated_on ?? null,
                correctionIterations: event.correction_iterations ?? null,
                incidentId: event.incident_id ?? null,
              })
              if (event.mr_url && !settledMrUrls.current.has(event.mr_url)) {
                settledMrUrls.current.add(event.mr_url)
                setSummary(s => ({ ...s, mrsOpened: s.mrsOpened + 1 }))
              }
            }

            return next
          })
        } catch { /* ignore malformed events */ }
      }
    }

    connect()
    return () => {
      destroyed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      ws.current?.close()
    }
  }, [])

  function reset() {
    settled.current.clear()
    settledMrUrls.current.clear()
    setServices(new Map())
    setSummary(s => ({ ...s, scanned: 0, hits: 0, clean: 0, mrsOpened: 0, riskScore: null }))
  }

  return { services, summary, reset }
}
