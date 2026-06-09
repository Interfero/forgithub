import { ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Hint } from '@/components/ui/hint'
import { saveVoiceAccessPermissions } from '@/lib/chatSurfaceMode'
import { cn } from '@/lib/utils'

interface VoiceAccessDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onGranted: () => void
}

export function VoiceAccessDialog({ open, onOpenChange, onGranted }: VoiceAccessDialogProps) {
  const [uiControl, setUiControl] = useState(false)
  const [osControl, setOsControl] = useState(false)

  const canEnable = uiControl && osControl

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Доступ для голосового режима
          </DialogTitle>
          <DialogDescription className="text-xs leading-relaxed">
            Голосовой режим рассчитан на слепых пользователей и hands-free. Без разрешений Jarvis
            не сможет управлять интерфейсом и не активирует режим.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 text-xs">
          <Hint text="Разрешить Jarvis нажимать кнопки в своём интерфейсе (чат, настройки, коннекторы) через ui_*-инструменты.">
            <label
              className={cn(
                'flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 transition-colors',
                uiControl ? 'border-primary/40 bg-primary/5' : 'border-border/70',
              )}
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={uiControl}
                onChange={(e) => setUiControl(e.target.checked)}
              />
              <span>
                <strong className="block text-foreground">Управление интерфейсом Jarvis</strong>
                <span className="text-muted-foreground">
                  Кнопки чата, настроек, Telegram и Авито — через безопасные JSON-инструменты.
                </span>
              </span>
            </label>
          </Hint>

          <Hint text="Разрешить Jarvis выполнять действия на ПК (окна ОС, системные кнопки) — только в рамках будущих automation-инструментов.">
            <label
              className={cn(
                'flex cursor-pointer items-start gap-2 rounded-lg border px-3 py-2 transition-colors',
                osControl ? 'border-primary/40 bg-primary/5' : 'border-border/70',
              )}
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={osControl}
                onChange={(e) => setOsControl(e.target.checked)}
              />
              <span>
                <strong className="block text-foreground">Управление компьютером (ОС)</strong>
                <span className="text-muted-foreground">
                  Системные окна и кнопки Windows — для полноценного голосового ассистента.
                </span>
              </span>
            </label>
          </Hint>
        </div>

        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button
            type="button"
            disabled={!canEnable}
            className="transition-transform hover:scale-[1.02]"
            onClick={() => {
              saveVoiceAccessPermissions({ uiControl, osControl })
              onGranted()
              onOpenChange(false)
            }}
          >
            Разрешить и включить
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
