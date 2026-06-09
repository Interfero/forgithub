import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { SettingsFocusSection } from '@/lib/uiBridge'
import { Moon, Search, Sun } from 'lucide-react'
import { SettingsCollapsibleBlock } from '@/components/settings/SettingsCollapsibleBlock'
import { SettingsNavTree } from '@/components/settings/SettingsNavTree'
import {
  blockIdForSectionDomId,
  focusSectionToBlockId,
  sectionDomIdForFocus,
  type SettingsBlockId,
} from '@/lib/settingsMenu'
import { useMenuSearch } from '@/hooks/useMenuSearch'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { SettingsVoiceSection } from '@/components/settings/SettingsVoiceSection'
import { SettingsTelephonySection } from '@/components/settings/SettingsTelephonySection'
import { SettingsMailSection } from '@/components/settings/SettingsMailSection'
import { HfSkillsPanel } from '@/components/settings/HfSkillsPanel'
import { AvitoConnectorPanel } from '@/components/sidebar/AvitoConnectorPanel'
import { TelegramConnectorPanel } from '@/components/sidebar/TelegramConnectorPanel'
import { QwenRamToggle } from '@/components/sidebar/QwenRamToggle'
import { Hint } from '@/components/ui/hint'
import { ServiceEnableToggle } from '@/components/ui/ServiceEnableToggle'
import { setServiceActive } from '@/api/client'
import { cn } from '@/lib/utils'
import type {
  AgentState,
  AppSettings,
  AvitoConfig,
  TelegramConfig,
  VoiceSlot,
  XttsStatus,
} from '@/types'
import type { Theme } from '@/hooks/useTheme'

interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  focusSection?: SettingsFocusSection | null
  settings: AppSettings
  theme: Theme
  agent: AgentState
  voiceSlots: VoiceSlot[]
  xtts: XttsStatus
  onChange: (s: AppSettings) => void
  onSave: () => void | Promise<void>
  saveState?: 'idle' | 'saving' | 'ok' | 'error'
  onThemeChange: (theme: Theme) => void
  onVoiceSlotUpdate?: (slot: VoiceSlot) => void
  onVoiceRefresh?: () => void
  onXttsRefresh?: () => void
  onBaseVoiceUploaded?: () => void
  onMemoryChange?: () => void
  onSystemLog?: (text: string) => void
  telegramConfig: TelegramConfig | null
  avitoConfig: AvitoConfig | null
  tgLoading?: boolean
  avitoLoading?: boolean
  onToggleTelegram: () => void
  onToggleAvito: () => void
  onTelegramConfigSaved?: (cfg: TelegramConfig) => void
  onAvitoConfigSaved?: (cfg: AvitoConfig) => void
  backendConnected?: boolean
  onQwenRamChanged?: () => void
  searchQuery?: string
  onSearchQueryChange?: (q: string) => void
  scrollTargetDomId?: string | null
  onScrollTargetConsumed?: () => void
}

const EXPANDED_BLOCKS_STORAGE = 'jarvis-settings-expanded-v2'

const ALL_BLOCK_IDS: SettingsBlockId[] = [
  'core',
  'appearance',
  'api-modes',
  'voice',
  'telephony',
  'mail',
  'hf',
  'telegram',
  'avito',
]

function loadExpandedBlocks(): Record<SettingsBlockId, boolean> {
  const defaults = Object.fromEntries(ALL_BLOCK_IDS.map((id) => [id, false])) as Record<
    SettingsBlockId,
    boolean
  >
  try {
    const raw = sessionStorage.getItem(EXPANDED_BLOCKS_STORAGE)
    if (!raw) return defaults
    return { ...defaults, ...JSON.parse(raw) }
  } catch {
    return defaults
  }
}

