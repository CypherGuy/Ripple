import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Ripple — Architecture & Analysis',
}

export default function AboutLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
