import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts"
import type { CostByAgent, CostByProject } from "@/hooks/useMissionControl"

const AGENT_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444"]

interface CostChartProps {
  data: CostByAgent[] | CostByProject[]
  mode: "agent" | "project"
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

export function CostChart({ data, mode }: CostChartProps) {
  const chartData = mode === "agent"
    ? (data as CostByAgent[]).map((d) => ({
        name: d.agent_name || d.agent_id,
        total: d.total_tokens,
        input: d.total_input_tokens,
        output: d.total_output_tokens,
      }))
    : (data as CostByProject[]).map((d) => ({
        name: d.project_name,
        total: d.total_tokens,
      }))

  if (chartData.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted-foreground">
        No token data available
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={chartData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={formatTokens}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value: number) => [formatTokens(value), "Tokens"]}
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            color: "hsl(var(--foreground))",
          }}
        />
        <Bar dataKey="total" radius={[4, 4, 0, 0]}>
          {chartData.map((_, idx) => (
            <Cell key={idx} fill={AGENT_COLORS[idx % AGENT_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

interface AgentTokenBreakdownProps {
  agents: CostByAgent[]
}

export function AgentTokenBreakdown({ agents }: AgentTokenBreakdownProps) {
  const data = agents.map((a) => ({
    name: a.agent_name || a.agent_id,
    input: a.total_input_tokens,
    output: a.total_output_tokens,
  }))

  if (data.length === 0) return null

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={formatTokens}
          tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          formatter={(value: number, name: string) => [formatTokens(value), name]}
          contentStyle={{
            background: "hsl(var(--card))",
            border: "1px solid hsl(var(--border))",
            borderRadius: "8px",
            color: "hsl(var(--foreground))",
          }}
        />
        <Bar dataKey="input" name="Input" fill="#3b82f6" radius={[2, 2, 0, 0]} stackId="a" />
        <Bar dataKey="output" name="Output" fill="#10b981" radius={[2, 2, 0, 0]} stackId="a" />
      </BarChart>
    </ResponsiveContainer>
  )
}
