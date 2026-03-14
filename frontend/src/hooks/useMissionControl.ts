/**
 * React Query hooks for Mission Control API endpoints.
 * Uses the same axios/OpenAPI base as the existing client.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState } from "react"
import axios from "axios"
import { OpenAPI } from "@/client"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentIdentity {
  name: string
  emoji?: string
  avatar?: string
  theme?: string
}

export interface AgentInfo {
  id: string
  name: string
  workspace?: string
  model?: string
  identity?: AgentIdentity
  is_active: boolean
  active_session_count: number
  total_sessions: number
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
}

export interface SessionInfo {
  id: string
  agent_id: string
  filename: string
  is_active: boolean
  started_at?: string
  cwd?: string
  message_count: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  model?: string
}

export interface Project {
  id: string
  name: string
  description?: string
  status: "active" | "paused" | "completed" | "archived"
  pact_dir?: string
  model_override?: string | null
  auto_advance?: boolean
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  status?: Project["status"]
  pact_dir?: string
  model_override?: string | null
  auto_advance?: boolean
}

export interface ProjectUpdate {
  name?: string
  description?: string
  status?: Project["status"]
  pact_dir?: string
  model_override?: string | null
  auto_advance?: boolean
}

export type TaskStatus = "backlog" | "in_progress" | "review" | "done"

export interface Task {
  id: string
  project_id: string
  title: string
  description?: string
  status: TaskStatus
  priority: "low" | "medium" | "high" | "critical"
  assigned_agent_id?: string
  pact_component_id?: string
  created_at: string
  updated_at: string
}

export interface TaskCreate {
  project_id: string
  title: string
  description?: string
  status?: Task["status"]
  priority?: Task["priority"]
  assigned_agent_id?: string
  pact_component_id?: string
}

export interface TaskUpdate {
  title?: string
  description?: string
  status?: Task["status"]
  priority?: Task["priority"]
  assigned_agent_id?: string
  pact_component_id?: string
}

export interface PactStatus {
  project_id: string
  phase: string
  status: string
  has_decomposition: boolean
  has_contracts: boolean
  component_count: number
  components_contracted: number
  components_tested: number
  components_implemented: number
}

export interface PactComponent {
  id: string
  name: string
  description?: string
  layer?: string
  dependencies: string[]
  has_contract: boolean
  has_tests: boolean
  has_implementation: boolean
  test_passed?: number
  test_failed?: number
  test_total?: number
}

export interface ActivityEvent {
  id: string
  event_type: string
  agent_id?: string
  project_id?: string
  message: string
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface CostByAgent {
  agent_id: string
  agent_name: string
  total_input_tokens: number
  total_output_tokens: number
  total_tokens: number
  session_count: number
}

export interface CostByProject {
  project_id: string
  project_name: string
  assigned_agent_ids: string[]
  total_tokens: number
}

export interface MemoryFile {
  path: string
  filename: string
  content: string
  last_modified?: string
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function getToken(): string {
  const token = OpenAPI.TOKEN
  if (typeof token === "string") return token
  // If it's a resolver function or undefined, fall back to localStorage
  return localStorage.getItem("access_token") || ""
}

async function apiGet<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const token = getToken()
  const base = OpenAPI.BASE || ""
  const url = `${base}/api/v1${path}`
  const resp = await axios.get<T>(url, {
    headers: { Authorization: `Bearer ${token}` },
    params,
  })
  return resp.data
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const token = getToken()
  const base = OpenAPI.BASE || ""
  const url = `${base}/api/v1${path}`
  const resp = await axios.post<T>(url, body, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return resp.data
}

async function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  const token = getToken()
  const base = OpenAPI.BASE || ""
  const url = `${base}/api/v1${path}`
  const resp = await axios.patch<T>(url, body, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return resp.data
}

async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  const token = getToken()
  const base = OpenAPI.BASE || ""
  const url = `${base}/api/v1${path}`
  const resp = await axios.put<T>(url, body, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return resp.data
}

async function apiDelete<T>(path: string): Promise<T> {
  const token = getToken()
  const base = OpenAPI.BASE || ""
  const url = `${base}/api/v1${path}`
  const resp = await axios.delete<T>(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return resp.data
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: () => apiGet<AgentInfo[]>("/agents/"),
    refetchInterval: 15000,
  })
}

export function useAgent(agentId: string) {
  return useQuery({
    queryKey: ["agents", agentId],
    queryFn: () => apiGet<AgentInfo>(`/agents/${agentId}`),
    refetchInterval: 15000,
  })
}

export function useAgentSessions(agentId: string) {
  return useQuery({
    queryKey: ["agents", agentId, "sessions"],
    queryFn: () => apiGet<SessionInfo[]>(`/agents/${agentId}/sessions`),
  })
}

// ---------------------------------------------------------------------------
// Projects
// ---------------------------------------------------------------------------

export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () => apiGet<{ data: Project[]; count: number }>("/projects/"),
    select: (d) => d.data,
  })
}

export function useProject(projectId: string) {
  return useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => apiGet<Project>(`/projects/${projectId}`),
    enabled: !!projectId,
  })
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ProjectCreate) => apiPost<Project>("/projects/", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  })
}

export function useUpdateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: ProjectUpdate & { id: string }) =>
      apiPatch<Project>(`/projects/${id}`, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["projects"] })
      qc.invalidateQueries({ queryKey: ["projects", vars.id] })
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/projects/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  })
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

export function useTasks(projectId?: string) {
  return useQuery({
    queryKey: ["tasks", projectId],
    queryFn: () =>
      apiGet<{ data: Task[]; count: number }>("/tasks/", projectId ? { project_id: projectId } : undefined),
    select: (d) => d.data,
    enabled: true,
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: TaskCreate) => apiPost<Task>("/tasks/", data),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      qc.invalidateQueries({ queryKey: ["tasks", t.project_id] })
    },
  })
}

export function useUpdateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: TaskUpdate & { id: string; project_id: string }) =>
      apiPatch<Task>(`/tasks/${id}`, data),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      qc.invalidateQueries({ queryKey: ["tasks", t.project_id] })
    },
  })
}

export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, project_id }: { id: string; project_id: string }) =>
      apiDelete(`/tasks/${id}`).then((r) => ({ r, project_id })),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["tasks"] })
      qc.invalidateQueries({ queryKey: ["tasks", vars.project_id] })
    },
  })
}

// ---------------------------------------------------------------------------
// PACT
// ---------------------------------------------------------------------------

export function usePactStatus(projectId: string, enabled = true) {
  return useQuery({
    queryKey: ["pact", projectId, "status"],
    queryFn: () => apiGet<PactStatus>(`/pact/${projectId}/status`),
    enabled: !!projectId && enabled,
    // Poll every 3s when running, 30s otherwise (TanStack Query v5 dynamic interval)
    refetchInterval: (query) => {
      return query.state.data?.status === "running" ? 3000 : 30000
    },
    retry: false,
  })
}

export function usePactComponents(projectId: string, enabled = true) {
  return useQuery({
    queryKey: ["pact", projectId, "components"],
    queryFn: () => apiGet<PactComponent[]>(`/pact/${projectId}/components`),
    enabled: !!projectId && enabled,
    retry: false,
  })
}

export function usePactInit(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<{ status: string }>(`/pact/${projectId}/init`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pact", projectId, "status"] })
    },
  })
}

export function usePactRun(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (phase?: string) =>
      apiPost<{ status: string }>(`/pact/${projectId}/run`, phase ? { phase } : {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pact", projectId, "status"] })
    },
  })
}

export function usePactInterviewStart(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<{ status: string }>(`/pact/${projectId}/interview/start`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pact", projectId, "status"] })
    },
  })
}

export function usePactComponentRetest(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (componentId: string) =>
      apiPost<{ status: string }>(`/pact/${projectId}/components/${componentId}/retest`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pact", projectId, "status"] })
      qc.invalidateQueries({ queryKey: ["pact", projectId, "components"] })
    },
  })
}

export interface PactComponentContract {
  filename: string
  content: string
}

export interface PactComponentTestFile {
  filename: string
  content: string
}

export interface PactComponentTests {
  files: PactComponentTestFile[]
}

export function usePactComponentContract(projectId: string, componentId: string, enabled = true) {
  return useQuery({
    queryKey: ["pact", projectId, "components", componentId, "contract"],
    queryFn: () => apiGet<PactComponentContract>(`/pact/${projectId}/components/${componentId}/contract`),
    enabled: !!projectId && !!componentId && enabled,
    retry: false,
  })
}

export function usePactComponentTests(projectId: string, componentId: string, enabled = true) {
  return useQuery({
    queryKey: ["pact", projectId, "components", componentId, "tests"],
    queryFn: () => apiGet<PactComponentTests>(`/pact/${projectId}/components/${componentId}/tests`),
    enabled: !!projectId && !!componentId && enabled,
    retry: false,
  })
}

/**
 * SSE log streaming hook.
 * Opens an EventSource to the PACT log stream endpoint when enabled.
 * Uses query-param token auth (EventSource doesn't support custom headers).
 * Cleans up the EventSource on unmount.
 */
