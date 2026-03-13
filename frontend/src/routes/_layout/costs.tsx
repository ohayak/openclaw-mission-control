import { createFileRoute } from "@tanstack/react-router"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { CostChart, AgentTokenBreakdown } from "@/components/MissionControl/CostChart"
import { useCostsByAgent, useCostsByProject } from "@/hooks/useMissionControl"
import { DollarSign } from "lucide-react"

export const Route = createFileRoute("/_layout/costs")({
  component: CostsPage,
  head: () => ({ meta: [{ title: "Costs — Mission Control" }] }),
})

function formatTokens(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function CostsPage() {
  const { data: byAgent = [], isLoading: agentLoading } = useCostsByAgent()
  const { data: byProject = [], isLoading: projectLoading } = useCostsByProject()

  const totalTokens = byAgent.reduce((sum, a) => sum + a.total_tokens, 0)

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <DollarSign size={20} className="text-muted-foreground" />
        <div>
          <h1 className="text-2xl font-bold">Costs & Tokens</h1>
          <p className="text-muted-foreground text-sm">
            Total: {formatTokens(totalTokens)} tokens across all agents
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {byAgent.slice(0, 3).map((a) => (
          <Card key={a.agent_id}>
            <CardContent className="pt-6">
              <p className="text-xl font-bold">{formatTokens(a.total_tokens)}</p>
              <p className="text-sm text-muted-foreground">{a.agent_name} · {a.session_count} sessions</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="by-agent">
        <TabsList>
          <TabsTrigger value="by-agent">By Agent</TabsTrigger>
          <TabsTrigger value="by-project">By Project</TabsTrigger>
          <TabsTrigger value="breakdown">Token Breakdown</TabsTrigger>
        </TabsList>

        <TabsContent value="by-agent" className="mt-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Total Tokens by Agent</CardTitle></CardHeader>
            <CardContent>
              {agentLoading ? <Skeleton className="h-60" /> : <CostChart data={byAgent} mode="agent" />}
            </CardContent>
          </Card>

          {/* Table */}
          {!agentLoading && byAgent.length > 0 && (
            <Card className="mt-4">
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-4 font-medium text-muted-foreground">Agent</th>
                      <th className="text-right p-4 font-medium text-muted-foreground">Sessions</th>
                      <th className="text-right p-4 font-medium text-muted-foreground">Input</th>
                      <th className="text-right p-4 font-medium text-muted-foreground">Output</th>
                      <th className="text-right p-4 font-medium text-muted-foreground">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {byAgent.sort((a, b) => b.total_tokens - a.total_tokens).map((a) => (
                      <tr key={a.agent_id} className="border-b last:border-0 hover:bg-muted/20">
                        <td className="p-4 font-medium">{a.agent_name}</td>
                        <td className="p-4 text-right text-muted-foreground">{a.session_count}</td>
                        <td className="p-4 text-right text-muted-foreground">{formatTokens(a.total_input_tokens)}</td>
                        <td className="p-4 text-right text-muted-foreground">{formatTokens(a.total_output_tokens)}</td>
                        <td className="p-4 text-right font-semibold">{formatTokens(a.total_tokens)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="by-project" className="mt-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Tokens by Project</CardTitle></CardHeader>
            <CardContent>
              {projectLoading ? <Skeleton className="h-60" /> : <CostChart data={byProject} mode="project" />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="breakdown" className="mt-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Input vs Output Tokens by Agent</CardTitle></CardHeader>
            <CardContent>
              {agentLoading ? <Skeleton className="h-52" /> : <AgentTokenBreakdown agents={byAgent} />}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
