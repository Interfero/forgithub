import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const COLORS = ['#2dd4bf', '#38bdf8', '#a78bfa', '#f472b6', '#fbbf24', '#34d399']

type ChartSpec = {
  type?: 'bar' | 'line' | 'pie'
  title?: string
  labels: string[]
  values: number[]
}

function parseChartSpec(raw: string): ChartSpec | null {
  try {
    const data = JSON.parse(raw) as ChartSpec
    if (!Array.isArray(data.labels) || !Array.isArray(data.values)) return null
    if (data.labels.length === 0 || data.labels.length !== data.values.length) return null
    return data
  } catch {
    return null
  }
}

interface ChartBlockProps {
  source: string
}

export function ChartBlock({ source }: ChartBlockProps) {
  const spec = parseChartSpec(source)
  if (!spec) {
    return (
      <pre className="my-2 overflow-x-auto rounded-md bg-muted p-3 text-xs">
        {source}
      </pre>
    )
  }

  const rows = spec.labels.map((label, i) => ({
    name: label,
    value: Number(spec.values[i]) || 0,
  }))

  const chartType = spec.type ?? 'bar'

  return (
    <div className="jarvis-chart my-3 w-full min-w-[280px] rounded-md border border-border bg-muted/20 p-3">
      {spec.title ? (
        <p className="mb-2 text-center text-sm font-medium">{spec.title}</p>
      ) : null}
      <ResponsiveContainer width="100%" height={260}>
        {chartType === 'line' ? (
          <LineChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#2dd4bf" strokeWidth={2} />
          </LineChart>
        ) : chartType === 'pie' ? (
          <PieChart>
            <Pie data={rows} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90}>
              {rows.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        ) : (
          <BarChart data={rows}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.35} />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#2dd4bf" radius={[4, 4, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
