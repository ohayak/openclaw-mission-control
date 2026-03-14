/**
 * PactPhaseActions — per-phase action buttons shown below each pipeline stage.
 *
 * Phase-specific actions:
 *   interview:  [Start Interview]
 *   shape/decompose/contract/test/implement/integrate/polish: [Run Phase]
 *
 * Disabled when PACT is running. Shows spinner when mutation is pending.
 */
import { Button } from "@/components/ui/button"
import {
  usePactInit,
  usePactInterviewStart,
  usePactRun,
  type PactStatus,
} from "@/hooks/useMissionControl"
import { Loader2, Play, Zap } from "lucide-react"
import { toast } from "sonner"

interface PactPhaseActionsProps {
  projectId: string
  pactStatus: PactStatus
  /** The pipeline phase this action group belongs to */
  phase: string
}

export function PactPhaseActions({ projectId, pactStatus, phase }: PactPhaseActionsProps) {
  const isRunning = pactStatus.status === "running"
  const initMutation = usePactInit(projectId)
  const interviewMutation = usePactInterviewStart(projectId)
  const runMutation = usePactRun(projectId)

  const anyPending =
    initMutation.isPending || interviewMutation.isPending || runMutation.isPending

  async function handleInit() {
    try {
      await initMutation.mutateAsync()
      toast.success("PACT initialization started")
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "Failed to initialize PACT"
      if (err?.response?.status === 409) {
        toast.error("PACT is already running")
      } else if (err?.response?.status === 503) {
        toast.error("pact CLI not installed on the server")
      } else {
        toast.error(detail)
      }
    }
  }

  async function handleInterviewStart() {
    try {
      await interviewMutation.mutateAsync()
      toast.success("Interview started — check the Logs tab for output")
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("PACT is already running")
      } else if (err?.response?.status === 503) {
        toast.error("pact CLI not installed on the server")
      } else {
        toast.error(err?.response?.data?.detail || "Failed to start interview")
      }
    }
  }

  async function handleRunPhase(targetPhase?: string) {
    try {
      await runMutation.mutateAsync(targetPhase)
      toast.success(targetPhase ? `Running phase: ${targetPhase}` : "PACT run started — check the Logs tab")
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("PACT is already running")
      } else if (err?.response?.status === 503) {
        toast.error("pact CLI not installed on the server")
      } else {
        toast.error(err?.response?.data?.detail || "Failed to run phase")
      }
    }
  }

  const disabled = isRunning || anyPending

  if (phase === "interview") {
    return (
      <div className="flex gap-2 mt-2">
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          onClick={handleInit}
        >
          {initMutation.isPending ? (
            <Loader2 size={12} className="mr-1 animate-spin" />
          ) : (
            <Zap size={12} className="mr-1" />
          )}
          Init PACT
        </Button>
        <Button
          size="sm"
          disabled={disabled}
          onClick={handleInterviewStart}
        >
          {interviewMutation.isPending ? (
            <Loader2 size={12} className="mr-1 animate-spin" />
          ) : (
            <Play size={12} className="mr-1" />
          )}
          Start Interview
        </Button>
      </div>
    )
  }

  if (phase === "complete") {
    // No actions for complete phase
    return null
  }

  // All other phases: shape, decompose, contract, test, implement, integrate, polish
  return (
    <div className="flex gap-2 mt-2">
      <Button
        size="sm"
        disabled={disabled}
        onClick={() => handleRunPhase(phase)}
      >
        {runMutation.isPending ? (
          <Loader2 size={12} className="mr-1 animate-spin" />
        ) : (
          <Play size={12} className="mr-1" />
        )}
        Run {phase.charAt(0).toUpperCase() + phase.slice(1)}
      </Button>
    </div>
  )
}
