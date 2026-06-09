import { Save, Trash2, Volume2 } from 'lucide-react'

import { useCallback, useEffect, useRef, useState } from 'react'

import { DownloadActionButton } from '@/components/ui/DownloadActionButton'

import { DownloadProgress } from '@/components/ui/DownloadProgress'

import { Button } from '@/components/ui/button'

import { Hint } from '@/components/ui/hint'

import { useDownloadPoll } from '@/hooks/useDownloadPoll'

import {

  deleteSileroStressEntry,

  fetchSileroSpeakers,

  fetchSileroStatus,

  fetchSileroStressLexicon,

  previewSileroSpeaker,

  saveSileroStressLexicon,

  saveSileroVoiceSettings,

  startSileroInstall,

  type SileroStressEntry,

  type SileroVoice,

} from '@/api/client'

import { cn } from '@/lib/utils'

import type { XttsStatus } from '@/types'



interface SettingsVoiceSectionProps {

  silero: XttsStatus

  onSileroRefresh: () => void

  onSystemLog?: (text: string) => void

}



export function SettingsVoiceSection({

  silero,

  onSileroRefresh,

  onSystemLog,

}: SettingsVoiceSectionProps) {

  const [status, setStatus] = useState(silero)

  const [voices, setVoices] = useState<SileroVoice[]>([])

  const [selected, setSelected] = useState('aidar')

  const [savedSpeaker, setSavedSpeaker] = useState('aidar')

  const [tempo, setTempo] = useState(1.0)

  const [savedTempo, setSavedTempo] = useState(1.0)

  const [tempoMin, setTempoMin] = useState(0.75)

  const [tempoMax, setTempoMax] = useState(1.5)

  const [model, setModel] = useState('v5_ru')

  const [installing, setInstalling] = useState(false)

  const [saving, setSaving] = useState(false)

  const [previewing, setPreviewing] = useState<string | null>(null)

  const previewAudioRef = useRef<HTMLAudioElement | null>(null)



  const [stressInput, setStressInput] = useState('')

  const [stressEntries, setStressEntries] = useState<SileroStressEntry[]>([])

  const [stressSaving, setStressSaving] = useState(false)

  const [stressFlags, setStressFlags] = useState<Record<string, boolean>>({})



  const dirty = selected !== savedSpeaker || Math.abs(tempo - savedTempo) > 0.01



  useEffect(() => {

    setStatus(silero)

    const busy = silero.status === 'installing_deps' || silero.status === 'downloading_model'

    if (busy) setInstalling(true)

  }, [silero])



  const loadStressLexicon = useCallback(() => {

    fetchSileroStressLexicon()

      .then((data) => {

        setStressEntries(data.entries)

        setStressFlags(data.stress_flags ?? {})

      })

      .catch(() => {})

  }, [])



  const loadSpeakers = useCallback(() => {

    fetchSileroSpeakers()

      .then((cfg) => {

        setVoices(cfg.voices)

        setSelected(cfg.selected)

        setSavedSpeaker(cfg.selected)

        setTempo(cfg.tempo)

        setSavedTempo(cfg.tempo)

        setTempoMin(cfg.tempo_min)

        setTempoMax(cfg.tempo_max)

        setModel(cfg.model)

      })

      .catch(() => {})

    loadStressLexicon()

  }, [loadStressLexicon])



  useEffect(() => {

    loadSpeakers()

  }, [loadSpeakers])



  const pollStatus = useCallback(async () => {

    const s = await fetchSileroStatus()

    setStatus(s)

    onSileroRefresh()

    return s

  }, [onSileroRefresh])



  useDownloadPoll(installing, pollStatus, 1000)



  const isReady = status.status === 'ready' || status.importable

  const isBusy =

    status.status === 'installing_deps' || status.status === 'downloading_model' || installing



  const saveSettings = async () => {

    setSaving(true)

    try {

      const cfg = await saveSileroVoiceSettings(selected, tempo)

      setSelected(cfg.selected)

      setSavedSpeaker(cfg.selected)

      setTempo(cfg.tempo)

      setSavedTempo(cfg.tempo)

      onSystemLog?.(`✅ Голос ${cfg.selected}, темп ${cfg.tempo}× сохранены`)

      onSileroRefresh()

    } catch (e) {

      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'не удалось сохранить'}`)

    } finally {

      setSaving(false)

    }

  }



  const saveStress = async () => {

    const lines = stressInput.trim()

    if (!lines.includes('+')) {

      onSystemLog?.('❌ Поставьте «+» перед ударной гласной, например: на св+язи')

      return

    }

    setStressSaving(true)

    try {

      const { entries } = await saveSileroStressLexicon(lines)

      setStressEntries(entries)

      setStressInput('')

      onSystemLog?.(`✅ Ударения сохранены (${entries.length} фраз)`)

    } catch (e) {

      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'не удалось сохранить ударения'}`)

    } finally {

      setStressSaving(false)

    }

  }



  const removeStress = async (plain: string) => {

    try {

      const { entries } = await deleteSileroStressEntry(plain)

      setStressEntries(entries)

      onSystemLog?.(`🗑 Удалено: «${plain}»`)

    } catch (e) {

      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка удаления'}`)

    }

  }



  const installSilero = async () => {

    if (installing || isReady) return

    setInstalling(true)

    onSystemLog?.('📥 Установка Silero TTS (torch + модель v5_ru)…')

    try {

      await startSileroInstall()

      const deadline = Date.now() + 30 * 60 * 1000

      const interval = setInterval(async () => {

        const st = await pollStatus()

        if (st.status === 'ready' || st.importable) {

          onSystemLog?.('✅ Silero TTS установлен')

          clearInterval(interval)

          setInstalling(false)

        } else if (st.status === 'error') {

          onSystemLog?.(`❌ Silero: ${st.error ?? st.message}`)

          clearInterval(interval)

          setInstalling(false)

        } else if (Date.now() > deadline) {

          onSystemLog?.('⚠️ Превышено время ожидания установки Silero')

          clearInterval(interval)

          setInstalling(false)

        }

      }, 1500)

    } catch (e) {

      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'ошибка установки'}`)

      setInstalling(false)

    }

  }



  const previewVoice = async (speakerId: string) => {

    if (previewAudioRef.current) {

      previewAudioRef.current.pause()

      previewAudioRef.current = null

    }

    if (previewing === speakerId) {

      setPreviewing(null)

      return

    }

    setPreviewing(speakerId)

    try {

      const url = await previewSileroSpeaker(speakerId, tempo)

      const audio = new Audio(url)

      previewAudioRef.current = audio

      audio.onended = () => setPreviewing(null)

      audio.onerror = () => setPreviewing(null)

      await audio.play()

    } catch (e) {

      onSystemLog?.(`❌ ${e instanceof Error ? e.message : 'прослушивание не удалось'}`)

      setPreviewing(null)

    }

  }



  const flagsOk =

    stressFlags.put_accent &&

    stressFlags.put_yo &&

    stressFlags.put_stress_homo &&

    stressFlags.put_yo_homo



  return (

    <div id="settings-section-voice" className="space-y-4 scroll-mt-4">

      <p className="text-[11px] leading-relaxed text-muted-foreground">

        Озвучка — <strong className="text-foreground">Silero TTS {model}</strong>

        {flagsOk ? (

          <>

            {' '}

            · автоударения включены (put_accent, put_yo, put_stress_homo, put_yo_homo)

          </>

        ) : (

          <> · проверьте флаги ударений в backend</>

        )}

        . Ссылки не зачитываются; числа — словами.

      </p>



      {!isReady && (

        <div className="rounded-lg border border-border/80 bg-muted/15 p-3 space-y-2">

          <h4 className="text-sm font-medium">Установка Silero</h4>

          <p className="text-[11px] text-muted-foreground">

            Модель сохраняется в <strong>backend/data/silero</strong>.

          </p>

          {isBusy && (

            <DownloadProgress

              className="max-w-md"

              percent={status.progress}

              indeterminate={status.progress <= 0}

              message={status.message || 'Установка Silero…'}

            />

          )}

          <DownloadActionButton

            className="max-w-xs"

            label={isReady ? 'Установлено' : 'Установить Silero'}

            activeLabel="Установка…"

            loading={isBusy}

            active={isBusy}

            disabled={isBusy || isReady}

            onClick={() => void installSilero()}

          />

        </div>

      )}



      {isReady && (

        <p className="text-[11px] text-emerald-600 dark:text-emerald-400">

          ✓ Silero {model} готов · сохранено: {savedSpeaker}, темп {savedTempo}×

        </p>

      )}



      <div className="grid gap-4 lg:grid-cols-[minmax(240px,1fr)_minmax(280px,1.35fr)]">

        {/* Слева — словарь ударений */}

        <div className="rounded-lg border border-border/60 bg-muted/10 p-3 space-y-3">

          <Hint text="Silero понимает «+» перед ударной гласной. Фраза из словаря подставляется при озвучке.">

            <h4 className="text-sm font-medium">Ударения Silero</h4>

          </Hint>

          <p className="text-[10px] text-muted-foreground leading-relaxed">

            Пример: <code className="text-foreground">на св+язи</code> — ударение на «я», не на

            последний слог. Одна фраза на строку.

          </p>

          <textarea

            value={stressInput}

            onChange={(e) => setStressInput(e.target.value)}

            placeholder={'на св+язи\nкат+алог'}

            rows={4}

            className="w-full resize-y rounded-md border border-border/70 bg-background/80 px-2 py-1.5 font-mono text-[11px] leading-relaxed focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40"

          />

          <Hint text="Сохранить фразы с «+» в словарь озвучки Jarvis">

            <Button

              type="button"

              size="sm"

              disabled={stressSaving || !stressInput.trim()}

              onClick={() => void saveStress()}

              className="w-full transition-all hover:brightness-110 active:scale-[0.99]"

            >

              <Save className={cn('mr-2 h-3.5 w-3.5', stressSaving && 'animate-pulse')} />

              {stressSaving ? 'Сохранение…' : 'Сохранить'}

            </Button>

          </Hint>

          <div className="space-y-1 max-h-[140px] overflow-y-auto">

            {stressEntries.length === 0 ? (

              <p className="text-[10px] italic text-muted-foreground">Словарь пуст</p>

            ) : (

              stressEntries.map((e) => (

                <div

                  key={e.plain}

                  className="flex items-center justify-between gap-1 rounded bg-muted/40 px-2 py-1 text-[10px]"

                >

                  <span className="truncate font-mono" title={e.marked}>

                    {e.marked}

                  </span>

                  <Hint text={`Удалить «${e.plain}»`}>

                    <button

                      type="button"

                      className="shrink-0 text-destructive transition-colors hover:text-destructive/80"

                      onClick={() => void removeStress(e.plain)}

                    >

                      <Trash2 className="h-3 w-3" />

                    </button>

                  </Hint>

                </div>

              ))

            )}

          </div>

        </div>



        {/* Справа — голос и темп */}

        <div className="space-y-4">

          <div className="space-y-2">

            <h4 className="text-sm font-medium">Голос озвучки</h4>

            <div className="grid gap-2 sm:grid-cols-2">

              {voices.map((voice) => {

                const active = selected === voice.id

                return (

                  <div

                    key={voice.id}

                    className={cn(

                      'rounded-lg border p-3 transition-all',

                      active

                        ? 'border-primary bg-primary/10 shadow-sm'

                        : 'border-border/60 bg-muted/10 hover:border-primary/40',

                    )}

                  >

                    <div className="flex items-start justify-between gap-2">

                      <button

                        type="button"

                        className="text-left"

                        onClick={() => setSelected(voice.id)}

                      >

                        <Hint text={`Выбрать голос ${voice.label}`}>

                          <span className="text-sm font-medium">{voice.label}</span>

                        </Hint>

                        <p className="mt-0.5 text-[10px] text-muted-foreground">

                          {voice.description}

                        </p>

                      </button>

                      <Hint text="Прослушать с текущим темпом">

                        <Button

                          type="button"

                          size="sm"

                          variant="outline"

                          className="h-7 w-7 shrink-0 p-0 transition-all hover:border-primary/50 active:scale-95"

                          onClick={() => void previewVoice(voice.id)}

                        >

                          <Volume2

                            className={cn(

                              'h-3.5 w-3.5',

                              previewing === voice.id && 'animate-pulse text-primary',

                            )}

                          />

                        </Button>

                      </Hint>

                    </div>

                  </div>

                )

              })}

            </div>

          </div>



          <div className="rounded-lg border border-border/60 bg-muted/10 p-3 space-y-3">

            <div className="flex items-center justify-between gap-2">

              <Hint text="Скорость речи: меньше — медленнее, больше — быстрее">

                <h4 className="text-sm font-medium">Темп речи</h4>

              </Hint>

              <span className="text-sm font-semibold tabular-nums text-primary">

                {tempo.toFixed(2)}×

              </span>

            </div>

            <input

              type="range"

              min={tempoMin}

              max={tempoMax}

              step={0.05}

              value={tempo}

              onChange={(e) => setTempo(Number(e.target.value))}

              className="h-2 w-full cursor-pointer accent-primary"

            />

            <div className="flex justify-between text-[10px] text-muted-foreground">

              <span>{tempoMin}× медленнее</span>

              <span>1.00×</span>

              <span>{tempoMax}× быстрее</span>

            </div>

          </div>



          <Hint text="Сохранить выбранный голос и темп для всех ответов Jarvis">

            <Button

              type="button"

              disabled={!dirty || saving}

              onClick={() => void saveSettings()}

              className="w-full transition-all hover:brightness-110 active:scale-[0.99]"

            >

              <Save className={cn('mr-2 h-4 w-4', saving && 'animate-pulse')} />

              {saving ? 'Сохранение…' : dirty ? 'Сохранить голос и темп' : 'Сохранено'}

            </Button>

          </Hint>

        </div>

      </div>

    </div>

  )

}