function ProviderCard({
  title,
  description,
  children,
  serviceToggle,
}: {
  title: string
  description?: string
  children: ReactNode
  serviceToggle?: ReactNode
}) {
  return (
    <div className="rounded-lg border border-border/80 bg-muted/15 p-3 shadow-sm">
      <div className="mb-2 border-b border-border/60 pb-2">
        <h4 className="text-sm font-medium text-foreground">{title}</h4>
        {description && (
          <p className="mt-0.5 text-[11px] text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="space-y-2.5">{children}</div>
      {serviceToggle && <div className="mt-3 border-t border-border/50 pt-3">{serviceToggle}</div>}
    </div>
  )
}

function TokenField({
  hint,
  placeholder,
  value,
  configured,
  onChange,
}: {
  hint: string
  placeholder: string
  value: string
  configured?: boolean
  onChange: (v: string) => void
}) {
  const showSaved = configured && !value.trim()
  return (
    <div>
      <label className="mb-1 block text-xs font-medium">API-токен</label>
      <Input
        type="password"
        placeholder={showSaved ? 'Ключ на сервере — введите новый, чтобы заменить' : placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="font-mono text-sm"
        spellCheck={false}
        autoComplete="off"
      />
      <p
        className={cn(
          'mt-1 text-[11px]',
          showSaved ? 'font-medium text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground',
        )}
      >
        {showSaved ? '✓ Токен сохранён на сервере' : hint}
      </p>
    </div>
  )
}

function ModelField({
  value,
  placeholder,
  onChange,
}: {
  value: string
  placeholder: string
  onChange: (v: string) => void
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium">Название модели</label>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="font-mono text-sm"
        spellCheck={false}
        autoComplete="off"
      />
    </div>
  )
}

export function SettingsDialog({
  open,
  onOpenChange,
  focusSection,
  settings,
  theme,
  agent,
  voiceSlots,
  xtts,
  onChange,
  onSave,
  saveState = 'idle',
  onThemeChange,
  onVoiceSlotUpdate,
  onVoiceRefresh,
  onXttsRefresh,
  onBaseVoiceUploaded,
  onMemoryChange,
  onSystemLog,
  telegramConfig,
  avitoConfig,
  tgLoading,
  avitoLoading,
  onToggleTelegram,
  onToggleAvito,
  onTelegramConfigSaved,
  onAvitoConfigSaved,
  backendConnected = true,
  onQwenRamChanged,
  searchQuery = '',
  onSearchQueryChange,
  scrollTargetDomId,
  onScrollTargetConsumed,
}: SettingsDialogProps) {
  const [saveFlash, setSaveFlash] = useState<string | null>(null)
  const [serviceBusy, setServiceBusy] = useState<string | null>(null)
  const [expandedBlocks, setExpandedBlocks] =
    useState<Record<SettingsBlockId, boolean>>(loadExpandedBlocks)
  const [activeSectionDomId, setActiveSectionDomId] = useState<string | null>(null)
  const [showTree, setShowTree] = useState(true)
  const { isBlockVisible, isSectionVisible } = useMenuSearch(searchQuery)

  const setBlockExpanded = useCallback((blockId: SettingsBlockId, open: boolean) => {
    setExpandedBlocks((prev) => {
      const next = { ...prev, [blockId]: open }
      try {
        sessionStorage.setItem(EXPANDED_BLOCKS_STORAGE, JSON.stringify(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }, [])

  const scrollToSection = useCallback(
    (sectionDomId: string, blockId: SettingsBlockId) => {
      setBlockExpanded(blockId, true)
      setActiveSectionDomId(sectionDomId)
      window.setTimeout(() => {
        document.getElementById(sectionDomId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 80)
    },
    [setBlockExpanded],
  )

  useEffect(() => {
    if (!searchQuery.trim()) return
    for (const id of ALL_BLOCK_IDS) {
      setBlockExpanded(id, isBlockVisible(id))
    }
  }, [searchQuery, setBlockExpanded, isBlockVisible])

  const toggleService = async (
    service: 'deepseek' | 'openai' | 'perplexity' | 'xai' | 'nanobanana' | 'ideogram' | 'xtts',
    enabled: boolean,
  ) => {
    setServiceBusy(service)
    try {
      const next = await setServiceActive(service, enabled)
      onChange(next)
      onXttsRefresh?.()
      onMemoryChange?.()
    } catch (e) {
      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'не удалось переключить сервис'}`)
    } finally {
      setServiceBusy(null)
    }
  }

  useEffect(() => {
    if (saveState === 'ok') {
      setSaveFlash('Настройки сохранены на сервере')
      const t = window.setTimeout(() => setSaveFlash(null), 4000)
      return () => window.clearTimeout(t)
    }
    if (saveState === 'error') {
      setSaveFlash('Не удалось сохранить — проверьте связь с сервером')
    }
  }, [saveState])

  useEffect(() => {
    if (!open || !focusSection || focusSection === 'general') return
    const domId = sectionDomIdForFocus(focusSection)
    const blockId = focusSectionToBlockId(focusSection)
    if (!domId || !blockId) return
    const t = window.setTimeout(() => scrollToSection(domId, blockId), 120)
    return () => window.clearTimeout(t)
  }, [open, focusSection, scrollToSection])

  useEffect(() => {
    if (!open || !scrollTargetDomId) return
    const domId = scrollTargetDomId
    const blockId = blockIdForSectionDomId(domId)
    const t = window.setTimeout(() => {
      if (blockId) scrollToSection(domId, blockId)
      else document.getElementById(domId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      onScrollTargetConsumed?.()
    }, 150)
    return () => window.clearTimeout(t)
  }, [open, scrollTargetDomId, scrollToSection, onScrollTargetConsumed])

  const blockProps = useMemo(
    () => ({
      core: {
        id: 'settings-block-core' as const,
        blockId: 'core' as const,
        title: 'Ядро Jarvis',
        description:
          'Стандартный чат: локальная Qwen в ОЗУ и облачный DeepSeek для сложных текстовых запросов.',
      },
      appearance: {
        id: 'settings-block-appearance' as const,
        blockId: 'appearance' as const,
        title: 'Оформление',
        description: 'Тема интерфейса Jarvis.',
      },
      apiModes: {
        id: 'settings-block-api-modes' as const,
        blockId: 'api-modes' as const,
        title: 'API для режимов чата',
        description: 'Ключи для специализированных режимов.',
      },
      voice: {
        id: 'settings-block-voice' as const,
        blockId: 'voice' as const,
        title: 'Голос и озвучка',
        description: 'Silero TTS v5 — выбор встроенного голоса озвучки.',
      },
      telephony: {
        id: 'settings-block-telephony' as const,
        blockId: 'telephony' as const,
        title: 'Телефония',
        description: 'Входящие звонки (Mango, Zadarma).',
      },
      mail: {
        id: 'settings-block-mail' as const,
        blockId: 'mail' as const,
        title: 'Почтовый клиент',
        description: 'Gmail, Яндекс, iCloud, Mail.ru и 1 слот legacy IMAP.',
      },
      hf: {
        id: 'settings-block-hf' as const,
        blockId: 'hf' as const,
        title: 'Навыки Hugging Face',
        description: 'Поиск на Hub, скачивание в data/hf_skills/, включение для агента.',
      },
      telegram: {
        id: 'settings-block-telegram' as const,
        blockId: 'telegram' as const,
        title: 'Коннектор Телеграм',
        description: 'BotFather-токен, прокси и bot_logic.json — быстрый сервер бота в Jarvis.',
      },
      avito: {
        id: 'settings-block-avito' as const,
        blockId: 'avito' as const,
        title: 'Коннектор Авито',
        description: 'OAuth2 — статистика и чаты.',
      },
    }),
    [],
  )

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'left-0 top-0 flex h-[100dvh] w-screen max-w-none translate-x-0 translate-y-0 flex-col',
          'rounded-none border-0 p-0 sm:rounded-none',
        )}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4 pr-14">
          <DialogHeader className="text-left">
            <DialogTitle>Настройки</DialogTitle>
            <DialogDescription className="text-xs">
              Оформление, ядро Jarvis, API по режимам, голос, телефония и коннекторы.
            </DialogDescription>
          </DialogHeader>
          <div className="flex shrink-0 flex-col items-end gap-1.5">
            {saveFlash && (
              <p
                className={cn(
                  'max-w-[220px] text-right text-[11px] font-medium',
                  saveState === 'error'
                    ? 'text-destructive'
                    : 'text-emerald-600 dark:text-emerald-400',
                )}
              >
                {saveFlash}
              </p>
            )}
            <Hint text="Сохранить ключи и модели на сервере">
              <button
                type="button"
                disabled={saveState === 'saving'}
                onClick={() => void onSave()}
                className={cn(
                  'shrink-0 rounded-md px-4 py-2 text-sm font-medium transition-colors',
                  saveState === 'ok'
                    ? 'bg-emerald-600 text-white hover:bg-emerald-600/90'
                    : 'bg-primary text-primary-foreground hover:bg-primary/90',
                  saveState === 'saving' && 'opacity-70',
                )}
              >
                {saveState === 'saving'
                  ? 'Сохранение…'
                  : saveState === 'ok'
                    ? 'Сохранено ✓'
                    : 'Сохранить'}
              </button>
            </Hint>
          </div>
        </div>

        <div
          id="settings-dialog-root"
          className="shrink-0 border-b border-border/60 bg-muted/20 px-5 py-3"
        >
          <label className="mb-1 block text-[10px] font-medium text-muted-foreground" htmlFor="settings-search">
            Поиск в настройках
          </label>
          <div className="flex max-w-xl items-center gap-2">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                id="settings-search"
                type="search"
                value={searchQuery}
                onChange={(e) => onSearchQueryChange?.(e.target.value)}
                placeholder="Название раздела, API, голос, Авито…"
                className="h-9 w-full rounded-md border border-input bg-background py-1 pl-8 pr-3 text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => setShowTree((v) => !v)}
              className="shrink-0 rounded-md border border-border px-2.5 py-1.5 text-[11px] text-muted-foreground hover:bg-muted/50 lg:hidden"
            >
              {showTree ? 'Скрыть дерево' : 'Дерево'}
            </button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          {showTree && (
            <aside className="max-h-40 shrink-0 overflow-y-auto border-b border-border/60 bg-muted/10 lg:max-h-none lg:w-52 lg:border-b-0 lg:border-r xl:w-56">
              <SettingsNavTree
                searchQuery={searchQuery}
                activeSectionDomId={activeSectionDomId}
                onSelect={scrollToSection}
                isSectionVisible={isSectionVisible}
                isBlockVisible={isBlockVisible}
              />
            </aside>
          )}

          <div className="min-h-0 min-w-0 flex-1 overflow-y-auto overscroll-y-contain px-5 py-4 [scrollbar-gutter:stable]">
            <div className="mx-auto flex max-w-6xl flex-col gap-4">
            <SettingsCollapsibleBlock
              id={blockProps.appearance.id}
              title={blockProps.appearance.title}
              description={blockProps.appearance.description}
              expanded={expandedBlocks.appearance}
              onExpandedChange={(on) => setBlockExpanded('appearance', on)}
              hidden={!isBlockVisible('appearance')}
            >
              <div className="flex max-w-md gap-2">
                <Hint text="Светлая цветовая схема интерфейса">
                  <button
                    type="button"
                    onClick={() => onThemeChange('light')}
                    className={cn(
                      'flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm',
                      theme === 'light'
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border hover:bg-muted/50',
                    )}
                  >
                    <Sun className="h-4 w-4" />
                    Светлая
                  </button>
                </Hint>
                <Hint text="Тёмная цветовая схема интерфейса">
                  <button
                    type="button"
                    onClick={() => onThemeChange('dark')}
                    className={cn(
                      'flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm',
                      theme === 'dark'
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border hover:bg-muted/50',
                    )}
                  >
                    <Moon className="h-4 w-4" />
                    Тёмная
                  </button>
                </Hint>
              </div>
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.core.id}
              title={blockProps.core.title}
              description={blockProps.core.description}
              expanded={expandedBlocks.core}
              onExpandedChange={(on) => setBlockExpanded('core', on)}
              hidden={!isBlockVisible('core')}
            >
              <div className="space-y-4">
                <QwenRamToggle
                  inSettings
                  qwen={agent.qwen}
                  disabled={!backendConnected}
                  onChanged={onQwenRamChanged}
                />
                {!backendConnected && (
                  <p className="text-[10px] text-amber-700/90 dark:text-amber-300/90">
                    Для скачивания модели нужен запущенный сервер: start.bat →{' '}
                    <strong>http://127.0.0.1:8000/</strong>
                  </p>
                )}
                <div id="settings-section-deepseek" className="scroll-mt-4 border-t border-border/50 pt-4">
                  <ProviderCard
                    title="DeepSeek"
                    description="Резерв для роутера и режима «Бухгалтер + Юрист». Только текст; картинки — Nano Banana в режиме «Маркетолог»."
                    serviceToggle={
                      <ServiceEnableToggle
                        label="Активный сервис DeepSeek"
                        description="Ключ остаётся на сервере; запросы к API не отправляются"
                        enabled={settings.deepseekActive ?? true}
                        ready
                        busy={serviceBusy === 'deepseek'}
                        onToggle={(on) => void toggleService('deepseek', on)}
                      />
                    }
                  >
                    <TokenField
                      placeholder="sk-…"
                      value={settings.deepseekKey}
                      configured={settings.deepseekConfigured}
                      hint="Ключ DeepSeek"
                      onChange={(v) => onChange({ ...settings, deepseekKey: v })}
                    />
                    <ModelField
                      value={settings.defaultModel}
                      placeholder="deepseek-chat"
                      onChange={(v) => onChange({ ...settings, defaultModel: v })}
                    />
                  </ProviderCard>
                </div>
              </div>
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.apiModes.id}
              title={blockProps.apiModes.title}
              description={blockProps.apiModes.description}
              expanded={expandedBlocks['api-modes']}
              onExpandedChange={(on) => setBlockExpanded('api-modes', on)}
              hidden={!isBlockVisible('api-modes')}
            >
              <div className="grid gap-4 lg:grid-cols-2">
                <div id="settings-section-perplexity" className="scroll-mt-4 space-y-3">
                  <ProviderCard
                    title="Perplexity"
                    description="Режим «Разработчик»: код, архитектура, поиск. Без pplx-… режим недоступен."
                    serviceToggle={
                      <ServiceEnableToggle
                        label="Активный сервис Perplexity"
                        enabled={settings.perplexityActive ?? false}
                        ready={settings.perplexityConfigured}
                        busy={serviceBusy === 'perplexity'}
                        onToggle={(on) => void toggleService('perplexity', on)}
                      />
                    }
                  >
                    <TokenField
                      placeholder="pplx-…"
                      value={settings.perplexityKey}
                      configured={settings.perplexityConfigured}
                      hint="Ключ pplx-…"
                      onChange={(v) => onChange({ ...settings, perplexityKey: v })}
                    />
                    <ModelField
                      value={settings.perplexityModel}
                      placeholder="sonar"
                      onChange={(v) => onChange({ ...settings, perplexityModel: v })}
                    />
                  </ProviderCard>
                </div>

                <div id="settings-section-ideogram" className="scroll-mt-4 space-y-3">
                  <Hint text="Ключ API на ideogram.ai — генерация изображений через медиа-роутер Jarvis">
                    <ProviderCard
                      title="Ideogram"
                      description="Генерация картинок (Ideogram 3.0). Роутер выберет Ideogram, если ключ активен."
                      serviceToggle={
                        <ServiceEnableToggle
                          label="Активный сервис Ideogram"
                          description="Картинки через api.ideogram.ai"
                          enabled={settings.ideogramActive ?? false}
                          ready={settings.ideogramConfigured}
                          busy={serviceBusy === 'ideogram'}
                          onToggle={(on) => void toggleService('ideogram', on)}
                        />
                      }
                    >
                      <TokenField
                        placeholder="Api-Key…"
                        value={settings.ideogramKey}
                        configured={settings.ideogramConfigured}
                        hint="Ключ из ideogram.ai → API"
                        onChange={(v) => onChange({ ...settings, ideogramKey: v })}
                      />
                    </ProviderCard>
                  </Hint>
                </div>

                <div id="settings-section-nanobanana" className="scroll-mt-4 space-y-3">
                  <Hint text="Обязателен для режима «Маркетолог+Дизайнер». aistudio.google.com/apikey">
                    <ProviderCard
                      title="Google Nano Banana"
                      description="Режим «Маркетолог+Дизайнер» — только генерация изображений."
                      serviceToggle={
                        <ServiceEnableToggle
                          label="Активный сервис Nano Banana"
                          description="Генерация изображений в режиме «Маркетолог»"
                          enabled={settings.nanobananaActive ?? false}
                          ready={settings.nanobananaConfigured}
                          busy={serviceBusy === 'nanobanana'}
                          onToggle={(on) => void toggleService('nanobanana', on)}
                        />
                      }
                    >
                      <TokenField
                        placeholder="AIza…"
                        value={settings.nanobananaKey}
                        configured={settings.nanobananaConfigured}
                        hint="Вставьте ключ Google AI Studio"
                        onChange={(v) => onChange({ ...settings, nanobananaKey: v })}
                      />
                    </ProviderCard>
                  </Hint>
                </div>
              </div>

              <div className="mt-4 border-t border-border/50 pt-4">
                <p className="mb-3 text-[11px] font-medium text-muted-foreground">Дополнительные API</p>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div id="settings-section-openai" className="scroll-mt-4">
                  <ProviderCard
                    title="ChatGPT (OpenAI)"
                    serviceToggle={
                      <ServiceEnableToggle
                        label="Активный сервис OpenAI"
                        enabled={settings.openaiActive ?? false}
                        ready={settings.openaiConfigured}
                        busy={serviceBusy === 'openai'}
                        onToggle={(on) => void toggleService('openai', on)}
                      />
                    }
                  >
                    <TokenField
                      placeholder="sk-…"
                      value={settings.openaiKey}
                      configured={settings.openaiConfigured}
                      hint="Ключ OpenAI"
                      onChange={(v) => onChange({ ...settings, openaiKey: v })}
                    />
                    <ModelField
                      value={settings.openaiModel}
                      placeholder="gpt-5.5-instant"
                      onChange={(v) => onChange({ ...settings, openaiModel: v })}
                    />
                  </ProviderCard>
                  </div>

                  <div id="settings-section-xai" className="scroll-mt-4">
                  <ProviderCard
                    title="Grok (xAI)"
                    serviceToggle={
                      <ServiceEnableToggle
                        label="Активный сервис xAI"
                        enabled={settings.xaiActive ?? false}
                        ready={settings.xaiConfigured}
                        busy={serviceBusy === 'xai'}
                        onToggle={(on) => void toggleService('xai', on)}
                      />
                    }
                  >
                    <TokenField
                      placeholder="xai-…"
                      value={settings.xaiKey}
                      configured={settings.xaiConfigured}
                      hint="Ключ xAI"
                      onChange={(v) => onChange({ ...settings, xaiKey: v })}
                    />
                    <ModelField
                      value={settings.xaiModel}
                      placeholder="grok-4.20"
                      onChange={(v) => onChange({ ...settings, xaiModel: v })}
                    />
                  </ProviderCard>
                  </div>
                </div>
              </div>
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.voice.id}
              title={blockProps.voice.title}
              description={blockProps.voice.description}
              expanded={expandedBlocks.voice}
              onExpandedChange={(on) => setBlockExpanded('voice', on)}
              hidden={!isBlockVisible('voice')}
            >
              <SettingsVoiceSection
                silero={xtts}
                onSileroRefresh={() => onXttsRefresh?.()}
                onSystemLog={onSystemLog}
              />
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.telephony.id}
              title={blockProps.telephony.title}
              description={blockProps.telephony.description}
              expanded={expandedBlocks.telephony}
              onExpandedChange={(on) => setBlockExpanded('telephony', on)}
              hidden={!isBlockVisible('telephony')}
            >
              <div id="settings-section-telephony" className="scroll-mt-4">
                <SettingsTelephonySection onSystemLog={onSystemLog} onRefresh={onXttsRefresh} />
              </div>
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.mail.id}
              title={blockProps.mail.title}
              description={blockProps.mail.description}
              expanded={expandedBlocks.mail}
              onExpandedChange={(on) => setBlockExpanded('mail', on)}
              hidden={!isBlockVisible('mail')}
            >
              <div id="settings-section-mail" className="scroll-mt-4">
                <SettingsMailSection onSystemLog={onSystemLog} onRefresh={onXttsRefresh} />
              </div>
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.hf.id}
              title={blockProps.hf.title}
              description={blockProps.hf.description}
              expanded={expandedBlocks.hf}
              onExpandedChange={(on) => setBlockExpanded('hf', on)}
              hidden={!isBlockVisible('hf')}
            >
              <div id="settings-section-hf" className="scroll-mt-4">
                <HfSkillsPanel onSystemLog={onSystemLog} />
              </div>
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.telegram.id}
              title={blockProps.telegram.title}
              description={blockProps.telegram.description}
              expanded={expandedBlocks.telegram}
              onExpandedChange={(on) => setBlockExpanded('telegram', on)}
              hidden={!isBlockVisible('telegram')}
            >
              <TelegramConnectorPanel
                inSettings
                telegram={agent.telegram}
                config={telegramConfig}
                tgLoading={tgLoading}
                onToggle={onToggleTelegram}
                onConfigSaved={onTelegramConfigSaved}
                onSystemLog={onSystemLog}
              />
            </SettingsCollapsibleBlock>

            <SettingsCollapsibleBlock
              id={blockProps.avito.id}
              title={blockProps.avito.title}
              description={blockProps.avito.description}
              expanded={expandedBlocks.avito}
              onExpandedChange={(on) => setBlockExpanded('avito', on)}
              hidden={!isBlockVisible('avito')}
            >
              <AvitoConnectorPanel
                inSettings
                avito={agent.avito}
                config={avitoConfig}
                avitoLoading={avitoLoading}
                onToggle={onToggleAvito}
                onConfigSaved={onAvitoConfigSaved}
                onSystemLog={onSystemLog}
              />
            </SettingsCollapsibleBlock>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
