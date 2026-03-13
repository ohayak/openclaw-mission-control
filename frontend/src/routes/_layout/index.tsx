import { createFileRoute, Link } from "@tanstack/react-router"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AgentCard } from "@/components/MissionControl/AgentCard"
import { ActivityFeed } from "@/components/MissionControl/ActivityFeed"
import { useAgents, useProjects, useActivity } from "@/hooks/useMissionControl"
import { Activity, Bot, Briefcase, CheckSquare } from "lucide-react"
import { useNavigate } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/")({
  component: Dashboard,
  head: () => ({
    meta: [{ title: "Mission Control" }],
  }),
})

function StatCard({ icon: Icon, label, value, sub }: {
  icon: React.ElementType
  label: string
  value: string | number
  sub?: string
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-md bg-primary/10 text-primary">
            <Icon size={18} />
          </div>
          <div>
            <p className="text-2xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
            {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function Dashboard() {
  const navigate = useNavigate()
  const { data: agents = [], isLoading: agentsLoading } = useAgents()
  const { data: projects = [], isLoading: projectsLoading } = useProjects()
  const { data: activity = [] } = useActivity(20)

  const activeAgents = agents.filter((a) => a.is_active).length
  const activeProjects = projects.filter((p) => p.status === "active").length

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Mission Control</h1>
        <p className="text-muted-foreground mt-1">OpenClaw AI Team Dashboard</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Bot} label="Agents" value={agents.length} sub={`${activeAgents} active`} />
        <StatCard icon={Briefcase} label="Projects" value={projects.length} sub={`${activeProjects} active`} />
        <StatCard icon={Activity} label="Live Sessions" value={activeAgents} />
        <StatCard
          icon={CheckSquare}
          label="Total Tokens"
          value={(() => {
            const t = agents.reduce((sum, a) => sum + a.total_tokens, 0)
            return t >= 1_000_000 ? `${(t / 1_000_000).toFixed(1)}M` : t >= 1_000 ? `${(t / 1_000).toFixed(0)}K` : t
          })()}
        />
      </div>

      {/* Agent Grid */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Agents</h2>
        {agentsLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-32" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                onClick={() => navigate({ to: "/agents/$agentId", params: { agentId: agent.id } })}
              />
            ))}
          </div>
        )}
      </section>

      {/* Projects + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Recent Projects</h2>
            <Link to="/projects" className="text-sm text-primary hover:underline">View all →</Link>
          </div>
          {projectsLoading ? (
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16" />)}
            </div>
          ) : (
            <div className="space-y-2">
              {projects.slice(0, 5).map((project) => (
                <Link
                  key={project.id}
                  to="/projects/$projectId"
                  params={{ projectId: project.id }}
                  className="block"
                >
                  <Card className="hover:border-primary/40 transition-colors cursor-pointer">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-sm">{project.name}</p>
                          {project.description && (
                            <p className="text-xs text-muted-foreground truncate max-w-xs">{project.description}</p>
                          )}
                        </div>
                        <Badge
                          variant={project.status === "active" ? "default" : "secondary"}
                          className={project.status === "active" ? "bg-green-500 text-white" : ""}
                        >
                          {project.status}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
              {projects.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No projects yet.{" "}
                  <Link to="/projects" className="text-primary hover:underline">Create one →</Link>
                </p>
              )}
            </div>
          )}
        </section>

        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">Live Activity</h2>
            <Link to="/activity" className="text-sm text-primary hover:underline">View all →</Link>
          </div>
          <Card>
            <CardContent className="p-4">
              <ActivityFeed initialEvents={activity} maxHeight={320} liveSSE={true} />
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}
