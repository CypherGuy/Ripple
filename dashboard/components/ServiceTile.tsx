"use client";
import type { ServiceState } from "../hooks/useRippleSocket";

interface Props {
  name: string;
  state: ServiceState;
  onApprove?: (service: string) => void;
  onSkip?: (service: string) => void;
}

const STATUS_CONFIG = {
  idle: {
    border: "border-white/5",
    bg: "bg-ripple-card",
    dot: "bg-ripple-subtle",
    label: "IDLE",
    labelColor: "text-ripple-subtle",
    glow: "",
  },
  scanning: {
    border: "border-ripple-scan/40",
    bg: "bg-ripple-card",
    dot: "bg-ripple-scan",
    label: "SCANNING",
    labelColor: "text-ripple-scan",
    glow: "shadow-[0_0_16px_rgba(245,158,11,0.2)]",
  },
  hit: {
    border: "border-ripple-hit/60",
    bg: "bg-ripple-card",
    dot: "bg-ripple-hit",
    label: "HIT",
    labelColor: "text-ripple-hit",
    glow: "shadow-[0_0_20px_rgba(239,68,68,0.35)] animate-hit-pulse",
  },
  clean: {
    border: "border-ripple-clean/30",
    bg: "bg-ripple-card",
    dot: "bg-ripple-clean",
    label: "CLEAN",
    labelColor: "text-ripple-clean",
    glow: "shadow-[0_0_12px_rgba(34,197,94,0.2)]",
  },
  requires_approval: {
    border: "border-ripple-accent/60",
    bg: "bg-ripple-card",
    dot: "bg-ripple-accent",
    label: "APPROVAL",
    labelColor: "text-ripple-accent",
    glow: "shadow-[0_0_16px_rgba(99,102,241,0.3)]",
  },
  skipped: {
    border: "border-white/10",
    bg: "bg-ripple-card/60",
    dot: "bg-ripple-subtle",
    label: "SKIPPED",
    labelColor: "text-ripple-subtle",
    glow: "",
  },
  approving: {
    border: "border-ripple-accent/40",
    bg: "bg-ripple-card",
    dot: "bg-ripple-accent animate-pulse",
    label: "FIXING...",
    labelColor: "text-ripple-accent",
    glow: "shadow-[0_0_16px_rgba(99,102,241,0.2)]",
  },
} as const;

