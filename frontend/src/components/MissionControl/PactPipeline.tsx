import { Badge } from "@/components/ui/badge"
import type { PactStatus } from "@/hooks/useMissionControl"
import { CheckCircle2, Circle, Loader2 } from "lucide-react"

const STAGES = [
  "interview",
  "shape",
  "decompose",
  "contract",
  "test",
  "implement",
  "integrate",
  "polish",
  "complete",
]

const STAGE_LABELS: Record<string, string> = {
  interview: "Interview",
  shape: "Shape",
  decompose: "Decompose",
  contract: "Contract",
  test: "Test",
  implement: "Implement",
  integrate: "Integrate",
  polish: "Polish",
  complete: "Complete",
}

function stageIndex(phase: string): number {
  return STAGES.indexOf(phase.toLowerCase())
}

interface PactPipelineProps {
  status: PactStatus
}

export function PactPipeline({ status }: PactPipelineProps) {
  const currentIdx = stageIndex(status.phase)
  const isRunning = status.status === "running"

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={isRunning ? "default" : "secondary"} className={isRunning ? "bg-blue-500" : ""}>
            {isRunning ? "Running" : status.status}
          </Badge>
          <span className="text-sm text-muted-foreground capitalize">{status.phase}</span>
        </div>
        {status.component_count > 0 && (
          <div className="text-xs text-muted-foreground">
            {status.components_implemented}/{status.component_count} implemented
          </div>
        )}
      </div>

      {/* Pipeline stages */}
      <div className="flex items-center gap-0 overflow-x-auto pb-2">
        {STAGES.map((stage, idx) => {
          const isComplete = idx < currentIdx
          const isCurrent = idx === currentIdx

          return (
            <div key={stage} className="flex items-center">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`flex items-center justify-center w-8 h-8 rounded-full border-2 transition-all ${
                    isComplete
                      ? "border-green-500 bg-green-500/20 text-green-500"
                      : isCurrent
                        ? isRunning
                          ? "border-blue-500 bg-blue-500/20 text-blue-500"
                          : "border-primary bg-primary/20 text-primary"
                        : "border-muted bg-muted/20 text-muted-foreground"
                  }`}
                >
                  {isComplete ? (
                    <CheckCircle2 size={16} />
                  ) : isCurrent && isRunning ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <Circle size={14} />
                  )}
                </div>
                <span
                  className={`text-[10px] whitespace-nowrap ${
                    isCurrent ? "text-foreground font-medium" : "text-muted-foreground"
                  }`}
                >
                  {STAGE_LABELS[stage]}
                </span>
              </div>
              {idx < STAGES.length - 1 && (
                <div
                  className={`h-0.5 w-6 mt-[-10px] ${idx < currentIdx ? "bg-green-500/50" : "bg-muted"}`}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Stats row */}
      {status.component_count > 0 && (
        <div className="grid grid-cols-4 gap-2 text-center text-xs">
          <div className="rounded border p-2">
            <p className="font-semibold">{status.component_count}</p>
            <p className="text-muted-foreground">Components</p>
          </div>
          <div className="rounded border p-2">
            <p className="font-semibold text-blue-400">{status.components_contracted}</p>
            <p className="text-muted-foreground">Contracted</p>
          </div>
          <div className="rounded border p-2">
            <p className="font-semibold text-yellow-400">{status.components_tested}</p>
            <p className="text-muted-foreground">Tested</p>
          </div>
          <div className="rounded border p-2">
            <p className="font-semibold text-green-400">{status.components_implemented}</p>
            <p className="text-muted-foreground">Done</p>
          </div>
        </div>
      )}
    </div>
  )
}
