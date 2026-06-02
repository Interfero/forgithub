/** US QWERTY ↔ русская ЙЦУКЕН (по позициям клавиш). */
const EN_KEYS = '`qwertyuiop[]asdfghjkl;\'zxcvbnm,./'
const RU_KEYS = 'ёйцукенгшщзхъфывапролджэячсмитьбю.'

const enToRuMap = new Map<string, string>()
const ruToEnMap = new Map<string, string>()
for (let i = 0; i < EN_KEYS.length; i++) {
  enToRuMap.set(EN_KEYS[i], RU_KEYS[i])
  ruToEnMap.set(RU_KEYS[i], EN_KEYS[i])
}

/** Транслит RU↔LAT: «апи» ↔ «api». */
const RU_TO_LAT: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'j', з: 'z', и: 'i', й: 'j',
  к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f',
  х: 'h', ц: 'c', ч: 'c', ш: 's', щ: 's', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'u', я: 'a',
}

const LAT_TO_RU: Record<string, string> = {
  a: 'а', b: 'б', c: 'к', d: 'д', e: 'е', f: 'ф', g: 'г', h: 'х', i: 'и', j: 'ж', k: 'к',
  l: 'л', m: 'м', n: 'н', o: 'о', p: 'п', q: 'к', r: 'р', s: 'с', t: 'т', u: 'у', v: 'в',
  w: 'в', x: 'кс', y: 'ы', z: 'з',
}

export function normSearchText(s: string): string {
  return s
    .toLowerCase()
    .replace(/ё/g, 'е')
    .trim()
}

export function enToRuLayout(text: string): string {
  return [...text].map((ch) => enToRuMap.get(ch) ?? ch).join('')
}

export function ruToEnLayout(text: string): string {
  return [...text].map((ch) => ruToEnMap.get(ch) ?? ch).join('')
}

export function ruToLatinPhonetic(text: string): string {
  return [...normSearchText(text)].map((ch) => RU_TO_LAT[ch] ?? ch).join('')
}

export function latinToRuPhonetic(text: string): string {
  return [...normSearchText(text)].map((ch) => LAT_TO_RU[ch] ?? ch).join('')
}

/** Варианты запроса: раскладка + транслит RU↔LAT. */
export function searchQueryVariants(query: string): string[] {
  const base = normSearchText(query)
  if (!base) return []
  const variants = new Set<string>([
    base,
    normSearchText(enToRuLayout(base)),
    normSearchText(ruToEnLayout(base)),
    normSearchText(ruToLatinPhonetic(base)),
    normSearchText(latinToRuPhonetic(base)),
  ])
  return [...variants].filter((v) => v.length > 0)
}

export function textMatchesSearchQuery(haystack: string, query: string): boolean {
  const h = normSearchText(haystack)
  if (!h) return false
  for (const variant of searchQueryVariants(query)) {
    if (variant.length < 1) continue
    if (h.includes(variant) || variant.includes(h)) return true
  }
  return false
}
