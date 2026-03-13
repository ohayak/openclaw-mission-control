import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import type { AgentInfo } from "@/hooks/useMissionControl"

interface AgentCardProps {
  agent: AgentInfo
  onClick?: () => void
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

export function AgentCard({ agent, onClick }: AgentCardProps) {
  const emoji = agent.identity?.emoji || "🤖"
  const displayName = agent.identity?.name || agent.name

  return (
    <Card
      className={`cursor-pointer transition-all hover:border-primary/50 hover:shadow-md ${
        agent.is_active ? "border-green-500/50 bg-green-500/5" : ""
      }`}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{emoji}</span>
            <div>
              <h3 className="font-semibold text-sm leading-tight">{displayName}</h3>
              <p className="text-xs text-muted-foreground">{agent.id}</p>
            </div>
          </div>
          <Badge
            variant={agent.is_active ? "default" : "secondary"}
            className={agent.is_active ? "bg-green-500 text-white" : ""}
          >
            {agent.is_active ? "Active" : "Idle"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div>
            <p className="font-semibold text-sm">{agent.total_sessions}</p>
            <p className="text-muted-foreground">sessions</p>
          </div>
          <div>
            <p className="font-semibold text-sm">{formatTokens(agent.total_tokens)}</p>
            <p className="text-muted-foreground">tokens</p>
          </div>
          <div>
            <p className="font-semibold text-sm">{agent.active_session_count}</p>
            <p className="text-muted-foreground">active</p>
          </div>
        </div>
        {agent.model && (
          <p className="mt-2 text-xs text-muted-foreground truncate">{agent.model}</p>
        )}
      </CardContent>
    </Card>
  )
}
