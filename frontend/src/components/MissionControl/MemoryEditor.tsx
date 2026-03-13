import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Eye, Pencil, Save, Loader2 } from "lucide-react"
import type { MemoryFile } from "@/hooks/useMissionControl"

// Simple markdown-like renderer (no extra deps)
function MarkdownPreview({ content }: { content: string }) {
  // Convert basic markdown to HTML-safe elements
  const lines = content.split("\n")
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-sm leading-relaxed">
      {lines.map((line, i) => {
        if (line.startsWith("# ")) return <h1 key={i} className="text-xl font-bold mt-4 mb-2">{line.slice(2)}</h1>
        if (line.startsWith("## ")) return <h2 key={i} className="text-lg font-semibold mt-3 mb-1.5">{line.slice(3)}</h2>
        if (line.startsWith("### ")) return <h3 key={i} className="text-base font-medium mt-2 mb-1">{line.slice(4)}</h3>
        if (line.startsWith("- ") || line.startsWith("* ")) return (
          <div key={i} className="flex gap-2 my-0.5">
            <span className="text-muted-foreground flex-shrink-0">•</span>
            <span>{line.slice(2)}</span>
          </div>
        )
        if (line.startsWith("---")) return <hr key={i} className="my-3 border-border" />
        if (line.trim() === "") return <div key={i} className="h-2" />
        if (line.startsWith("> ")) return (
          <blockquote key={i} className="border-l-2 border-primary/50 pl-3 text-muted-foreground italic my-1">
            {line.slice(2)}
          </blockquote>
        )
        // Bold and inline code
        const formatted = line
          .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
          .replace(/`([^`]+)`/g, '<code class="bg-muted px-1 rounded text-xs font-mono">$1</code>')
        return <p key={i} className="my-0.5" dangerouslySetInnerHTML={{ __html: formatted }} />
      })}
    </div>
  )
}

interface MemoryEditorProps {
  file: MemoryFile
  onSave: (content: string) => Promise<void>
  isSaving?: boolean
}

export function MemoryEditor({ file, onSave, isSaving = false }: MemoryEditorProps) {
  const [mode, setMode] = useState<"edit" | "preview">("preview")
  const [content, setContent] = useState(file.content)
  const [isDirty, setIsDirty] = useState(false)

  useEffect(() => {
    setContent(file.content)
    setIsDirty(false)
  }, [file.content, file.filename])

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setContent(e.target.value)
    setIsDirty(true)
  }

  async function handleSave() {
    await onSave(content)
    setIsDirty(false)
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{file.filename}</span>
          {isDirty && <Badge variant="outline" className="text-xs">unsaved</Badge>}
          {file.last_modified && (
            <span className="text-xs text-muted-foreground">
              Last modified: {new Date(file.last_modified).toLocaleString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMode(mode === "edit" ? "preview" : "edit")}
          >
            {mode === "edit" ? <Eye size={14} className="mr-1" /> : <Pencil size={14} className="mr-1" />}
            {mode === "edit" ? "Preview" : "Edit"}
          </Button>
          {isDirty && (
            <Button size="sm" onClick={handleSave} disabled={isSaving}>
              {isSaving ? <Loader2 size={14} className="mr-1 animate-spin" /> : <Save size={14} className="mr-1" />}
              Save
            </Button>
          )}
        </div>
      </div>

      {mode === "edit" ? (
        <textarea
          value={content}
          onChange={handleChange}
          className="w-full min-h-[400px] rounded-md border border-input bg-background px-3 py-2 text-sm font-mono resize-y focus:outline-none focus:ring-1 focus:ring-ring"
          placeholder={`# ${file.filename}\n\nStart writing...`}
        />
      ) : (
        <div className="min-h-[200px] rounded-md border border-border bg-muted/20 p-4">
          {content ? (
            <MarkdownPreview content={content} />
          ) : (
            <p className="text-sm text-muted-foreground">
              No content yet. Click Edit to start writing.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
