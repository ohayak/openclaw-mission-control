import { createFileRoute, Link, useNavigate } from "@tanstack/react-router"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AgentCard } from "@/components/MissionControl/AgentCard"
import { useAgents } from "@/hooks/useMissionControl"

export const Route = createFileRoute("/_layout/agents")({
  component: AgentsPage,
  head: () => ({ meta: [{ title: "Agents — Mission Control" }] }),
})

function AgentsPage() {
  const navigate = useNavigate()
  const { data: agents = [], isLoading } = useAgents()
  const activeAgents = agents.filter((a) => a.is_active)
  const idleAgents = agents.filter((a) => !a.is_active)

  function formatTokens(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
    return String(n)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Agents</h1>
        <p className="text-muted-foreground mt-1">
          {agents.length} agents · {activeAgents.length} active
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-36" />)}
        </div>
      ) : (
        <>
          {activeAgents.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-green-400 mb-3 uppercase tracking-wide">Active</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {activeAgents.map((a) => (
                  <AgentCard
                    key={a.id}
                    agent={a}
                    onClick={() => navigate({ to: "/agents/$agentId", params: { agentId: a.id } })}
                  />
                ))}
              </div>
            </section>
          )}
          {idleAgents.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">Idle</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {idleAgents.map((a) => (
                  <AgentCard
                    key={a.id}
                    agent={a}
                    onClick={() => navigate({ to: "/agents/$agentId", params: { agentId: a.id } })}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Token summary table */}
          {agents.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-3">Token Usage Summary</h2>
              <Card>
                <CardContent className="p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-4 text-muted-foreground font-medium">Agent</th>
                        <th className="text-right p-4 text-muted-foreground font-medium">Sessions</th>
                        <th className="text-right p-4 text-muted-foreground font-medium">Input</th>
                        <th className="text-right p-4 text-muted-foreground font-medium">Output</th>
                        <th className="text-right p-4 text-muted-foreground font-medium">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agents
                        .sort((a, b) => b.total_tokens - a.total_tokens)
                        .map((agent) => (
                          <tr key={agent.id} className="border-b last:border-0 hover:bg-muted/30">
                            <td className="p-4">
                              <div className="flex items-center gap-2">
                                <span>{agent.identity?.emoji || "🤖"}</span>
                                <Link
                                  to="/agents/$agentId"
                                  params={{ agentId: agent.id }}
                                  className="font-medium hover:text-primary"
                                >
                                  {agent.identity?.name || agent.name}
                                </Link>
                                {agent.is_active && (
                                  <Badge className="bg-green-500 text-white text-xs px-1.5 py-0">live</Badge>
                                )}
                              </div>
                            </td>
                            <td className="p-4 text-right text-muted-foreground">{agent.total_sessions}</td>
                            <td className="p-4 text-right text-muted-foreground">{formatTokens(agent.total_input_tokens)}</td>
                            <td className="p-4 text-right text-muted-foreground">{formatTokens(agent.total_output_tokens)}</td>
                            <td className="p-4 text-right font-semibold">{formatTokens(agent.total_tokens)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </section>
          )}
        </>
      )}
    </div>
  )
}
