'use client'
import type { ServiceState } from '../hooks/useRippleSocket'
import ServiceTile from './ServiceTile'

const ALL_SERVICES = [
  'http-monitor', 'ssl-monitor', 'api-monitor', 'github-monitor',
  'dns-checker', 'latency-monitor', 'slack-notifier', 'email-notifier',
  'webhook-dispatcher', 'incident-manager', 'metrics-collector', 'report-generator',
]

interface Props {
  services: Map<string, ServiceState>
}

export default function ServiceGrid({ services }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
      {ALL_SERVICES.map((name) => (
        <ServiceTile
          key={name}
          name={name}
          state={services.get(name) ?? {
            status: 'idle',
            mrUrl: null,
            fileHit: null,
            confidence: null,
            timestamp: null,
          }}
        />
      ))}
    </div>
  )
}
