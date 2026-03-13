import { createFileRoute } from "@tanstack/react-router"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ActivityFeed } from "@/components/MissionControl/ActivityFeed"
import { useActivity } from "@/hooks/useMissionControl"
import { Activity } from "lucide-react"

export const Route = createFileRoute("/_layout/activity")({
  component: ActivityPage,
  head: () => ({ meta: [{ title: "Activity — Mission Control" }] }),
})

function ActivityPage() {
  const { data: events = [], isLoading } = useActivity(100)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Activity size={20} className="text-muted-foreground" />
        <div>
          <h1 className="text-2xl font-bold">Activity Feed</h1>
          <p className="text-muted-foreground text-sm">Real-time events from agents and pipelines</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Live Events</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-sm">Loading...</p>
          ) : (
            <ActivityFeed
              initialEvents={events}
              maxHeight={600}
              liveSSE={true}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
