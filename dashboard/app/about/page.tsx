'use client'
import Link from 'next/link'

const CHECK = () => (
  <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4 shrink-0 text-ripple-clean" aria-hidden="true">
    <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
    <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

const CROSS = () => (
  <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4 shrink-0 text-ripple-subtle" aria-hidden="true">
    <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
    <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
)

const PLAN = () => (
  <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4 shrink-0 text-ripple-scan" aria-hidden="true">
    <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" strokeDasharray="3 2" />
    <path d="M8 5v3.5l2 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
)

const UNIQUE = () => (
  <span className="font-mono text-[9px] text-ripple-accent border border-ripple-accent/40 bg-ripple-accent/10 rounded px-1 py-0.5 uppercase tracking-widest">
    only
  </span>
)

const services = [
  { name: 'GitLab Webhook', desc: 'receives PR open/update event', color: 'border-ripple-accent/40 bg-ripple-accent/5 text-ripple-accent' },
  { name: 'Orchestrator', desc: 'port 8000 · coordinates the pipeline', color: 'border-ripple-accent/60 bg-ripple-accent/10 text-ripple-accent' },
  { name: 'Intelligence', desc: 'port 8001 · extracts risk pattern from Dynatrace', color: 'border-blue-500/40 bg-blue-500/5 text-blue-400' },
  { name: 'Scanner', desc: 'port 8002 · 12 agents fan out in parallel', color: 'border-amber-500/40 bg-amber-500/5 text-amber-400' },
  { name: 'Fix Factory', desc: 'port 8003 · generates fix · self-corrects · opens MRs', color: 'border-ripple-hit/40 bg-ripple-hit/5 text-ripple-hit' },
]

const mcps = [
  { name: 'Dynatrace MCP', role: 'Primary', desc: 'incident history, real traces, service maps, root cause' },
  { name: 'GitLab REST API', role: 'Secondary', desc: 'codebase read/write, MR creation, fix precedent' },
  { name: 'MongoDB Atlas', role: 'Tertiary', desc: 'institutional memory — scars, wins, patterns from past scans' },
]

const differentiators = [
  { stat: '12', label: 'services scanned in parallel' },
  { stat: '1', label: 'PR triggers the entire sweep' },
  { stat: 'P-26051', label: 'real Dynatrace problem ID' },
  { stat: '£23k', label: 'quantified outage cost' },
]

type Cell = true | false | 'planned' | 'unique' | string
const matrix: { feature: string; argus: Cell; gitmem: Cell; ripple: Cell }[] = [
  { feature: 'Institutional memory', argus: 'git + reactions', gitmem: 'session scars/wins', ripple: 'unique' },
  { feature: 'Multi-pass review pipeline', argus: true, gitmem: false, ripple: true },
  { feature: 'Architecture & dependency tracing', argus: 'static analysis', gitmem: false, ripple: 'Dynatrace service maps' },
  { feature: 'Failure simulation', argus: 'hypothetical', gitmem: false, ripple: 'real incident replay' },
  { feature: 'Production cost quantification', argus: false, gitmem: false, ripple: 'unique' },
  { feature: 'Codebase-wide sweep', argus: false, gitmem: false, ripple: 'unique' },
  { feature: 'Autonomous fix MR creation', argus: false, gitmem: false, ripple: 'unique' },
  { feature: 'Feedback loop (MR outcomes)', argus: 'reviewer reactions', gitmem: 'scar/win', ripple: 'planned' },
  { feature: 'Self-learning over time', argus: true, gitmem: true, ripple: 'planned' },
  { feature: 'Self-hosted', argus: false, gitmem: true, ripple: true },
]

const secondary = [
  { tool: 'CodeRabbit', angle: 'AI PR review', memory: true, sweep: false, action: false, prod: false },
  { tool: 'Greptile', angle: 'Codebase understanding', memory: true, sweep: 'read-only', action: false, prod: false },
  { tool: 'Semgrep', angle: 'Static pattern matching', memory: true, sweep: true, action: false, prod: false },
  { tool: 'SonarQube', angle: 'Code quality + security', memory: false, sweep: true, action: false, prod: false },
  { tool: 'GitHub Copilot', angle: 'AI assistant + review', memory: true, sweep: true, action: false, prod: false },
  { tool: 'Ripple', angle: 'Production-grounded sweep', memory: true, sweep: true, action: true, prod: true },
]

function Cell({ val }: { val: Cell }) {
  if (val === true) return <CHECK />
  if (val === false) return <CROSS />
  if (val === 'planned') return <PLAN />
  if (val === 'unique') return (
    <div className="flex items-center gap-1.5">
      <CHECK />
      <UNIQUE />
    </div>
  )
  return <span className="font-mono text-[10px] text-ripple-subtle">{val}</span>
}

export default function About() {
  return (
    <div className="min-h-dvh bg-ripple-bg text-ripple-text font-sans">

      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-white/5 bg-ripple-bg/90 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative w-6 h-6 shrink-0">
              <div className="absolute inset-0 rounded border border-ripple-accent/40 rotate-45 scale-75" />
              <div className="absolute inset-0 rounded border border-ripple-hit/30 rotate-12 scale-90" />
              <div className="absolute inset-1 rounded-sm bg-ripple-accent/10" />
            </div>
            <span className="font-mono text-sm font-bold tracking-wider uppercase text-ripple-text">Ripple</span>
          </div>
          <nav className="flex items-center gap-6" aria-label="Page sections">
            <a href="#overview" className="font-mono text-[11px] text-ripple-subtle hover:text-ripple-text transition-colors uppercase tracking-widest">Overview</a>
            <a href="#architecture" className="font-mono text-[11px] text-ripple-subtle hover:text-ripple-text transition-colors uppercase tracking-widest">Architecture</a>
            <a href="#competitors" className="font-mono text-[11px] text-ripple-subtle hover:text-ripple-text transition-colors uppercase tracking-widest">Competitors</a>
            <Link
              href="/"
              className="font-mono text-[11px] border border-ripple-accent/30 text-ripple-accent hover:bg-ripple-accent/10 transition-colors rounded px-3 py-1 uppercase tracking-widest"
            >
              Live Demo →
            </Link>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-16 flex flex-col gap-24">

        {/* ── Hero ── */}
        <section id="overview" className="flex flex-col gap-8">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-ripple-accent border border-ripple-accent/30 rounded px-2 py-0.5 uppercase tracking-widest">Incident-grounded code review</span>
            <span className="font-mono text-[10px] text-ripple-subtle">Powered by Google ADK · Dynatrace · GitLab</span>
          </div>

          <div className="flex flex-col gap-4 max-w-4xl">
            <h1 className="text-4xl font-bold tracking-tight text-ripple-text leading-tight">
              Every other code review tool asks<br />
              <span className="text-ripple-subtle">"did this pattern appear before?"</span>
            </h1>
            <p className="text-3xl font-bold tracking-tight text-ripple-accent">
              Ripple asks "did this pattern cause an outage —<br />and where else is it hiding right now?"
            </p>
          </div>

          <p className="text-base text-ripple-subtle leading-relaxed max-w-3xl">
            Ripple detects dangerous code patterns in incoming GitLab PRs by checking whether that pattern has ever caused a real production incident in Dynatrace. When it finds a match, it fans out across every service simultaneously and opens targeted fix MRs — each grounded in the exact incident that proved why the pattern is dangerous.
          </p>

          {/* Key stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2">
            {differentiators.map(({ stat, label }) => (
              <div key={label} className="rounded-lg border border-white/5 bg-ripple-surface p-4 flex flex-col gap-1">
                <span className="font-mono text-2xl font-bold text-ripple-text">{stat}</span>
                <span className="font-mono text-[10px] text-ripple-subtle uppercase tracking-widest leading-snug">{label}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Architecture ── */}
        <section id="architecture" className="flex flex-col gap-10">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-bold text-ripple-text">Architecture</h2>
            <p className="text-sm text-ripple-subtle max-w-2xl">
              Four FastAPI microservices communicating via A2A protocol, orchestrated by Google ADK with Gemini 2.5 Flash. Deployed on Cloud Run.
            </p>
          </div>

          {/* Pipeline flow */}
          <div className="flex flex-col gap-2">
            {services.map((svc, i) => (
              <div key={svc.name} className="flex items-start gap-4">
                <div className="flex flex-col items-center gap-0 pt-2">
                  <div className={`w-2.5 h-2.5 rounded-full border-2 ${i === 0 ? 'border-ripple-accent bg-ripple-accent/30' : 'border-white/20 bg-white/5'}`} />
                  {i < services.length - 1 && <div className="w-px h-8 bg-white/10" />}
                </div>
                <div className={`flex-1 rounded-lg border p-3 ${svc.color}`}>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm font-bold">{svc.name}</span>
                    <span className="font-mono text-[10px] text-ripple-subtle">{svc.desc}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* MCPs */}
          <div className="flex flex-col gap-3">
            <h3 className="font-mono text-[11px] text-ripple-subtle uppercase tracking-widest">Three MCPs</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {mcps.map((mcp) => (
                <div key={mcp.name} className="rounded-lg border border-white/5 bg-ripple-surface p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-ripple-text">{mcp.name}</span>
                    <span className="font-mono text-[9px] text-ripple-accent border border-ripple-accent/30 rounded px-1.5 py-0.5 uppercase tracking-widest">{mcp.role}</span>
                  </div>
                  <p className="text-xs text-ripple-subtle leading-relaxed">{mcp.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* How it works steps */}
          <div className="flex flex-col gap-3">
            <h3 className="font-mono text-[11px] text-ripple-subtle uppercase tracking-widest">How it works</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { n: '01', title: 'PR Opens', body: 'Developer pushes a change. GitLab fires a webhook to Ripple with the diff.' },
                { n: '02', title: 'Intelligence', body: 'Dynatrace MCP is queried for incidents matching the pattern. Gemini extracts the semantic risk and scores it 1–10.' },
                { n: '03', title: 'Sweep', body: '12 scanner agents fan out across all services in parallel. Each agent hunts for the pattern in its assigned service.' },
                { n: '04', title: 'Fix Factory', body: 'For each hit, a fix agent generates a targeted patch informed by the real Dynatrace traces from the incident.' },
                { n: '05', title: 'Self-Correction', body: 'An evaluation agent checks whether the fix would have prevented the incident. If it fails, the fix agent iterates (up to 3×).' },
                { n: '06', title: 'MRs Open', body: 'On pass: a fix MR opens in GitLab with the incident context embedded. MongoDB stores the outcome for future scans.' },
              ].map(({ n, title, body }) => (
                <div key={n} className="rounded-lg border border-white/5 bg-ripple-surface p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-ripple-accent">{n}</span>
                    <span className="font-mono text-sm font-bold text-ripple-text">{title}</span>
                  </div>
                  <p className="text-xs text-ripple-subtle leading-relaxed">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Competitors ── */}
        <section id="competitors" className="flex flex-col gap-10">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-bold text-ripple-text">Competitor Analysis</h2>
            <p className="text-sm text-ripple-subtle max-w-2xl">
              Ripple sits at the intersection of AI code review, agent memory, and production observability. No existing tool occupies all three simultaneously.
            </p>
          </div>

          {/* TL;DR — for judges scanning fast */}
          <div className="rounded-lg border border-ripple-accent/20 bg-ripple-accent/5 p-5 flex flex-col gap-3">
            <span className="font-mono text-[10px] text-ripple-accent uppercase tracking-widest">TL;DR</span>
            <p className="text-sm text-ripple-text leading-relaxed">
              Every competitor in this space lacks two things simultaneously — <strong className="text-ripple-text">production observability data</strong> and <strong className="text-ripple-text">autonomous action</strong>. Ripple is the only system that has both. ARGUS reviews the PR in front of it. Ripple reviews the PR, queries Dynatrace for the incident that proves why it's dangerous, then sweeps every service and opens fix MRs — all without human input.
            </p>
          </div>

          {/* Narrative competitor cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              {
                name: 'ARGUS',
                url: 'argus.reviews',
                verdict: 'Best for deep single-PR review',
                rippleEdge: 'ARGUS knows what broke before (from git). Ripple knows what breaking cost (from Dynatrace) and fixes it across every service automatically.',
                theyWin: 'Your team wants thoughtful, multi-pass PR commentary with failure scenario simulation and reviewer-reaction learning. ARGUS is excellent at this.',
                weWin: 'You want a PR to trigger an autonomous sweep of your entire codebase and open targeted fix MRs grounded in a real production incident — not just a review comment.',
              },
              {
                name: 'GitMem',
                url: 'gitmem.ai',
                verdict: 'Best for developer AI memory',
                rippleEdge: 'GitMem is memory for the developer\'s AI assistant. Ripple is memory for the team\'s production system. Different layers, no direct overlap.',
                theyWin: 'A solo developer or small team wants their AI coding agent to remember past decisions, mistakes, and architectural choices across sessions.',
                weWin: 'A team wants their PR pipeline to automatically catch patterns that caused real production incidents and prevent them from spreading across services.',
              },
            ].map(({ name, url, verdict, rippleEdge, theyWin, weWin }) => (
              <div key={name} className="rounded-lg border border-white/5 bg-ripple-surface p-5 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm font-bold text-ripple-text">{name}</span>
                  <span className="font-mono text-[9px] text-ripple-subtle">{url}</span>
                </div>
                <div className="rounded border border-ripple-scan/20 bg-ripple-scan/5 px-3 py-2">
                  <span className="font-mono text-[10px] text-ripple-scan">{verdict}</span>
                </div>
                <p className="text-xs text-ripple-subtle leading-relaxed italic border-l-2 border-ripple-accent/30 pl-3">{rippleEdge}</p>
                <div className="flex flex-col gap-2">
                  <div className="flex flex-col gap-1">
                    <span className="font-mono text-[9px] text-ripple-subtle uppercase tracking-widest">Choose {name} if</span>
                    <p className="text-xs text-ripple-subtle leading-relaxed">{theyWin}</p>
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="font-mono text-[9px] text-ripple-accent uppercase tracking-widest">Choose Ripple if</span>
                    <p className="text-xs text-ripple-text/80 leading-relaxed">{weWin}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Primary competitor comparison */}
          <div className="flex flex-col gap-3">
            <h3 className="font-mono text-[11px] text-ripple-subtle uppercase tracking-widest">Feature matrix</h3>
            <div className="rounded-lg border border-white/5 overflow-hidden">
              <table className="w-full text-sm" role="table">
                <thead>
                  <tr className="border-b border-white/5 bg-ripple-surface">
                    <th className="text-left font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3 w-1/3">Feature</th>
                    <th className="text-left font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">ARGUS</th>
                    <th className="text-left font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">GitMem</th>
                    <th className="text-left font-mono text-[10px] text-ripple-accent uppercase tracking-widest px-4 py-3">Ripple</th>
                  </tr>
                </thead>
                <tbody>
                  {matrix.map(({ feature, argus, gitmem, ripple }, i) => (
                    <tr key={feature} className={`border-b border-white/5 ${i % 2 === 0 ? '' : 'bg-white/[0.015]'}`}>
                      <td className="px-4 py-3 text-xs text-ripple-text">{feature}</td>
                      <td className="px-4 py-3"><Cell val={argus} /></td>
                      <td className="px-4 py-3"><Cell val={gitmem} /></td>
                      <td className="px-4 py-3 bg-ripple-accent/[0.04]"><Cell val={ripple} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex items-center gap-4 text-[10px] font-mono text-ripple-subtle pt-1">
              <span className="flex items-center gap-1"><CHECK /><span>supported</span></span>
              <span className="flex items-center gap-1"><CROSS /><span>not supported</span></span>
              <span className="flex items-center gap-1"><PLAN /><span>planned</span></span>
              <span className="flex items-center gap-1"><CHECK /><UNIQUE /><span>unique to Ripple</span></span>
            </div>
          </div>

          {/* Secondary matrix */}
          <div className="flex flex-col gap-3">
            <h3 className="font-mono text-[11px] text-ripple-subtle uppercase tracking-widest">Broader Market</h3>
            <div className="rounded-lg border border-white/5 overflow-hidden">
              <table className="w-full text-sm" role="table">
                <thead>
                  <tr className="border-b border-white/5 bg-ripple-surface">
                    <th className="text-left font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">Tool</th>
                    <th className="text-left font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3 hidden sm:table-cell">Angle</th>
                    <th className="text-center font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">Memory</th>
                    <th className="text-center font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">Sweep</th>
                    <th className="text-center font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">Action</th>
                    <th className="text-center font-mono text-[10px] text-ripple-subtle uppercase tracking-widest px-4 py-3">Prod data</th>
                  </tr>
                </thead>
                <tbody>
                  {secondary.map(({ tool, angle, memory, sweep, action, prod }, i) => {
                    const isRipple = tool === 'Ripple'
                    return (
                      <tr
                        key={tool}
                        className={[
                          'border-b border-white/5',
                          i % 2 === 0 ? '' : 'bg-white/[0.015]',
                          isRipple ? 'bg-ripple-accent/[0.06] border-t border-ripple-accent/20' : '',
                        ].join(' ')}
                      >
                        <td className="px-4 py-3">
                          <span className={`font-mono text-xs font-bold ${isRipple ? 'text-ripple-accent' : 'text-ripple-text'}`}>{tool}</span>
                        </td>
                        <td className="px-4 py-3 text-xs text-ripple-subtle hidden sm:table-cell">{angle}</td>
                        <td className="px-4 py-3 text-center"><Cell val={memory as Cell} /></td>
                        <td className="px-4 py-3 text-center">
                          {typeof sweep === 'string' ? (
                            <span className="font-mono text-[10px] text-ripple-subtle">{sweep}</span>
                          ) : (
                            <Cell val={sweep as Cell} />
                          )}
                        </td>
                        <td className="px-4 py-3 text-center"><Cell val={action as Cell} /></td>
                        <td className="px-4 py-3 text-center"><Cell val={prod as Cell} /></td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Where Ripple wins */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="rounded-lg border border-ripple-clean/20 bg-ripple-clean/5 p-5 flex flex-col gap-3">
              <span className="font-mono text-[10px] text-ripple-clean uppercase tracking-widest">Where Ripple wins</span>
              <ul className="flex flex-col gap-2">
                {[
                  'Production-grounded data from real Dynatrace incidents',
                  'Codebase-wide autonomous sweep from a single PR',
                  'Autonomous fix MR creation across all affected services',
                  'Real failure replay — actual traces, not hypothetical simulation',
                  'Quantified impact: "47-minute outage, £23k"',
                  'Three MCPs: Dynatrace + GitLab + MongoDB',
                ].map(w => (
                  <li key={w} className="flex items-start gap-2 text-xs text-ripple-text/80 leading-relaxed">
                    <CHECK />
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-white/5 bg-ripple-surface p-5 flex flex-col gap-3">
              <span className="font-mono text-[10px] text-ripple-subtle uppercase tracking-widest">Where Ripple is weak (and why)</span>
              <ul className="flex flex-col gap-2">
                {[
                  'No reviewer reaction learning yet — addressed by MongoDB memory store',
                  'No self-learning over time yet — addressed by scar/win accumulation',
                  'No PR diagram generation yet — planned, will use real DT traces',
                  'No general code quality review — intentional scope, not a bug',
                  'GitHub support not yet available — GitLab only today',
                ].map(w => (
                  <li key={w} className="flex items-start gap-2 text-xs text-ripple-subtle leading-relaxed">
                    <PLAN />
                    <span>{w}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-white/5 mt-8">
        <div className="max-w-7xl mx-auto px-6 py-6 flex items-center justify-between">
          <p className="font-mono text-[10px] text-ripple-subtle">Ripple · Incident-grounded code review · ripple.dev</p>
          <Link href="/" className="font-mono text-[10px] text-ripple-accent hover:underline">← Back to Live Dashboard</Link>
        </div>
      </footer>
    </div>
  )
}
