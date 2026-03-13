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
import {
  useProject,
  useTasks,
  useCreateTask,
  useUpdateTask,
  useDeleteTask,
  usePactStatus,
  usePactComponents,
  useAgents,
  type TaskCreate,
  type TaskStatus,
} from "@/hooks/useMissionControl"
import { ArrowLeft, Plus, Brain } from "lucide-react"
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

      <Tabs defaultValue="tasks">
        <TabsList>
          <TabsTrigger value="tasks">Tasks ({tasks.length})</TabsTrigger>
          {hasPact && <TabsTrigger value="pact">PACT Pipeline</TabsTrigger>}
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
              <>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Pipeline Status</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <PactPipeline status={pactStatus} />
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Components</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <PactComponentTree components={pactComponents} />
                  </CardContent>
                </Card>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">Loading PACT status...</p>
            )}
          </TabsContent>
        )}
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
