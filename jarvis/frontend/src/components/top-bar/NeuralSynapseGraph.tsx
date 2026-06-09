import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

export type NeuralAnchorId =
  | 'server'
  | 'qwen'
  | 'stt'
  | 'tts'
  | 'browser'
  | 'agent'
  | 'api-cloud'
  | 'telegram'
  | 'avito'
  | 'ats'
  | 'mail'

export type NeuralLinkKind = 'core' | 'cloud' | 'connector' | 'inactive'

export type NeuralLink = {
  from: NeuralAnchorId
  to: NeuralAnchorId
  kind: NeuralLinkKind
  active: boolean
  warn?: boolean
}

type Point = { x: number; y: number }

function cubicPath(a: Point, b: Point, bend = 0.35): string {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const c1 = { x: a.x + dx * bend, y: a.y + dy * 0.05 }
  const c2 = { x: b.x - dx * bend, y: b.y - dy * 0.05 }
  return `M ${a.x} ${a.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${b.x} ${b.y}`
}

function dendritePath(a: Point, b: Point, side: 1 | -1): string {
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  const nx = (-dy / len) * side * 8
  const ny = (dx / len) * side * 8
  return `M ${a.x} ${a.y} Q ${mx + nx} ${my + ny} ${b.x} ${b.y}`
}

const STROKE: Record<NeuralLinkKind, { on: string; off: string; width: number }> = {
  core: { on: 'url(#jarvis-neural-core)', off: 'rgb(100 116 139 / 0.2)', width: 2.2 },
  cloud: { on: 'url(#jarvis-neural-cloud)', off: 'rgb(100 116 139 / 0.15)', width: 1.6 },
  connector: { on: 'url(#jarvis-neural-out)', off: 'rgb(100 116 139 / 0.18)', width: 1.8 },
  inactive: { on: 'rgb(100 116 139 / 0.2)', off: 'rgb(100 116 139 / 0.12)', width: 1 },
}

export function neuralAnchorProps(id: NeuralAnchorId) {
  return { 'data-neural-anchor': id } as const
}

export function NeuralSynapseGraph({
  links,
  className,
}: {
  links: NeuralLink[]
  className?: string
}) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [points, setPoints] = useState<Partial<Record<NeuralAnchorId, Point>>>({})

  useLayoutEffect(() => {
    const host = hostRef.current
    if (!host) return

    const measure = () => {
      const box = host.getBoundingClientRect()
      if (box.width < 8 || box.height < 8) return
      const next: Partial<Record<NeuralAnchorId, Point>> = {}
      host.querySelectorAll<HTMLElement>('[data-neural-anchor]').forEach((el) => {
        const id = el.dataset.neuralAnchor as NeuralAnchorId | undefined
        if (!id) return
        const r = el.getBoundingClientRect()
        next[id] = {
          x: r.left + r.width / 2 - box.left,
          y: r.top + r.height / 2 - box.top,
        }
      })
      setPoints(next)
    }

    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(host)
    window.addEventListener('resize', measure)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', measure)
    }
  }, [links])

  const rendered = useMemo(() => {
    return links
      .map((link) => {
        const a = points[link.from]
        const b = points[link.to]
        if (!a || !b) return null
        const style = STROKE[link.kind]
        const stroke = link.active ? style.on : style.off
        const main = cubicPath(a, b, link.kind === 'core' ? 0.28 : 0.38)
        const branch =
          link.active && link.kind !== 'inactive'
            ? dendritePath(a, b, link.from < link.to ? 1 : -1)
            : null
        return { link, a, b, stroke, main, branch, width: style.width }
      })
      .filter(Boolean)
  }, [links, points])

  return (
    <div ref={hostRef} className={cn('pointer-events-none absolute inset-0', className)} aria-hidden>
      <svg className="h-full w-full overflow-visible">
        <defs>
          <linearGradient id="jarvis-neural-core" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="rgb(56 189 248)" />
            <stop offset="100%" stopColor="rgb(45 212 191)" />
          </linearGradient>
          <linearGradient id="jarvis-neural-cloud" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgb(167 139 250)" />
            <stop offset="100%" stopColor="rgb(96 165 250)" />
          </linearGradient>
          <linearGradient id="jarvis-neural-out" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgb(45 212 191 / 0.9)" />
            <stop offset="100%" stopColor="rgb(129 140 248 / 0.85)" />
          </linearGradient>
          <filter id="jarvis-neural-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2.5" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {rendered.map((item) => {
          if (!item) return null
          const { link, a, b, stroke, main, branch, width } = item
          const glow = link.active && !link.warn
          return (
            <g key={`${link.from}-${link.to}-${link.kind}`}>
              {branch && (
                <path
                  d={branch}
                  fill="none"
                  stroke={stroke}
                  strokeWidth={width * 0.45}
                  strokeLinecap="round"
                  opacity={0.35}
                />
              )}
              <path
                d={main}
                fill="none"
                stroke={stroke}
                strokeWidth={width}
                strokeLinecap="round"
                filter={glow ? 'url(#jarvis-neural-glow)' : undefined}
                className={cn(glow && 'jarvis-neural-axon')}
                opacity={link.active ? 0.92 : 0.35}
              />
              {link.active && (
                <>
                  <circle
                    cx={a.x}
                    cy={a.y}
                    r={3.5}
                    className="fill-slate-950/80 stroke-sky-400/80 jarvis-neural-soma"
                    strokeWidth={1}
                  />
                  <circle
                    cx={b.x}
                    cy={b.y}
                    r={2.8}
                    className="fill-sky-400/90 jarvis-neural-soma"
                  />
                </>
              )}
            </g>
          )
        })}
      </svg>
    </div>
  )
}
