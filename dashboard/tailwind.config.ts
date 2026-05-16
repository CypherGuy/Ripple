import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}', './hooks/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ripple: {
          bg:       '#080D1A',
          surface:  '#0D1426',
          card:     '#111827',
          border:   'rgba(99,102,241,0.12)',
          muted:    '#1E293B',
          hit:      '#EF4444',
          clean:    '#22C55E',
          scan:     '#F59E0B',
          accent:   '#6366F1',
          text:     '#E2E8F0',
          subtle:   '#64748B',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        'scan-ring': {
          '0%':   { transform: 'scale(0.85)', opacity: '0.9' },
          '100%': { transform: 'scale(1.5)',  opacity: '0' },
        },
        'hit-pulse': {
          '0%, 100%': { boxShadow: '0 0 8px rgba(239,68,68,0.35)' },
          '50%':       { boxShadow: '0 0 28px rgba(239,68,68,0.7)' },
        },
        'clean-fade': {
          '0%':   { boxShadow: '0 0 16px rgba(34,197,94,0.5)' },
          '100%': { boxShadow: '0 0 4px rgba(34,197,94,0.15)' },
        },
        'count-up': {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%':   { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'glow-line': {
          '0%, 100%': { opacity: '0.4' },
          '50%':       { opacity: '1' },
        },
      },
      animation: {
        'scan-ring':  'scan-ring 1.4s ease-out infinite',
        'hit-pulse':  'hit-pulse 2s ease-in-out infinite',
        'clean-fade': 'clean-fade 0.8s ease-out forwards',
        'count-up':   'count-up 0.25s ease-out forwards',
        'slide-in':   'slide-in 0.3s ease-out forwards',
        'glow-line':  'glow-line 2.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}

export default config
