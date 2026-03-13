import { useState } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MemoryEditor } from "@/components/MissionControl/MemoryEditor"
import { useProject, useMemoryFiles, useUpdateMemoryFile, type MemoryFile } from "@/hooks/useMissionControl"
import { ArrowLeft } from "lucide-react"
import { toast } from "sonner"

export const Route = createFileRoute("/_layout/projects/$projectId/memory")({
  component: ProjectMemoryPage,
  head: () => ({ meta: [{ title: "Project Memory — Mission Control" }] }),
})

const MEMORY_FILES = [
  { filename: "CONTEXT.md", description: "High-level project context" },
  { filename: "decisions.md", description: "Architectural decisions" },
  { filename: "patterns.md", description: "Code patterns & conventions" },
  { filename: "gotchas.md", description: "Known issues & workarounds" },
  { filename: "glossary.md", description: "Project-specific terminology" },
]

function ProjectMemoryPage() {
  const { projectId } = Route.useParams()
  const { data: project } = useProject(projectId)
  const { data: files = [], isLoading } = useMemoryFiles(projectId)
  const { mutateAsync: updateFile, isPending: saving } = useUpdateMemoryFile(projectId)
  const [activeFile, setActiveFile] = useState("CONTEXT.md")

  // Merge actual files with defaults (show all tabs even if file doesn't exist)
  const fileMap = new Map(files.map((f) => [f.filename, f]))

  const getFile = (filename: string): MemoryFile =>
    fileMap.get(filename) || {
      path: filename,
      filename,
      content: "",
      last_modified: undefined,
    }

  async function handleSave(filename: string, content: string) {
    try {
      await updateFile({ filename, content })
      toast.success(`${filename} saved`)
    } catch {
      toast.error(`Failed to save ${filename}`)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to="/projects/$projectId"
          params={{ projectId }}
          className="text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Project Memory</h1>
          {project && <p className="text-muted-foreground text-sm">{project.name}</p>}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Shared knowledge base for this project. Agents load{" "}
        <code className="bg-muted px-1 rounded text-xs">CONTEXT.md</code> before starting work.
      </p>

      {isLoading ? (
        <Skeleton className="h-96" />
      ) : (
        <Tabs value={activeFile} onValueChange={setActiveFile}>
          <TabsList className="flex-wrap h-auto gap-1">
            {MEMORY_FILES.map((mf) => {
              const exists = fileMap.has(mf.filename)
              return (
                <TabsTrigger key={mf.filename} value={mf.filename} className="text-xs">
                  {mf.filename}
                  {exists && <Badge variant="secondary" className="ml-1 text-[10px] px-1 py-0">✓</Badge>}
                </TabsTrigger>
              )
            })}
          </TabsList>

          {MEMORY_FILES.map((mf) => (
            <TabsContent key={mf.filename} value={mf.filename} className="mt-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {mf.description}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MemoryEditor
                    file={getFile(mf.filename)}
                    onSave={(content) => handleSave(mf.filename, content)}
                    isSaving={saving}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      )}

      <Card className="border-primary/20 bg-primary/5">
        <CardContent className="p-4">
          <p className="text-xs text-muted-foreground">
            <strong>Agent Loading Protocol:</strong> Agents can fetch compiled context via{" "}
            <code className="bg-muted px-1 rounded">GET /api/v1/memory/{projectId}/context</code>
            {" "}— returns all memory files merged into a single document sized for an 8K token context window.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
