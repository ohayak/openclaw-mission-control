/**
 * ComponentDetail — expandable panel showing contract + test details for a component.
 *
 * Features:
 * - Contract content in a scrollable, syntax-highlighted code block
 * - Test files listed with content
 * - [Re-test] button that fires the retest endpoint
 * - "No contract yet" placeholder when contract doesn't exist
 * - Expanded state keyed by component_id (stable across pipeline refreshes)
 */
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  usePactComponentContract,
  usePactComponentTests,
  usePactComponentRetest,
} from "@/hooks/useMissionControl"
import { FileText, Loader2, RefreshCw } from "lucide-react"
import { toast } from "sonner"

interface ComponentDetailProps {
  projectId: string
  componentId: string
  /** Whether the detail panel is currently expanded/visible */
  expanded: boolean
}

export function ComponentDetail({ projectId, componentId, expanded }: ComponentDetailProps) {
  const { data: contract, isLoading: contractLoading } = usePactComponentContract(
    projectId,
    componentId,
    expanded,
  )
  const { data: tests, isLoading: testsLoading } = usePactComponentTests(
    projectId,
    componentId,
    expanded,
  )
  const retestMutation = usePactComponentRetest(projectId)

  async function handleRetest() {
    try {
      await retestMutation.mutateAsync(componentId)
      toast.success(`Re-testing ${componentId} — check the Logs tab for output`)
    } catch (err: any) {
      if (err?.response?.status === 409) {
        toast.error("PACT is already running")
      } else if (err?.response?.status === 503) {
        toast.error("pact CLI not installed on the server")
      } else {
        toast.error(err?.response?.data?.detail || "Failed to start retest")
      }
    }
  }

  if (!expanded) return null

  return (
    <div className="mt-3 border-t border-border pt-3 space-y-4">
      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={handleRetest}
          disabled={retestMutation.isPending}
        >
          {retestMutation.isPending ? (
            <Loader2 size={12} className="mr-1 animate-spin" />
          ) : (
            <RefreshCw size={12} className="mr-1" />
          )}
          Re-test
        </Button>
      </div>

      {/* Contract section */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <FileText size={14} className="text-muted-foreground" />
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Contract
          </span>
          {contract && (
            <Badge variant="outline" className="text-xs px-1.5 py-0">
              {contract.filename}
            </Badge>
          )}
        </div>
        {contractLoading ? (
          <div className="h-20 rounded bg-muted animate-pulse" />
        ) : contract ? (
          <div className="rounded border bg-black/80 overflow-auto max-h-64">
            <pre className="p-3 text-xs font-mono text-green-300 whitespace-pre-wrap break-all">
              {contract.content}
            </pre>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic py-2">
            No contract yet — run the contract phase to generate it.
          </p>
        )}
      </div>

      {/* Tests section */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <FileText size={14} className="text-muted-foreground" />
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Tests
          </span>
          {tests && tests.files.length > 0 && (
            <Badge variant="outline" className="text-xs px-1.5 py-0">
              {tests.files.length} file{tests.files.length !== 1 ? "s" : ""}
            </Badge>
          )}
        </div>
        {testsLoading ? (
          <div className="h-20 rounded bg-muted animate-pulse" />
        ) : tests && tests.files.length > 0 ? (
          <div className="space-y-3">
            {tests.files.map((file) => (
              <div key={file.filename}>
                <div className="flex items-center gap-1.5 mb-1">
                  <FileText size={12} className="text-muted-foreground" />
                  <span className="text-xs font-mono text-muted-foreground">{file.filename}</span>
                </div>
                <div className="rounded border bg-black/80 overflow-auto max-h-48">
                  <pre className="p-3 text-xs font-mono text-green-300 whitespace-pre-wrap break-all">
                    {file.content}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground italic py-2">
            No tests yet — run the test phase to generate them.
          </p>
        )}
      </div>
    </div>
  )
}
