import { useState } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useProjects, useCreateProject, useDeleteProject, type ProjectCreate } from "@/hooks/useMissionControl"
import { Plus, Trash2, FolderOpen } from "lucide-react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

export const Route = createFileRoute("/_layout/projects/")({
  component: ProjectsPage,
  head: () => ({ meta: [{ title: "Projects — Mission Control" }] }),
})

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500 text-white",
  paused: "bg-yellow-500 text-white",
  completed: "bg-blue-500 text-white",
  archived: "bg-slate-500 text-white",
}

function CreateProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { mutateAsync, isPending } = useCreateProject()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<ProjectCreate>()

  async function onSubmit(data: ProjectCreate) {
    try {
      await mutateAsync(data)
      toast.success("Project created")
      reset()
      onClose()
    } catch (e) {
      toast.error("Failed to create project")
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="text-sm font-medium">Name *</label>
            <Input
              {...register("name", { required: "Name is required" })}
              placeholder="My awesome project"
              className="mt-1"
            />
            {errors.name && <p className="text-xs text-destructive mt-1">{errors.name.message}</p>}
          </div>
          <div>
            <label className="text-sm font-medium">Description</label>
            <Input
              {...register("description")}
              placeholder="What is this project about?"
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium">PACT Directory (optional)</label>
            <Input
              {...register("pact_dir")}
              placeholder="/data/.openclaw/workspace/my-project"
              className="mt-1 font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Absolute path to the PACT project directory on the host
            </p>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? "Creating..." : "Create Project"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function ProjectsPage() {
  const { data: projects = [], isLoading } = useProjects()
  const { mutateAsync: deleteProject } = useDeleteProject()
  const [createOpen, setCreateOpen] = useState(false)
  const [search, setSearch] = useState("")

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase())
  )

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete "${name}"? This will also delete all tasks.`)) return
    try {
      await deleteProject(id)
      toast.success("Project deleted")
    } catch {
      toast.error("Failed to delete project")
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Projects</h1>
          <p className="text-muted-foreground mt-1">{projects.length} projects</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus size={14} className="mr-1" /> New Project
        </Button>
      </div>

      <div>
        <Input
          placeholder="Search projects..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>

      {isLoading ? (
        <div className="grid gap-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16">
          <FolderOpen size={40} className="mx-auto text-muted-foreground mb-3" />
          <p className="text-muted-foreground">
            {search ? "No projects match your search." : "No projects yet."}
          </p>
          {!search && (
            <Button className="mt-4" onClick={() => setCreateOpen(true)}>
              <Plus size={14} className="mr-1" /> Create First Project
            </Button>
          )}
        </div>
      ) : (
        <div className="grid gap-3">
          {filtered.map((project) => (
            <Card key={project.id} className="hover:border-primary/40 transition-colors group">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <Link
                    to="/projects/$projectId"
                    params={{ projectId: project.id }}
                    className="flex-1 min-w-0"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-semibold">{project.name}</p>
                          <Badge
                            variant="secondary"
                            className={`text-xs ${STATUS_COLORS[project.status] || ""}`}
                          >
                            {project.status}
                          </Badge>
                          {project.pact_dir && (
                            <Badge variant="outline" className="text-xs">PACT</Badge>
                          )}
                        </div>
                        {project.description && (
                          <p className="text-sm text-muted-foreground truncate">{project.description}</p>
                        )}
                        <p className="text-xs text-muted-foreground mt-0.5">
                          Updated {new Date(project.updated_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                  </Link>
                  <button
                    onClick={(e) => { e.preventDefault(); handleDelete(project.id, project.name) }}
                    className="opacity-0 group-hover:opacity-100 transition-opacity p-2 text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CreateProjectDialog open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
