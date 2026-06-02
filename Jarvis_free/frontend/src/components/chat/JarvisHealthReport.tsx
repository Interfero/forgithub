/** HTML-отчёт «проверка систем» (генерируется бэкендом, маркер <!-- jarvis-health-report -->) */

const MARKER = '<!-- jarvis-health-report -->'

export function isJarvisHealthReport(content: string): boolean {
  return content.includes(MARKER)
}

export function extractHealthReportHtml(content: string): string {
  return content.replace(MARKER, '').trim()
}

interface JarvisHealthReportProps {
  html: string
}

export function JarvisHealthReport({ html }: JarvisHealthReportProps) {
  return (
    <div
      className="jarvis-health-report-host markdown-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
