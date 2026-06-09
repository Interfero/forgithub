import { motherCoreChip, StatusChip } from '@/lib/statusIndicators'
import type { TelegramState } from '@/types'

interface DevPanelMotherCoreProps {
  telegram: TelegramState
}

/** Индикатор коннектора Telegram — дублирует настройки для панели разработчика. */
export function DevPanelMotherCore({ telegram }: DevPanelMotherCoreProps) {
  const mc = motherCoreChip(telegram)

  return (
    <div className="rounded-md border border-border/50 bg-background/40 p-2">
      <p className="mb-2 text-[9px] font-medium uppercase tracking-wider text-muted-foreground">
        Коннектор Телеграм
      </p>
      <div className="flex flex-wrap gap-2">
        <StatusChip
          label="Токен BotFather"
          hint={
            telegram.botTokenConfigured
              ? 'Токен сохранён в backend/data/telegram/config.json'
              : 'Токен не загружен — Настройки → Коннектор Телеграм → «Сохранить токен»'
          }
          value={telegram.botTokenConfigured ? 'Загружен' : 'Требуется'}
          variant={telegram.botTokenConfigured ? 'success' : 'warning'}
          icon={mc.icon}
        />
        <StatusChip
          label="Сервер бота"
          hint={mc.hint}
          value={mc.value}
          variant={mc.variant}
          icon={mc.icon}
        />
        <StatusChip
          label="Логика JSON"
          hint={
            telegram.botLogicConfigured
              ? `Файл bot_logic.json: ${telegram.botLogicName ?? 'настроен'}`
              : 'Сохраните bot_logic.json в Коннекторе Телеграм (кнопка «Сохранить логику»)'
          }
          value={telegram.botLogicConfigured ? 'На диске' : 'Нет файла'}
          variant={telegram.botLogicConfigured ? 'success' : 'muted'}
        />
      </div>
      {telegram.lastEvent && (
        <p className="mt-2 truncate text-[9px] text-muted-foreground" title={telegram.lastEvent}>
          {telegram.lastEvent}
        </p>
      )}
      {telegram.error && (
        <p className="mt-1 text-[9px] text-destructive">{telegram.error}</p>
      )}
    </div>
  )
}
