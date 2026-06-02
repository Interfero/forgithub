import type { SettingsFocusSection } from '@/lib/uiBridge'
import { textMatchesSearchQuery } from '@/lib/keyboardLayout'

/** Каталог меню синхронизируется в jarvis.db → backend/modules/menu_search.py */

export type SettingsBlockId =
  | 'core'
  | 'appearance'
  | 'api-modes'
  | 'voice'
  | 'telephony'
  | 'mail'
  | 'telegram'
  | 'avito'

export interface SettingsMenuItem {
  id: string
  blockId: SettingsBlockId | null
  sectionDomId: string
  label: string
  path: string[]
  keywords: string[]
  isBlock?: boolean
}

export interface SettingsNavChild {
  label: string
  sectionDomId: string
  focus?: SettingsFocusSection
  keywords: string[]
}

export interface SettingsNavGroup {
  blockId: SettingsBlockId
  label: string
  sectionDomId: string
  keywords: string[]
  children: SettingsNavChild[]
}

export const SETTINGS_NAV_GROUPS: SettingsNavGroup[] = [
  {
    blockId: 'appearance',
    label: 'Оформление',
    sectionDomId: 'settings-block-appearance',
    keywords: ['тема', 'светлая', 'тёмная', 'оформление'],
    children: [],
  },
  {
    blockId: 'core',
    label: 'Ядро Jarvis',
    sectionDomId: 'settings-block-core',
    keywords: ['ядро', 'jarvis', 'стандарт'],
    children: [
      {
        label: 'Qwen 2.5 14B',
        sectionDomId: 'settings-section-qwen',
        focus: 'qwen',
        keywords: ['qwen', 'озу', 'ram', 'локаль', 'нейросеть', 'gguf'],
      },
      {
        label: 'DeepSeek',
        sectionDomId: 'settings-section-deepseek',
        focus: 'deepseek',
        keywords: ['deepseek', 'sk-', 'бухгалтер', 'облако'],
      },
      {
        label: 'Chromium (браузер)',
        sectionDomId: 'settings-block-core',
        keywords: [
          'chromium',
          'хромиум',
          'браузер',
          'playwright',
          'fetch_url',
          'install-chromium',
          'страниц',
        ],
      },
    ],
  },
  {
    blockId: 'api-modes',
    label: 'API для режимов',
    sectionDomId: 'settings-block-api-modes',
    keywords: ['api', 'ключ', 'режим'],
    children: [
      {
        label: 'Perplexity',
        sectionDomId: 'settings-section-perplexity',
        focus: 'perplexity',
        keywords: ['perplexity', 'pplx', 'разработчик', 'код'],
      },
      {
        label: 'Ideogram',
        sectionDomId: 'settings-section-ideogram',
        focus: 'ideogram',
        keywords: ['ideogram', 'ideogram.ai', 'картин', 'логотип', 'баннер'],
      },
      {
        label: 'Nano Banana',
        sectionDomId: 'settings-section-nanobanana',
        focus: 'nanobanana',
        keywords: ['nano', 'banana', 'google', 'картин', 'маркетолог', 'aiza'],
      },
      {
        label: 'OpenAI',
        sectionDomId: 'settings-section-openai',
        keywords: ['openai', 'chatgpt', 'gpt'],
      },
      {
        label: 'Grok (xAI)',
        sectionDomId: 'settings-section-xai',
        keywords: ['grok', 'xai'],
      },
    ],
  },
  {
    blockId: 'voice',
    label: 'Голос и озвучка',
    sectionDomId: 'settings-block-voice',
    keywords: ['голос', 'озвучка', 'студия'],
    children: [
      {
        label: 'XTTS-v2',
        sectionDomId: 'settings-section-xtts',
        keywords: ['xtts', 'клон', 'кощей', 'edge-tts'],
      },
    ],
  },
  {
    blockId: 'telephony',
    label: 'Телефония',
    sectionDomId: 'settings-block-telephony',
    keywords: ['телефон', 'атс', 'mango', 'zadarma', 'звонок'],
    children: [],
  },
  {
    blockId: 'mail',
    label: 'Почтовый клиент',
    sectionDomId: 'settings-block-mail',
    keywords: ['почта', 'email', 'imap', 'gmail', 'ящик', 'письм'],
    children: [],
  },
  {
    blockId: 'telegram',
    label: 'Коннектор Телеграм',
    sectionDomId: 'settings-block-telegram',
    keywords: ['telegram', 'телеграм', 'бот'],
    children: [
      {
        label: 'Telegram-бот',
        sectionDomId: 'settings-section-telegram',
        focus: 'telegram',
        keywords: ['botfather', 'токен', 'прокси', 'bot_logic'],
      },
    ],
  },
  {
    blockId: 'avito',
    label: 'Коннектор Авито',
    sectionDomId: 'settings-block-avito',
    keywords: ['авито', 'avito', 'oauth'],
    children: [
      {
        label: 'Авито API',
        sectionDomId: 'settings-section-avito',
        focus: 'avito',
        keywords: ['client id', 'secret', 'синхрон'],
      },
    ],
  },
]

