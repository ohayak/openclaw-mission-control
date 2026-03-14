import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { ComponentDetail } from "@/components/MissionControl/ComponentDetail"
import type { PactComponent } from "@/hooks/useMissionControl"
import { CheckCircle2, ChevronDown, ChevronRight, Circle } from "lucide-react"

interface PactComponentTreeProps {
  components: PactComponent[]
  /** When provided, components are clickable and show drill-down detail panel */
  projectId?: string
}

function TestStatus({ passed, failed, total }: { passed?: number; failed?: number; total?: number }) {
  if (total === undefined) return null
  const allPass = failed === 0 && (passed ?? 0) > 0
  return (
    <span className={`text-xs ${allPass ? "text-green-400" : "text-red-400"}`}>
      {passed}/{total}
    </span>
  )
}

function StatusIcon({ has }: { has: boolean }) {
  return has ? (
    <CheckCircle2 size={14} className="text-green-500 flex-shrink-0" />
  ) : (
    <Circle size={14} className="text-muted-foreground flex-shrink-0" />
  )
}

interface ComponentRowProps {
  comp: PactComponent
  projectId?: string
  expanded: boolean
  onToggle: () => void
}

function ComponentRow({ comp, projectId, expanded, onToggle }: ComponentRowProps) {
  const isClickable = !!projectId

  return (
    <div>
      <div
        className={`grid gap-2 items-start p-3 rounded-lg border border-border transition-colors
          ${isClickable ? "cursor-pointer hover:border-primary/40 hover:bg-muted/20" : ""}
          ${expanded ? "border-primary/40 bg-muted/10" : ""}
        `}
        style={{ gridTemplateColumns: isClickable ? "auto 1fr auto auto auto" : "1fr auto auto auto" }}
        onClick={isClickable ? onToggle : undefined}
        role={isClickable ? "button" : undefined}
        tabIndex={isClickable ? 0 : undefined}
        onKeyDown={isClickable ? (e) => e.key === "Enter" && onToggle() : undefined}
        aria-expanded={isClickable ? expanded : undefined}
        aria-label={isClickable ? `${comp.name} — click to ${expanded ? "collapse" : "expand"} details` : undefined}
      >
        {/* Expand chevron (only when projectId provided) */}
        {isClickable && (
          <div className="flex items-center pt-0.5">
            {expanded ? (
              <ChevronDown size={14} className="text-muted-foreground" />
            ) : (
              <ChevronRight size={14} className="text-muted-foreground" />
            )}
          </div>
        )}

        {/* Component name + metadata */}
        <div>
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium">{comp.name}</p>
            {comp.layer && (
              <Badge variant="outline" className="text-xs px-1.5 py-0">
                {comp.layer}
              </Badge>
            )}
          </div>
          {comp.description && (
            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">{comp.description}</p>
          )}
          {comp.dependencies.length > 0 && (
            <p className="text-xs text-muted-foreground mt-0.5">
              deps: {comp.dependencies.join(", ")}
            </p>
          )}
        </div>

        {/* Status icons */}
        <div className="flex justify-center pt-0.5">
          <StatusIcon has={comp.has_contract} />
        </div>
        <div className="flex flex-col items-center pt-0.5 gap-0.5">
          <StatusIcon has={comp.has_tests} />
          {comp.test_total !== undefined && (
            <TestStatus passed={comp.test_passed} failed={comp.test_failed} total={comp.test_total} />
          )}
        </div>
        <div className="flex justify-center pt-0.5">
          <StatusIcon has={comp.has_implementation} />
        </div>
      </div>

      {/* Expandable detail panel — keyed by component id for stable state */}
      {isClickable && projectId && (
        <div className={`px-3 ${expanded ? "pb-3" : ""}`}>
          <ComponentDetail
            projectId={projectId}
            componentId={comp.id}
            expanded={expanded}
          />
        </div>
      )}
    </div>
  )
}

export function PactComponentTree({ components, projectId }: PactComponentTreeProps) {
  // Track expanded state by component id (stable across pipeline refreshes)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set())

  function toggleComponent(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  if (components.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No components yet — PACT has not decomposed this project.
      </div>
    )
  }

  const isClickable = !!projectId

  return (
    <div className="space-y-2">
      <div
        className="text-xs text-muted-foreground font-medium px-3 pb-1 border-b"
        style={{
          display: "grid",
          gridTemplateColumns: isClickable ? "auto 1fr auto auto auto" : "1fr auto auto auto",
          gap: "0.5rem",
        }}
      >
        {isClickable && <span />}
        <span>Component</span>
        <span className="text-center">Contract</span>
        <span className="text-center">Tests</span>
        <span className="text-center">Impl</span>
      </div>
      {components.map((comp) => (
        <ComponentRow
          key={comp.id}
          comp={comp}
          projectId={projectId}
          expanded={expandedIds.has(comp.id)}
          onToggle={() => toggleComponent(comp.id)}
        />
      ))}
    </div>
  )
}
