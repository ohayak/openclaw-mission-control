import { createFileRoute, Link } from "@tanstack/react-router"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useAgent, useAgentSessions } from "@/hooks/useMissionControl"
import { ArrowLeft, Clock, Server } from "lucide-react"

export const Route = createFileRoute("/_layout/agents/$agentId")({
  component: AgentDetailPage,
  head: () => ({ meta: [{ title: "Agent Detail — Mission Control" }] }),
})

function AgentDetailPage() {
  const { agentId } = Route.useParams()
  const { data: agent, isLoading } = useAgent(agentId)
  const { data: sessions = [], isLoading: sessionsLoading } = useAgentSessions(agentId)

  function formatTokens(n: number) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
    return String(n)
  }

  if (isLoading) return <Skeleton className="h-64 w-full" />
  if (!agent) return <div className="text-muted-foreground">Agent not found.</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/agents" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft size={18} />
        </Link>
        <div className="flex items-center gap-3">
          <span className="text-4xl">{agent.identity?.emoji || "🤖"}</span>
          <div>
            <h1 className="text-2xl font-bold">{agent.identity?.name || agent.name}</h1>
            <p className="text-muted-foreground text-sm">{agent.id}</p>
          </div>
          <Badge
            variant={agent.is_active ? "default" : "secondary"}
            className={agent.is_active ? "bg-green-500 text-white" : ""}
          >
            {agent.is_active ? "Active" : "Idle"}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Sessions", value: agent.total_sessions },
          { label: "Active Sessions", value: agent.active_session_count },
          { label: "Input Tokens", value: formatTokens(agent.total_input_tokens) },
          { label: "Output Tokens", value: formatTokens(agent.total_output_tokens) },
        ].map((s) => (
          <Card key={s.label}>
            <CardContent className="pt-6">
              <p className="text-2xl font-bold">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {agent.model && (
        <Card>
          <CardContent className="p-4 flex items-center gap-2">
            <Server size={14} className="text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Model:</span>
            <span className="text-sm font-mono">{agent.model}</span>
          </CardContent>
        </Card>
      )}

      {/* Sessions */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Sessions ({sessions.length})</h2>
        {sessionsLoading ? (
          <div className="space-y-2">{[...Array(5)].map((_, i) => <Skeleton key={i} className="h-16" />)}</div>
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-4 text-muted-foreground font-medium">Session</th>
                      <th className="text-left p-4 text-muted-foreground font-medium">Started</th>
                      <th className="text-right p-4 text-muted-foreground font-medium">Messages</th>
                      <th className="text-right p-4 text-muted-foreground font-medium">Tokens</th>
                      <th className="text-left p-4 text-muted-foreground font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((session) => (
                      <tr key={session.id} className="border-b last:border-0 hover:bg-muted/20">
                        <td className="p-4 font-mono text-xs text-muted-foreground truncate max-w-[200px]">
                          {session.id.slice(0, 8)}...
                        </td>
                        <td className="p-4 text-xs">
                          <div className="flex items-center gap-1">
                            <Clock size={11} className="text-muted-foreground" />
                            {session.started_at
                              ? new Date(session.started_at).toLocaleString()
                              : "—"}
                          </div>
                        </td>
                        <td className="p-4 text-right">{session.message_count}</td>
                        <td className="p-4 text-right">{formatTokens(session.total_tokens)}</td>
                        <td className="p-4">
                          <Badge
                            variant={session.is_active ? "default" : "secondary"}
                            className={`text-xs ${session.is_active ? "bg-green-500 text-white" : ""}`}
                          >
                            {session.is_active ? "active" : "ended"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                    {sessions.length === 0 && (
                      <tr>
                        <td colSpan={5} className="p-8 text-center text-muted-foreground">
                          No sessions found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  )
}
