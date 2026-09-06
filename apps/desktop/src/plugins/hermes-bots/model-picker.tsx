/**
 * Provider + model dropdowns backed by the gateway's `model.options`
 * inventory, plus the bounded fetch that keeps a wedged bot socket from
 * spinning the picker forever.
 *
 * Shared by the advanced profile editor and the create dialog.
 */

import {
  Button,
  GlyphSpinner,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  useQuery
} from '@hermes/plugin-sdk'
import { useMemo, useState } from 'react'

import { labeled } from './dialog-parts'
import { botRouteKey, requestForBot, resolveBotConnectionRoute } from './routing'
import { ID } from './shared'
import type { RosterRow } from './types'

// ── model picker (model/provider dropdowns via model.options) ───────────────

// #95279: bounded RPC guard to prevent wedged socket spins
const MODEL_OPTIONS_SETTLE_MS = 20000

function boundedModelOptionsFetch<T>(fetch: Promise<T>, settleMs = MODEL_OPTIONS_SETTLE_MS): Promise<T> {
  const scope = typeof window === 'undefined' ? null : window

  if (!scope || typeof scope.setTimeout !== 'function') {
    return fetch
  }

  let timerId: any = null

  const deadline = new Promise<never>((_, reject) => {
    timerId = scope.setTimeout(() => {
      reject(new Error(`model.options did not answer within ${Math.round(settleMs / 1000)}s (#95279 settle guard)`))
    }, settleMs)
  })

  return Promise.race([fetch, deadline]).finally(() => scope.clearTimeout(timerId))
}

/** One provider row of the gateway's `model.options` inventory. Entries in
 *  `models` are bare slugs on current gateways and objects on older ones. */
export interface ModelProviderOption {
  authenticated?: boolean
  models?: Array<string | { id?: string; name?: string }>
  name?: string
  slug: string
}
export interface ModelOptionsResponse {
  providers?: ModelProviderOption[]
}

function useModelOptions(bot: null | RosterRow = null) {
  const resolved = bot ? resolveBotConnectionRoute(bot) : null
  const route = resolved?.status === 'resolved' ? resolved.route : null
  const orphaned = resolved?.status === 'owner_removed'

  return useQuery<ModelOptionsResponse>({
    queryKey: [ID, 'model-options', route ? botRouteKey(route) : 'active'],
    queryFn: () =>
      boundedModelOptionsFetch(
        requestForBot(bot, 'model.options', {
          include_unconfigured: true,
          explicit_only: false
        }) as Promise<ModelOptionsResponse>
      ),
    enabled: !orphaned,
    staleTime: 120000,
    retry: false
  })
}

export interface FallbackRoute {
  model: string
  provider: string
}

/** The fields a profile pins for its model and auto-fallback. */
export interface ModelSelection {
  fallback_providers?: FallbackRoute[]
  model: string
  provider: string
}

/** ModelPicker only ever emits the field(s) it just changed, so consumers can
 *  test membership with `in` and leave the rest of their state untouched. */
export type ModelSelectionPatch =
  | { fallback_providers?: FallbackRoute[]; model: string; provider: string }
  | { fallback_providers?: FallbackRoute[]; model: string }
  | { fallback_providers?: FallbackRoute[]; provider: string }

export interface ModelPickerProps {
  autoFallback?: boolean
  bot?: null | RosterRow
  onChange: (patch: ModelSelectionPatch) => void
  placeholderModel?: string
  value: ModelSelection
}

