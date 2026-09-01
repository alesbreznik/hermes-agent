import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getGlobalModelOptions } from '@/hermes'
import type { ModelOptionProvider } from '@/hermes'
import { useI18n } from '@/i18n'
import { Plus, X } from '@/lib/icons'
import { cn } from '@/lib/utils'

import { CONTROL_TEXT } from './constants'

interface FallbackEntry {
  provider: string
  model: string
}

// Normalize the raw config value (`fallback_providers`: a list of
// `{provider, model}` dicts) into editor rows. Defensive against legacy string
// entries ("provider/model") so the editor never crashes on odd data.
function normalizeEntries(value: unknown): FallbackEntry[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.map(item => {
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>

      return { provider: String(record.provider ?? ''), model: String(record.model ?? '') }
    }

    if (typeof item === 'string') {
      const slash = item.indexOf('/')

      return slash > 0
        ? { provider: item.slice(0, slash), model: item.slice(slash + 1) }
        : { provider: '', model: item }
    }

    return { provider: '', model: '' }
  })
}

function completeEntries(rows: FallbackEntry[]): FallbackEntry[] {
  return rows.filter(entry => entry.provider && entry.model)
}

function entriesEqual(a: FallbackEntry[], b: FallbackEntry[]): boolean {
  return (
    a.length === b.length &&
    a.every((entry, index) => entry.provider === b[index]?.provider && entry.model === b[index]?.model)
  )
}

import {
  buildCanonicalModelCatalog,
  isLocalOrConfiguredProvider,
  isStrictLocalProvider
} from '@/lib/canonical-models'

/**
 * Structured editor for the top-level `fallback_providers` config list — a
 * chain of `{provider, model}` pairs tried in order when the default model
 * fails. Model-first dropdown layout: select model first, then host provider.
 */
export function FallbackModelsField({
  value,
  onChange
}: {
  value: unknown
  onChange: (next: FallbackEntry[]) => void
}) {
  const { t } = useI18n()
  const m = t.settings.model

  const modelOptions = useQuery({
    queryKey: ['model-options', 'global'],
    queryFn: () => getGlobalModelOptions()
  })

  const providers = (modelOptions.data?.providers ?? []).filter(provider => provider.slug)

  // Build canonical deduplicated catalog grouped by family, version, and variant
  const { canonicalModels, canonicalMap, rawModelToCanonical, groupedByFamily } = useMemo(
    () => buildCanonicalModelCatalog(providers),
    [providers]
  )

  const [rows, setRows] = useState<FallbackEntry[]>(() => normalizeEntries(value))
  // Last complete chain we emitted (or seeded). Autosave echoes the same
  // filtered list back through `value`; ignore that echo so draft rows stay.
  const lastEmittedRef = useRef(normalizeEntries(value))

  // Resync on real external changes (profile switch / config reload). Skip
  // when `value` is just our own commit echoing through the parent.
  // eslint-disable-next-line no-restricted-syntax -- legitimate non-atom ref write (see eslint rule comment)
  useEffect(() => {
    const persisted = normalizeEntries(value)

    if (entriesEqual(persisted, lastEmittedRef.current)) {
      return
    }

    lastEmittedRef.current = persisted
    setRows(persisted)
  }, [value])

  const commit = (next: FallbackEntry[]) => {
    const complete = completeEntries(next)

    setRows(next)
    lastEmittedRef.current = complete
    onChange(complete)
  }

  const updateRow = (index: number, patch: Partial<FallbackEntry>) =>
    commit(rows.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)))

  return (
    <div className="grid w-full gap-1.5">
      {rows.length === 0 && <p className="text-xs text-muted-foreground">{m.fallbackEmpty}</p>}
      {rows.map((entry, index) => {
        const currentCanonicalKey =
          rawModelToCanonical.get(entry.model) || (canonicalMap.has(entry.model) ? entry.model : entry.model)
        const currentModelEntry = canonicalMap.get(currentCanonicalKey)
        const availableProviderBindings = currentModelEntry?.providers || []

        const displayProviders =
          availableProviderBindings.length > 0
            ? availableProviderBindings.map(b => ({
                slug: b.provider.slug,
                name: b.isLocal ? `Local GPU (${b.provider.slug})` : b.provider.name || b.provider.slug
              }))
            : providers.map(p => ({
                slug: p.slug,
                name: p.name || p.slug
              }))

        return (
          <div className="flex flex-wrap items-center gap-2" key={index}>
            <span className="w-4 shrink-0 text-center font-mono text-[0.7rem] text-muted-foreground">{index + 1}</span>
            <Select
              onValueChange={cKey => {
                const modelEntry = canonicalMap.get(cKey)
                if (modelEntry && modelEntry.providers.length > 0) {
                  const existingBinding = modelEntry.providers.find(p => p.provider.slug === entry.provider)
                  const bestBinding = existingBinding || modelEntry.providers[0]
                  updateRow(index, { model: bestBinding.modelId, provider: bestBinding.provider.slug })
                } else {
                  updateRow(index, { model: cKey })
                }
              }}
              value={currentCanonicalKey}
            >
              <SelectTrigger className={cn('min-w-52 flex-1', CONTROL_TEXT)}>
                <SelectValue placeholder={m.model} />
              </SelectTrigger>
              <SelectContent>
                {Array.from(groupedByFamily.entries()).map(([family, models]) => {
                  if (!models.length) return null
                  return (
                    <div key={family} className="py-1">
                      <div className="px-2 py-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                        {family === 'Local GPU' ? '🟢 Local GPU Hardware' : `${family} Family`}
                      </div>
                      {models.map(m => {
                        const provCount = m.providers.length
                        return (
                          <SelectItem key={m.canonicalKey} value={m.canonicalKey}>
                            {m.displayName}
                            {m.isLocal ? ' 🟢 [Local GPU]' : ''}
                            {provCount > 1 ? ` · ${provCount} hosts` : ''}
                          </SelectItem>
                        )
                      })}
                    </div>
                  )
                })}
              </SelectContent>
            </Select>
            <Select
              disabled={!entry.model && !entry.provider}
              onValueChange={provider => {
                if (currentModelEntry) {
                  const binding = currentModelEntry.providers.find(p => p.provider.slug === provider)
                  const nextModel = binding ? binding.modelId : entry.model
                  updateRow(index, { provider, model: nextModel })
                } else {
                  updateRow(index, { provider })
                }
              }}
              value={entry.provider}
            >
              <SelectTrigger className={cn('min-w-36', CONTROL_TEXT)}>
                <SelectValue placeholder={m.provider} />
              </SelectTrigger>
              <SelectContent>
                {displayProviders.map(provider => (
                  <SelectItem key={provider.slug} value={provider.slug}>
                    {provider.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              aria-label={t.common.remove}
              onClick={() => commit(rows.filter((_, i) => i !== index))}
              size="icon-xs"
              variant="ghost"
            >
              <X className="size-3.5" />
            </Button>
          </div>
        )
      })}
      <div>
        <Button onClick={() => commit([...rows, { provider: '', model: '' }])} size="sm" variant="textStrong">
          <Plus className="size-3.5" />
          {m.fallbackAdd}
        </Button>
      </div>
    </div>
  )
}
