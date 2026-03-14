import { useState } from "react"
import { createFileRoute, Link } from "@tanstack/react-router"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { KanbanBoard } from "@/components/MissionControl/KanbanBoard"
import { PactPipeline } from "@/components/MissionControl/PactPipeline"
import { PactComponentTree } from "@/components/MissionControl/PactComponentTree"
import { PactLogViewer } from "@/components/MissionControl/PactLogViewer"
import {
  useProject,
  useUpdateProject,
  useTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
  usePactStatus,
  usePactComponents,
  useAgents,
  type TaskCreate,
  type TaskStatus,
  type ProjectUpdate,
} from "@/hooks/useMissionControl"
import { ArrowLeft, Plus, Brain, Settings } from "lucide-react"
import { useForm } from "react-hook-form"
import { toast } from "sonner"

export const Route = createFileRoute("/_layout/projects/$projectId")({
  component: ProjectDetailPage,
  head: () => ({ meta: [{ title: "Project — Mission Control" }] }),
})

function AddTaskDialog({
  open,
  onClose,
  projectId,
  defaultStatus,
  agentIds,
}: {
  open: boolean
  onClose: () => void
  projectId: string
  defaultStatus: TaskStatus
  agentIds: string[]
}) {
  const { mutateAsync, isPending } = useCreateTask()
  const { register, handleSubmit, reset } = useForm<TaskCreate>({
    defaultValues: { project_id: projectId, status: defaultStatus, priority: "medium" },
  })

  async function onSubmit(data: TaskCreate) {
    try {
      await mutateAsync({ ...data, project_id: projectId })
      toast.success("Task created")
      reset()
      onClose()
    } catch {
      toast.error("Failed to create task")
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add Task</DialogTitle></DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="text-sm font-medium">Title *</label>
            <Input {...register("title", { required: true })} placeholder="Task title" className="mt-1" />
          </div>
          <div>
            <label className="text-sm font-medium">Description</label>
            <Input {...register("description")} placeholder="Optional description" className="mt-1" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">Status</label>
              <select
                {...register("status")}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="backlog">Backlog</option>
                <option value="in_progress">In Progress</option>
                <option value="review">Review</option>
                <option value="done">Done</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Priority</label>
              <select
                {...register("priority")}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Assign to Agent</label>
            <select
              {...register("assigned_agent_id")}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">Unassigned</option>
              {agentIds.map((id) => (
                <option key={id} value={id}>{id}</option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={isPending}>{isPending ? "Adding..." : "Add Task"}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// Config tab
// ---------------------------------------------------------------------------

interface ConfigFormData {
  pact_dir: string
  model_override: string
  auto_advance: boolean
}

function ConfigTab({ projectId }: { projectId: string }) {
  const { data: project } = useProject(projectId)
  const { mutateAsync: updateProject, isPending } = useUpdateProject()
  const { register, handleSubmit, formState: { errors } } = useForm<ConfigFormData>({
    values: {
      pact_dir: project?.pact_dir || "",
      model_override: (project as any)?.model_override || "",
      auto_advance: (project as any)?.auto_advance || false,
    },
  })

  async function onSubmit(data: ConfigFormData) {
    try {
      await updateProject({
        id: projectId,
        pact_dir: data.pact_dir || undefined,
        ...(data.model_override ? { model_override: data.model_override } : { model_override: null }),
        auto_advance: data.auto_advance,
      } as ProjectUpdate & { id: string; model_override?: string | null; auto_advance?: boolean })
      toast.success("Configuration saved")
    } catch {
      toast.error("Failed to save configuration")
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <Settings size={16} />
          PACT Configuration
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 max-w-lg">
          <div>
            <label className="text-sm font-medium">PACT Directory</label>
            <Input
              {...register("pact_dir", {
                validate: (v) =>
                  !v || v.startsWith("/") || "Path must be absolute (start with /)",
              })}
              placeholder="/data/.openclaw/workspace/my-project"
              className="mt-1 font-mono text-sm"
            />
            {errors.pact_dir && (
              <p className="text-xs text-destructive mt-1">{errors.pact_dir.message}</p>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Absolute path to the PACT project directory on the host
            </p>
          </div>

          <div>
            <label className="text-sm font-medium">Model Override</label>
            <Input
              {...register("model_override")}
              placeholder="claude-opus-4-5 (leave blank to use default)"
              className="mt-1 font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Override the AI model for this project's PACT runs
            </p>
          </div>

          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="auto_advance"
              {...register("auto_advance")}
              className="rounded"
            />
            <div>
              <label htmlFor="auto_advance" className="text-sm font-medium cursor-pointer">
                Auto-advance phases
              </label>
              <p className="text-xs text-muted-foreground">
                Automatically proceed to the next phase when the current one completes
              </p>
            </div>
          </div>

          <div className="pt-2">
            <Button type="submit" disabled={isPending}>
              {isPending ? "Saving..." : "Save Configuration"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function ProjectDetailPage() {
  const { projectId } = Route.useParams()
  const { data: project, isLoading } = useProject(projectId)
  const { data: tasks = [] } = useTasks(projectId)
  const { data: agents = [] } = useAgents()
  const { mutateAsync: updateTask } = useUpdateTask()
  const { mutateAsync: deleteTask } = useDeleteTask()
  const hasPact = !!project?.pact_dir
  const { data: pactStatus } = usePactStatus(projectId, hasPact)
  const { data: pactComponents = [] } = usePactComponents(projectId, hasPact)

  const [addTaskOpen, setAddTaskOpen] = useState(false)
  const [addTaskStatus, setAddTaskStatus] = useState<TaskStatus>("backlog")
  const [activeTab, setActiveTab] = useState("tasks")

  async function handleStatusChange(taskId: string, newStatus: TaskStatus) {
    const task = tasks.find((t) => t.id === taskId)
    if (!task) return
    try {
      await updateTask({ id: taskId, project_id: projectId, status: newStatus })
    } catch {
      toast.error("Failed to update task")
    }
  }

  async function handleDeleteTask(taskId: string) {
    try {
      await deleteTask({ id: taskId, project_id: projectId })
      toast.success("Task deleted")
    } catch {
      toast.error("Failed to delete task")
    }
  }

  function handleAddTask(status: TaskStatus) {
    setAddTaskStatus(status)
    setAddTaskOpen(true)
  }

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!project) return <div className="text-muted-foreground">Project not found.</div>

  // Determine if Logs tab is actively streaming
  const isLogsTabOpen = activeTab === "logs"

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/projects" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <Badge variant="secondary">{project.status}</Badge>
            {hasPact && <Badge variant="outline">PACT</Badge>}
          </div>
          {project.description && (
            <p className="text-muted-foreground text-sm mt-0.5">{project.description}</p>
          )}
        </div>
        <Link to="/projects/$projectId/memory" params={{ projectId }}>
          <Button variant="outline" size="sm">
            <Brain size={14} className="mr-1" /> Memory
          </Button>
        </Link>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="tasks">Tasks ({tasks.length})</TabsTrigger>
          {hasPact && <TabsTrigger value="pact">PACT Pipeline</TabsTrigger>}
          {hasPact && <TabsTrigger value="components">Components ({pactComponents.length})</TabsTrigger>}
          {hasPact && <TabsTrigger value="logs">Logs</TabsTrigger>}
          <TabsTrigger value="config">Config</TabsTrigger>
        </TabsList>

        <TabsContent value="tasks" className="mt-4">
          <div className="flex justify-end mb-4">
            <Button size="sm" onClick={() => handleAddTask("backlog")}>
              <Plus size={14} className="mr-1" /> Add Task
            </Button>
          </div>
          <KanbanBoard
            tasks={tasks}
            onStatusChange={handleStatusChange}
            onDeleteTask={handleDeleteTask}
            onAddTask={handleAddTask}
          />
        </TabsContent>

        {hasPact && (
          <TabsContent value="pact" className="mt-4 space-y-6">
            {pactStatus ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Pipeline Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <PactPipeline
                    status={pactStatus}
                    projectId={projectId}
                  />
                </CardContent>
              </Card>
            ) : (
              <p className="text-muted-foreground text-sm">Loading PACT status...</p>
            )}
          </TabsContent>
        )}

        {hasPact && (
          <TabsContent value="components" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Components</CardTitle>
              </CardHeader>
              <CardContent>
                <PactComponentTree
                  components={pactComponents}
                  projectId={projectId}
                />
              </CardContent>
            </Card>
          </TabsContent>
        )}

        {hasPact && (
          <TabsContent value="logs" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Execution Logs</CardTitle>
              </CardHeader>
              <CardContent>
                <PactLogViewer
                  projectId={projectId}
                  streaming={isLogsTabOpen}
                />
              </CardContent>
            </Card>
          </TabsContent>
        )}

        <TabsContent value="config" className="mt-4">
          <ConfigTab projectId={projectId} />
        </TabsContent>
      </Tabs>

      <AddTaskDialog
        open={addTaskOpen}
        onClose={() => setAddTaskOpen(false)}
        projectId={projectId}
        defaultStatus={addTaskStatus}
        agentIds={agents.map((a) => a.id)}
      />
    </div>
  )
}