export function ModelPicker({
  bot = null,
  value,
  onChange,
  placeholderModel = 'gateway default',
  autoFallback: _autoFallback = true
}: ModelPickerProps) {
  const { data, isLoading, error } = useModelOptions(bot)

  const NONE = '__default__'
  const ALL = '__all__'
  const CUSTOM = '__custom__'

  const providers = useMemo(
    () => (data?.providers || []).filter(p => p && p.slug),
    [data?.providers]
  )

  const isKnown = !value.provider || value.provider === NONE || providers.some(p => p.slug === value.provider)
  const [useFreeText, setUseFreeText] = useState(!isKnown)

  const activeProvider = useMemo(
    () => providers.find(p => p.slug === value.provider) || null,
    [providers, value.provider]
  )

  const activeModels = useMemo(() => {
    if (!activeProvider) return []
    return (activeProvider.models || [])
      .map(m => (typeof m === 'string' ? m : m.id || m.name || ''))
      .filter(Boolean)
  }, [activeProvider])

  const allModels = useMemo(() => {
    const list: Array<{ model: string; providerSlug: string; providerName: string }> = []
    const seen = new Set<string>()
    for (const p of providers) {
      const pName = p.name || p.slug
      for (const raw of p.models || []) {
        const m = (typeof raw === 'string' ? raw : raw.id || raw.name || '').trim()
        if (!m) continue
        const key = `${p.slug}:::${m}`
        if (!seen.has(key)) {
          seen.add(key)
          list.push({ model: m, providerSlug: p.slug, providerName: pName })
        }
      }
    }
    return list
  }, [providers])

  if (isLoading) {
    return (
      <div className="flex justify-center py-2">
        <GlyphSpinner className="text-(--ui-text-tertiary)" spinner="breathe" />
      </div>
    )
  }

  if (error || !providers.length) {
    return (
      <div className="grid grid-cols-2 gap-2.5">
        {labeled(
          'Provider',
          <Input
            onChange={event =>
              onChange({
                provider: event.target.value
              })
            }
            placeholder="omnirouter / 9router / nous …"
            value={value.provider}
          />
        )}
        {labeled(
          'Model',
          <Input
            onChange={event =>
              onChange({
                model: event.target.value
              })
            }
            placeholder="antigravity/gemini-3.6-flash-high"
            value={value.model}
          />
        )}
      </div>
    )
  }

  if (useFreeText) {
    return (
      <div className="flex flex-col gap-2">
        <div className="grid grid-cols-2 gap-2.5">
          {labeled(
            'Provider (Custom)',
            <Input
              onChange={event =>
                onChange({
                  provider: event.target.value
                })
              }
              placeholder="e.g. omnirouter, inferx, 9router"
              value={value.provider}
            />
          )}
          {labeled(
            'Model (Custom)',
            <Input
              onChange={event =>
                onChange({
                  model: event.target.value
                })
              }
              placeholder="e.g. antigravity/gemini-3.6-flash-high"
              value={value.model}
            />
          )}
        </div>
        <Button
          className="h-6 self-start text-xs text-(--ui-text-tertiary)"
          onClick={() => setUseFreeText(false)}
          size="sm"
          variant="ghost"
        >
          ← Back to dropdowns
        </Button>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-[1fr_1.4fr] gap-2.5">
      {labeled(
        'Provider',
        <Select
          onValueChange={v => {
            if (v === NONE) {
              onChange({
                provider: '',
                model: ''
              })
            } else if (v === ALL) {
              onChange({
                provider: ''
              })
            } else if (v === CUSTOM) {
              setUseFreeText(true)
            } else {
              const prov = providers.find(p => p.slug === v)
              const provModels = (prov?.models || [])
                .map(m => (typeof m === 'string' ? m : m.id || m.name || ''))
                .filter(Boolean)
              const first = provModels[0] || ''
              onChange({
                provider: v,
                model: prov && provModels.includes(value.model) ? value.model : first
              })
            }
          }}
          value={value.provider || (value.model && !value.provider ? ALL : NONE)}
        >
          <SelectTrigger className="h-8 rounded-md">
            <SelectValue placeholder="Select provider..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Inherit (launch profile default)</SelectItem>
            <SelectItem value={ALL}>All Providers (Any)</SelectItem>
            {providers.map(p => (
              <SelectItem key={p.slug} value={p.slug}>
                {p.name ? `${p.name} (${p.slug})` : p.slug}
              </SelectItem>
            ))}
            <SelectItem value={CUSTOM}>✏️ Enter manually…</SelectItem>
          </SelectContent>
        </Select>
      )}

      {labeled(
        'Model',
        activeProvider && activeModels.length > 0 ? (
          <Select
            onValueChange={v => {
              if (v === NONE) {
                onChange({ model: '' })
              } else if (v === CUSTOM) {
                setUseFreeText(true)
              } else {
                onChange({ model: v })
              }
            }}
            value={value.model || (activeModels[0] ?? '')}
          >
            <SelectTrigger className="h-8 rounded-md">
              <SelectValue placeholder={placeholderModel || 'Select model...'} />
            </SelectTrigger>
            <SelectContent>
              {activeModels.map(m => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
              <SelectItem value={CUSTOM}>✏️ Enter manually…</SelectItem>
            </SelectContent>
          </Select>
        ) : !value.provider && allModels.length > 0 ? (
          <Select
            onValueChange={v => {
              if (v === NONE) {
                onChange({ model: '', provider: '' })
              } else if (v === CUSTOM) {
                setUseFreeText(true)
              } else {
                const found = allModels.find(item => item.model === v)
                if (found) {
                  onChange({ model: found.model, provider: found.providerSlug })
                } else {
                  onChange({ model: v })
                }
              }
            }}
            value={value.model || NONE}
          >
            <SelectTrigger className="h-8 rounded-md">
              <SelectValue placeholder={placeholderModel || 'Select from all models...'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>Inherit (launch profile default)</SelectItem>
              {allModels.map(item => (
                <SelectItem key={`${item.providerSlug}:${item.model}`} value={item.model}>
                  {item.model} ({item.providerName})
                </SelectItem>
              ))}
              <SelectItem value={CUSTOM}>✏️ Enter manually…</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input
            onChange={event =>
              onChange({
                model: event.target.value
              })
            }
            placeholder={placeholderModel || 'e.g. model name'}
            value={value.model}
          />
        )
      )}
    </div>
  )
}
