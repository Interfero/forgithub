import mermaid from 'mermaid'
import { useEffect, useId, useState } from 'react'

let mermaidReady = false

function ensureMermaid() {
  if (mermaidReady) return
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'strict',
    fontFamily: 'inherit',
  })
  mermaidReady = true
}

interface MermaidBlockProps {
  chart: string
}

export function MermaidBlock({ chart }: MermaidBlockProps) {
  const id = useId().replace(/:/g, '')
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const source = chart.trim()
    if (!source) return

    let cancelled = false
    ensureMermaid()

    void (async () => {
      try {
        const { svg: rendered } = await mermaid.render(`mermaid-${id}`, source)
        if (!cancelled) {
          setSvg(rendered)
          setError(null)
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Ошибка диаграммы')
          setSvg(null)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [chart, id])

  if (error) {
    return (
      <pre className="my-2 overflow-x-auto rounded-md bg-muted p-3 text-xs text-destructive">
        {error}
      </pre>
    )
  }

  if (!svg) {
    return (
      <div className="my-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        Рендер диаграммы…
      </div>
    )
  }

  return (
    <div
      className="jarvis-mermaid my-3 overflow-x-auto rounded-md border border-border bg-muted/30 p-3"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
