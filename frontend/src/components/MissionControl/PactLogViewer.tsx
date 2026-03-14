/**
 * PactLogViewer — terminal-style SSE log viewer for PACT execution output.
 *
 * Features:
 * - Connects to the SSE stream when `streaming` prop is true
 * - Auto-scrolls to bottom on new lines
 * - Shows "Process complete" badge when done event received
 * - Shows error toast + banner on stream error
 * - "Clear" button resets lines
 * - Monospace font, dark background
 */
import { useEffect, useRef } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { usePactStream } from "@/hooks/useMissionControl"
import { CheckCircle2, Loader2, Trash2 } from "lucide-react"
import { toast } from "sonner"

interface PactLogViewerProps {
  projectId: string
  /** Whether to open the SSE stream (typically true when user opens Logs tab) */
  streaming: boolean
}

export function PactLogViewer({ projectId, streaming }: PactLogViewerProps) {
  const { lines, done, error, reset } = usePactStream(projectId, streaming)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom whenever new lines arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [lines])

  // Show toast when error event received from stream
  useEffect(() => {
    if (error) {
      toast.error(error)
    }
  }, [error])

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Live Logs</span>
          {streaming && !done && !error && (
            <Badge variant="secondary" className="bg-blue-500/20 text-blue-400 border-blue-500/30">
              <Loader2 size={10} className="mr-1 animate-spin" />
              Streaming
            </Badge>
          )}
          {done && (
            <Badge variant="secondary" className="bg-green-500/20 text-green-400 border-green-500/30">
              <CheckCircle2 size={10} className="mr-1" />
              Complete
            </Badge>
          )}
          {error && (
            <Badge variant="destructive" className="text-xs">
              Error
            </Badge>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={reset}
          disabled={lines.length === 0}
          className="h-7 px-2 text-muted-foreground"
        >
          <Trash2 size={12} className="mr-1" />
          Clear
        </Button>
      </div>

      {/* Terminal-style log display */}
      <div
        className="h-96 overflow-y-auto rounded-md border bg-black/90 p-3 font-mono text-xs leading-relaxed"
        role="log"
        aria-live="polite"
        aria-label="PACT execution log output"
      >
        {lines.length === 0 && !error ? (
          <span className="text-muted-foreground">
            {streaming
              ? "Waiting for output..."
              : "No log output yet. Start a PACT action to see live output here."}
          </span>
        ) : (
          <>
            {lines.map((line, idx) => (
              <div key={idx} className="text-green-300 whitespace-pre-wrap break-all">
                {line}
              </div>
            ))}
            {error && (
              <div className="text-red-400 mt-2 border-t border-red-500/30 pt-2">
                ⚠ Stream error: {error}
              </div>
            )}
            {done && (
              <div className="text-blue-400 mt-2 border-t border-blue-500/30 pt-2">
                ✓ Process complete
              </div>
            )}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {!streaming && (
        <p className="text-xs text-muted-foreground">
          Open this tab while a PACT action is running to see live output.
        </p>
      )}
    </div>
  )
}
