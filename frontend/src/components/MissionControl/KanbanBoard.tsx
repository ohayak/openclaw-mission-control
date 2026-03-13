import { useState } from "react"
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from "@dnd-kit/core"
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import type { Task, TaskStatus } from "@/hooks/useMissionControl"
import { GripVertical, Plus, Trash2 } from "lucide-react"

const COLUMNS: { id: TaskStatus; label: string; color: string }[] = [
  { id: "backlog", label: "Backlog", color: "text-slate-400" },
  { id: "in_progress", label: "In Progress", color: "text-blue-400" },
  { id: "review", label: "Review", color: "text-yellow-400" },
  { id: "done", label: "Done", color: "text-green-400" },
]

const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  medium: "bg-blue-500/20 text-blue-400 border-blue-500/30",
  low: "bg-slate-500/20 text-slate-400 border-slate-500/30",
}

interface TaskCardProps {
  task: Task
  isDragging?: boolean
  onDelete?: (id: string) => void
}

function TaskCard({ task, isDragging, onDelete }: TaskCardProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  }

  return (
    <div ref={setNodeRef} style={style}>
      <Card className="group mb-2 cursor-default hover:border-primary/40">
        <CardContent className="p-3">
          <div className="flex items-start gap-2">
            <button
              {...attributes}
              {...listeners}
              className="mt-0.5 cursor-grab touch-none opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <GripVertical size={14} className="text-muted-foreground" />
            </button>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium leading-tight truncate">{task.title}</p>
              {task.description && (
                <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">{task.description}</p>
              )}
              <div className="flex items-center gap-1.5 mt-1.5 flex-wrap">
                <Badge
                  variant="outline"
                  className={`text-xs px-1.5 py-0 ${PRIORITY_COLORS[task.priority] || ""}`}
                >
                  {task.priority}
                </Badge>
                {task.assigned_agent_id && (
                  <Badge variant="secondary" className="text-xs px-1.5 py-0">
                    {task.assigned_agent_id}
                  </Badge>
                )}
              </div>
            </div>
            {onDelete && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(task.id) }}
                className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
              >
                <Trash2 size={13} />
              </button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

interface KanbanBoardProps {
  tasks: Task[]
  onStatusChange: (taskId: string, newStatus: TaskStatus) => void
  onDeleteTask?: (taskId: string) => void
  onAddTask?: (status: TaskStatus) => void
}

export function KanbanBoard({ tasks, onStatusChange, onDeleteTask, onAddTask }: KanbanBoardProps) {
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    })
  )

  const tasksByStatus = (status: TaskStatus) => tasks.filter((t) => t.status === status)

  function handleDragStart(event: DragStartEvent) {
    const task = tasks.find((t) => t.id === event.active.id)
    setActiveTask(task || null)
  }

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    setActiveTask(null)

    if (!over) return

    // Check if dropped over a column container
    const targetStatus = COLUMNS.find((c) => c.id === over.id)?.id
    if (targetStatus) {
      const task = tasks.find((t) => t.id === active.id)
      if (task && task.status !== targetStatus) {
        onStatusChange(String(active.id), targetStatus)
      }
      return
    }

    // Dropped over another task — move to that task's column
    const targetTask = tasks.find((t) => t.id === over.id)
    if (targetTask) {
      const task = tasks.find((t) => t.id === active.id)
      if (task && task.status !== targetTask.status) {
        onStatusChange(String(active.id), targetTask.status)
      }
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {COLUMNS.map((col) => {
          const colTasks = tasksByStatus(col.id)
          return (
            <div
              key={col.id}
              id={col.id}
              className="flex flex-col min-h-[200px] rounded-lg border border-border bg-muted/30 p-3"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <h3 className={`text-sm font-semibold ${col.color}`}>{col.label}</h3>
                  <Badge variant="secondary" className="text-xs px-1.5 py-0">
                    {colTasks.length}
                  </Badge>
                </div>
                {onAddTask && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => onAddTask(col.id)}
                  >
                    <Plus size={12} />
                  </Button>
                )}
              </div>
              <SortableContext
                items={colTasks.map((t) => t.id)}
                strategy={verticalListSortingStrategy}
              >
                {colTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    isDragging={activeTask?.id === task.id}
                    onDelete={onDeleteTask}
                  />
                ))}
              </SortableContext>
              {colTasks.length === 0 && (
                <div className="flex-1 flex items-center justify-center">
                  <p className="text-xs text-muted-foreground">No tasks</p>
                </div>
              )}
            </div>
          )
        })}
      </div>
      <DragOverlay>
        {activeTask && (
          <div className="rotate-2 opacity-90">
            <TaskCard task={activeTask} />
          </div>
        )}
      </DragOverlay>
    </DndContext>
  )
}