export default function ServiceTile({ name, state, onApprove, onSkip }: Props) {
  const cfg = STATUS_CONFIG[state.status];

  return (
    <div
      className={[
        "relative flex flex-col justify-between rounded-lg border p-3 transition-all duration-300",
        cfg.bg,
        cfg.border,
        cfg.glow,
        "min-h-[100px]",
      ].join(" ")}
      aria-label={`${name}: ${state.status}`}
      title={
        state.status === "hit" && state.incidentId
          ? `Pattern found - same as ${state.incidentId}${state.fileHit ? ` in ${state.fileHit}` : ""}. Confidence: ${state.confidence ? `${Math.round(state.confidence * 100)}%` : "high"}.`
          : undefined
      }
    >
      {/* Scanning ring */}
      {state.status === "scanning" && (
        <span className="absolute inset-0 rounded-lg border border-ripple-scan/50 animate-scan-ring" />
      )}

      {/* Header row */}
      <div className="flex items-center justify-between gap-2">
        <span
          className={[
            "w-1.5 h-1.5 rounded-full shrink-0 transition-colors duration-300",
            cfg.dot,
          ].join(" ")}
          aria-hidden="true"
        />
        <span
          className={[
            "font-mono text-[9px] font-semibold tracking-widest uppercase",
            cfg.labelColor,
          ].join(" ")}
        >
          {cfg.label}
        </span>
      </div>

      {/* Service name */}
      <p className="font-mono text-[11px] text-ripple-text/80 mt-2 truncate leading-tight">
        {name}
      </p>

      {/* Footer */}
      <div className="mt-2">
        {state.status === "hit" &&
          state.mrUrl &&
          state.mrUrl.startsWith("https://gitlab.com/") && (
            <div className="flex flex-col gap-1">
              <a
                href={state.mrUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={[
                  "inline-flex items-center gap-1 font-mono text-[9px] font-semibold tracking-wider uppercase",
                  "text-ripple-hit border border-ripple-hit/40 rounded px-2 py-0.5",
                  "hover:bg-ripple-hit/10 hover:border-ripple-hit/70 transition-all duration-150",
                  "cursor-pointer focus:outline-none focus:ring-1 focus:ring-ripple-hit/50",
                ].join(" ")}
              >
                View MR
                <svg
                  className="w-2.5 h-2.5"
                  viewBox="0 0 12 12"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M2.5 9.5L9.5 2.5M9.5 2.5H4.5M9.5 2.5V7.5"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </a>
              {state.evaluatedOn === "incident_context" && state.incidentId && (
                <span
                  className="font-mono text-[8px] text-ripple-hit/90 uppercase tracking-wider border border-ripple-hit/25 rounded px-1 py-px"
                  title="Fix was generated and evaluated against this Dynatrace incident"
                >
                  DT: {state.incidentId}
                </span>
              )}
              {state.correctionIterations !== null && (
                <span className="font-mono text-[8px] text-ripple-subtle/60 uppercase tracking-wider">
                  eval {state.correctionIterations}/3
                </span>
              )}
              {state.feedbackOutcome === "merged" && (
                <span className="font-mono text-[8px] text-ripple-clean uppercase tracking-wider">
                  ✓ Merged in GitLab
                </span>
              )}
              {state.feedbackOutcome === "closed" && (
                <span className="font-mono text-[8px] text-ripple-subtle uppercase tracking-wider">
                  ✗ Closed in GitLab
                </span>
              )}
            </div>
          )}
        {state.status === "hit" && !state.mrUrl && (
          <span className="font-mono text-[9px] text-ripple-hit/60 uppercase tracking-wider">
            {state.fileHit ? state.fileHit.split("/").pop() : "Pattern found"}
          </span>
        )}
        {state.status === "scanning" && (
          <span className="font-mono text-[9px] text-ripple-scan/60 uppercase tracking-wider">
            Searching...
          </span>
        )}
        {state.status === "clean" && (
          <span className="font-mono text-[9px] text-ripple-clean/70 uppercase tracking-wider">
            No match
          </span>
        )}
        {state.status === "idle" && (
          <span className="font-mono text-[9px] text-ripple-subtle/50 uppercase tracking-wider">
            Standby
          </span>
        )}
        {state.status === "requires_approval" && (
          <div className="flex flex-col gap-1 mt-1">
            {state.fileHit && (
              <span className="font-mono text-[8px] text-ripple-subtle/70 uppercase tracking-wider truncate">
                {state.fileHit.split("/").pop()}
                {state.confidence !== null &&
                  ` · ${Math.round(state.confidence * 100)}%`}
              </span>
            )}
            {state.riskScore !== null && (
              <span className="font-mono text-[8px] text-ripple-accent/70 uppercase tracking-wider">
                risk {state.riskScore}/10 - below auto-fix threshold
              </span>
            )}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => onApprove?.(name)}
                className={[
                  "font-mono text-[8px] uppercase tracking-wider px-2 py-0.5 rounded border transition-all",
                  "border-ripple-accent/60 text-ripple-accent hover:bg-ripple-accent/15 hover:border-ripple-accent",
                  "cursor-pointer focus:outline-none focus:ring-1 focus:ring-ripple-accent/40",
                ].join(" ")}
                aria-label={`Approve fix for ${name}`}
              >
                Approve fix
              </button>
              <button
                onClick={() => onSkip?.(name)}
                className={[
                  "font-mono text-[8px] uppercase tracking-wider px-2 py-0.5 rounded border transition-all",
                  "border-white/10 text-ripple-subtle hover:border-white/20 hover:text-ripple-text",
                  "cursor-pointer focus:outline-none focus:ring-1 focus:ring-white/20",
                ].join(" ")}
                aria-label={`Skip fix for ${name}`}
              >
                Skip
              </button>
            </div>
          </div>
        )}
        {state.status === "approving" && (
          <div className="flex flex-col gap-1 mt-1">
            {state.fileHit && (
              <span className="font-mono text-[8px] text-ripple-subtle/70 uppercase tracking-wider truncate">
                {state.fileHit.split("/").pop()}
                {state.confidence !== null &&
                  ` · ${Math.round(state.confidence * 100)}%`}
              </span>
            )}
            {state.riskScore !== null && (
              <span className="font-mono text-[8px] text-ripple-accent/60 uppercase tracking-wider">
                risk {state.riskScore}/10
              </span>
            )}
            <span className="font-mono text-[8px] text-ripple-accent/70 uppercase tracking-wider animate-pulse">
              Generating fix...
            </span>
          </div>
        )}
        {state.status === "skipped" && (
          <div className="flex flex-col gap-1 mt-1 opacity-70">
            {state.fileHit && (
              <span className="font-mono text-[8px] text-ripple-subtle/70 uppercase tracking-wider truncate line-through">
                {state.fileHit.split("/").pop()}
                {state.confidence !== null &&
                  ` · ${Math.round(state.confidence * 100)}%`}
              </span>
            )}
            {state.riskScore !== null && (
              <span className="font-mono text-[8px] text-ripple-subtle/70 uppercase tracking-wider">
                risk {state.riskScore}/10
              </span>
            )}
            <span className="font-mono text-[8px] text-ripple-subtle uppercase tracking-wider">
              Scar recorded - won&apos;t auto-fix next run
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
