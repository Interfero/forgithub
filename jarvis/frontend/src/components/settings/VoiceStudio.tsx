import { Mic, Upload } from 'lucide-react'
import { useCallback, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { uploadVoiceSlot } from '@/api/client'
import type { VoiceSlot, VoiceSlotStatus } from '@/types'

const STATUS_STYLES: Record<VoiceSlotStatus, string> = {
  empty: 'text-muted-foreground',
  checking: 'text-amber-600 dark:text-amber-400',
  ready: 'text-emerald-600 dark:text-emerald-400',
  error: 'text-destructive',
}

interface VoiceStudioProps {
  slots: VoiceSlot[]
  onUpdate: (slot: VoiceSlot) => void
  onRefresh: () => void
}

export function VoiceStudio({ slots, onUpdate, onRefresh }: VoiceStudioProps) {
  const [recordingSlot, setRecordingSlot] = useState<number | null>(null)
  const mediaRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])

  const stopRecording = useCallback(() => {
    mediaRef.current?.stop()
    setRecordingSlot(null)
  }, [])

  const startRecording = useCallback(async (slot: number) => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const updated = await uploadVoiceSlot(slot, blob, `recording_slot${slot}.webm`)
        onUpdate(updated)
        onRefresh()
      }
      mediaRef.current = recorder
      recorder.start()
      setRecordingSlot(slot)
    } catch {
      alert('Нет доступа к микрофону')
    }
  }, [onUpdate, onRefresh])

  const handleFile = async (slot: number, file: File) => {
    const updated = await uploadVoiceSlot(slot, file, file.name)
    onUpdate(updated)
    onRefresh()
  }

  return (
    <div className="space-y-3">
      {[1, 2, 3].map((n) => {
        const slot = slots.find((s) => s.slot === n) ?? {
          slot: n,
          status: 'empty' as const,
          message: 'Пусто',
          durationSec: null,
          filename: null,
        }
        const isRec = recordingSlot === n

        return (
          <div
            key={n}
            className="rounded-lg border border-border bg-muted/20 p-3"
          >
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium">Слот {n}</span>
              <span className={cn('text-xs font-medium', STATUS_STYLES[slot.status])}>
                {slot.message}
                {slot.durationSec != null && ` · ${slot.durationSec}с`}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={() => (isRec ? stopRecording() : startRecording(n))}
              >
                <Mic className={cn('h-3.5 w-3.5', isRec && 'animate-pulse text-red-500')} />
                {isRec ? 'Стоп' : 'Записать с микрофона'}
              </Button>
              <label className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-input bg-background px-3 py-1.5 text-xs font-medium hover:bg-muted">
                <Upload className="h-3.5 w-3.5" />
                Загрузить файл
                <input
                  type="file"
                  accept="audio/*,.wav,.mp3,.webm,.ogg,.m4a,.flac,.aac,.opus"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) void handleFile(n, f)
                    e.target.value = ''
                  }}
                />
              </label>
            </div>
            {slot.filename && (
              <p className="mt-1 truncate text-[10px] text-muted-foreground">{slot.filename}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
