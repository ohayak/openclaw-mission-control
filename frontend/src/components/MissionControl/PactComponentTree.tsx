import { Badge } from "@/components/ui/badge"
import type { PactComponent } from "@/hooks/useMissionControl"
import { CheckCircle2, Circle } from "lucide-react"

interface PactComponentTreeProps {
  components: PactComponent[]
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

export function PactComponentTree({ components }: PactComponentTreeProps) {
  if (components.length === 0) {
    return (
      <div className="text-sm text-muted-foreground text-center py-8">
        No components yet — PACT has not decomposed this project.
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-2 text-xs text-muted-foreground font-medium px-3 pb-1 border-b">
        <span>Component</span>
        <span className="text-center">Contract</span>
        <span className="text-center">Tests</span>
        <span className="text-center">Impl</span>
      </div>
      {components.map((comp) => (
        <div
          key={comp.id}
          className="grid grid-cols-[1fr_auto_auto_auto] gap-2 items-start p-3 rounded-lg border border-border hover:border-primary/30 transition-colors"
        >
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
      ))}
    </div>
  )
}
