/** HTML-отчёт «проанализируй авито» (маркер <!-- jarvis-avito-report -->) */

const MARKER = '<!-- jarvis-avito-report -->'

export function isJarvisAvitoReport(content: string): boolean {
  return content.includes(MARKER)
}

export function extractAvitoReportHtml(content: string): string {
  return content.replace(MARKER, '').trim()
}

interface JarvisAvitoReportProps {
  html: string
}

export function JarvisAvitoReport({ html }: JarvisAvitoReportProps) {
  return (
    <div
      className="jarvis-avito-report-host markdown-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