export function usePactStream(projectId: string, enabled = false) {
  const [lines, setLines] = useState<string[]>([])
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  useEffect(() => {
    if (!enabled || !projectId) return

    const token = getToken()
    const base = OpenAPI.BASE || ""
    // Pass token as query param — EventSource doesn't support Authorization headers
    const url = `${base}/api/v1/pact/${projectId}/stream?token=${encodeURIComponent(token)}`
    const es = new EventSource(url)

    es.onmessage = (e) => {
      setLines((prev) => [...prev, e.data])
    }

    es.addEventListener("done", () => {
      setDone(true)
      es.close()
      // Refresh status + components when run completes
      qc.invalidateQueries({ queryKey: ["pact", projectId, "status"] })
      qc.invalidateQueries({ queryKey: ["pact", projectId, "components"] })
    })

    es.addEventListener("error", (e) => {
      // Custom SSE error event from backend (not connection error)
      const data = (e as MessageEvent).data
      setError(data || "An error occurred during PACT execution")
      es.close()
    })

    es.onerror = () => {
      // Connection error — check if it's an auth issue
      setError("Stream connection failed. If the issue persists, please reload the page.")
      es.close()
    }

    return () => {
      es.close()
    }
  }, [projectId, enabled, qc])

  function reset() {
    setLines([])
    setDone(false)
    setError(null)
  }

  return { lines, done, error, reset }
}

