import { useEffect, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import type { ActivityEvent } from "@/hooks/useMissionControl"
import { OpenAPI } from "@/client"

const EVENT_COLORS: Record<string, string> = {
  session_start: "bg-green-500",
  session_end: "bg-slate-500",
  agent_active: "bg-blue-500",
  task_update: "bg-yellow-500",
  pact_phase: "bg-purple-500",
  pact_audit: "bg-indigo-500",
  default: "bg-muted-foreground",
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
  } catch {
    return ts
  }
}

interface ActivityFeedProps {
  initialEvents?: ActivityEvent[]
  maxHeight?: number
  liveSSE?: boolean
}

export function ActivityFeed({ initialEvents = [], maxHeight = 400, liveSSE = false }: ActivityFeedProps) {
  const [events, setEvents] = useState<ActivityEvent[]>(initialEvents)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Merge incoming initial events
  useEffect(() => {
    setEvents(initialEvents)
  }, [initialEvents])

  // Polling-based live updates (EventSource doesn't support auth headers)
  useEffect(() => {
    if (!liveSSE) return

    const interval = setInterval(async () => {
      try {
        const token = typeof OpenAPI.TOKEN === "string"
          ? OpenAPI.TOKEN
          : localStorage.getItem("access_token") || ""
        const base = OpenAPI.BASE || ""
        const resp = await fetch(`${base}/api/v1/activity/?limit=20`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (resp.ok) {
          const newEvents: ActivityEvent[] = await resp.json()
          setEvents((prev) => {
            const ids = new Set(prev.map((e) => e.id))
            const fresh = newEvents.filter((e) => !ids.has(e.id))
            if (fresh.length === 0) return prev
            return [...fresh, ...prev].slice(0, 200)
          })
        }
      } catch {
        // ignore network errors
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [liveSSE])

  const color = (type: string) => EVENT_COLORS[type] || EVENT_COLORS.default

  return (
    <div style={{ maxHeight, overflowY: "auto" }} className="w-full">
      <div ref={scrollRef} className="space-y-1 pr-2">
        {events.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-8">No activity yet</p>
        )}
        {events.map((event) => (
          <div
            key={event.id}
            className="flex items-start gap-3 p-2 rounded-md hover:bg-muted/30 transition-colors"
          >
            <div className={`mt-1.5 h-2 w-2 rounded-full flex-shrink-0 ${color(event.event_type)}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="outline" className="text-xs px-1.5 py-0">
                  {event.event_type}
                </Badge>
                {event.agent_id && (
                  <span className="text-xs text-muted-foreground">{event.agent_id}</span>
                )}
                <span className="text-xs text-muted-foreground ml-auto flex-shrink-0">
                  {formatTime(event.timestamp)}
                </span>
              </div>
              <p className="text-xs mt-0.5 text-foreground/80">{event.message}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