function norm(s: string): string {
  return s.toLowerCase().replace(/ё/g, 'е').trim()
}

export function flattenSettingsMenuItems(): SettingsMenuItem[] {
  const items: SettingsMenuItem[] = [
    {
      id: 'settings-root',
      blockId: null,
      sectionDomId: 'settings-dialog-root',
      label: 'Настройки',
      path: ['Приложение'],
      keywords: ['настройки', 'settings', 'параметры', 'меню'],
    },
  ]

  for (const g of SETTINGS_NAV_GROUPS) {
    items.push({
      id: g.blockId,
      blockId: g.blockId,
      sectionDomId: g.sectionDomId,
      label: g.label,
      path: ['Настройки', g.label],
      keywords: [g.label, ...g.keywords, ...g.children.flatMap((c) => c.keywords)],
      isBlock: true,
    })
    for (const c of g.children) {
      items.push({
        id: c.sectionDomId,
        blockId: g.blockId,
        sectionDomId: c.sectionDomId,
        label: c.label,
        path: ['Настройки', g.label, c.label],
        keywords: [...c.keywords, c.label, g.label],
      })
    }
  }

  return items
}

export function itemMatchesQuery(item: SettingsMenuItem, query: string): boolean {
  if (!query.trim()) return true
  if (textMatchesSearchQuery(item.label, query)) return true
  if (item.path.some((p) => textMatchesSearchQuery(p, query))) return true
  return item.keywords.some((k) => textMatchesSearchQuery(k, query))
}

/** Пункты для дерева и глобального поиска (без корня «Настройки»). */
export function filterSettingsMenu(query: string): SettingsMenuItem[] {
  const all = flattenSettingsMenuItems().filter((i) => i.id !== 'settings-root')
  const q = query.trim()
  if (!q) return all

  const matched = all.filter((i) => itemMatchesQuery(i, q))
  const blockIds = new Set<SettingsBlockId>()
  for (const m of matched) {
    if (m.blockId) blockIds.add(m.blockId)
  }
  return all.filter(
    (i) =>
      matched.some((m) => m.sectionDomId === i.sectionDomId) ||
      (i.isBlock && blockIds.has(i.blockId!)),
  )
}

export function blockVisibleInSearch(
  blockId: SettingsBlockId,
  query: string,
  dbVisibleBlockIds?: SettingsBlockId[] | null,
): boolean {
  if (!query.trim()) return true
  if (dbVisibleBlockIds != null) {
    return dbVisibleBlockIds.includes(blockId)
  }
  return filterSettingsMenu(query).some((i) => i.blockId === blockId && i.isBlock)
}

export function focusSectionToBlockId(
  section: SettingsFocusSection | null | undefined,
): SettingsBlockId | null {
  if (!section || section === 'general') return null
  for (const g of SETTINGS_NAV_GROUPS) {
    if (g.children.some((c) => c.focus === section)) return g.blockId
  }
  const map: Partial<Record<SettingsFocusSection, SettingsBlockId>> = {
    qwen: 'core',
    deepseek: 'core',
    perplexity: 'api-modes',
    ideogram: 'api-modes',
    nanobanana: 'api-modes',
    telegram: 'telegram',
    avito: 'avito',
  }
  return map[section] ?? null
}

export function blockIdForSectionDomId(sectionDomId: string): SettingsBlockId | null {
  for (const g of SETTINGS_NAV_GROUPS) {
    if (g.sectionDomId === sectionDomId) return g.blockId
    if (g.children.some((c) => c.sectionDomId === sectionDomId)) return g.blockId
  }
  return null
}

export function sectionDomIdForFocus(
  section: SettingsFocusSection | null | undefined,
): string | null {
  if (!section || section === 'general') return null
  for (const g of SETTINGS_NAV_GROUPS) {
    const child = g.children.find((c) => c.focus === section)
    if (child) return child.sectionDomId
  }
  return `settings-section-${section}`
}