// ---------------------------------------------------------------------------
// Activity
// ---------------------------------------------------------------------------

export function useActivity(limit = 50) {
  return useQuery({
    queryKey: ["activity"],
    queryFn: () => apiGet<ActivityEvent[]>("/activity/", { limit }),
    refetchInterval: 10000,
  })
}

// ---------------------------------------------------------------------------
// Costs
// ---------------------------------------------------------------------------

export function useCostsByAgent() {
  return useQuery({
    queryKey: ["costs", "by-agent"],
    queryFn: () => apiGet<CostByAgent[]>("/costs/by-agent"),
    refetchInterval: 60000,
  })
}

export function useCostsByProject() {
  return useQuery({
    queryKey: ["costs", "by-project"],
    queryFn: () => apiGet<CostByProject[]>("/costs/by-project"),
    refetchInterval: 60000,
  })
}

// ---------------------------------------------------------------------------
// Memory
// ---------------------------------------------------------------------------

export function useMemoryFiles(projectId: string) {
  return useQuery({
    queryKey: ["memory", projectId],
    queryFn: () => apiGet<MemoryFile[]>(`/memory/${projectId}/files`),
    enabled: !!projectId,
  })
}

export function useMemoryFile(projectId: string, filename: string) {
  return useQuery({
    queryKey: ["memory", projectId, filename],
    queryFn: () => apiGet<MemoryFile>(`/memory/${projectId}/files/${filename}`),
    enabled: !!projectId && !!filename,
  })
}

export function useUpdateMemoryFile(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ filename, content }: { filename: string; content: string }) =>
      apiPut<MemoryFile>(`/memory/${projectId}/files/${filename}`, { content }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["memory", projectId] })
      qc.invalidateQueries({ queryKey: ["memory", projectId, vars.filename] })
    },
  })
}
