import { Settings } from 'lucide-react'
import { MenuSearch } from '@/components/menu/MenuSearch'
import { Hint } from '@/components/ui/hint'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import type { MenuNavigatePayload } from '@/components/sidebar/Sidebar'

interface SidebarFreeProps {
  onOpenSettings: () => void
  onMenuNavigate: (payload: MenuNavigatePayload) => void
}

/** Боковая панель Jarvis Free — меню и настройки, без экрана-аватара. */
export function SidebarFree({ onOpenSettings, onMenuNavigate }: SidebarFreeProps) {
  return (
    <aside className="flex w-[240px] shrink-0 flex-col border-r border-border bg-sidebar">
      <div className="border-b border-border px-3 py-3">
        <p className="text-sm font-semibold">Jarvis Free</p>
        <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
          Весь функционал — в чате справа: Jarvis сам подбирает инструменты под задачу.
        </p>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3 px-3 py-4">
        <MenuSearch onNavigate={onMenuNavigate} />
        <p className="text-xs leading-relaxed text-muted-foreground">
          DeepSeek встроен для друзей. Qwen и браузеры — общие с полной версией Jarvis
          (не нужно скачивать повторно).
        </p>
      </div>

      <Separator />

      <div className="p-3">
        <Hint text="Параметры и ключи дополнительных сервисов">
          <Button
            variant="ghost"
            className="w-full justify-start gap-2"
            size="sm"
            onClick={onOpenSettings}
          >
            <Settings className="h-4 w-4" />
            Настройки
          </Button>
        </Hint>
      </div>
    </aside>
  )
}
