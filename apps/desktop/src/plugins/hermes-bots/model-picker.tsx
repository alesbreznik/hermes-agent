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

// #95279: the picker's catalog read rides the BOT's own socket — a lazily
// dialed second backend that can wedge (cold pool spawn, dropped remote hop)
// without the primary socket ever noticing. An unbounded RPC there left the
// query pending forever and the picker spinning ("never settles"). Bound every
// attempt: past the budget the query rejects and ModelPicker falls back to its
// free-text inputs instead of an eternal GlyphSpinner.
const MODEL_OPTIONS_SETTLE_MS = 20000

function boundedModelOptionsFetch<T>(fetch: Promise<T>, settleMs = MODEL_OPTIONS_SETTLE_MS): Promise<T> {
  // window.setTimeout (not bare setTimeout): bare vm test harnesses expose
  // timers only through the window shim. With no scheduler at all, degrade to
  // the old unbounded behavior rather than not fetching.
  const scope = typeof window === 'undefined' ? null : window

  if (!scope || typeof scope.setTimeout !== 'function') {
    return fetch
  }

  // `any`: the timer id is assigned synchronously by the executor below, but
  // it is still `null` on the declaration TypeScript sees from the closure,
  // and clearTimeout's signature takes `number | undefined`.
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
interface ModelProviderOption {
  models?: Array<string | { id?: string; name?: string }>
  name?: string
  slug: string
}
interface ModelOptionsResponse {
  providers?: ModelProviderOption[]
}

function useModelOptions(bot: null | RosterRow = null) {
  // Hook body runs during render: an orphaned row must paint the picker
  // disabled/erroring, not throw into the pane's error boundary.
  const resolved = bot ? resolveBotConnectionRoute(bot) : null
  const route = resolved?.status === 'resolved' ? resolved.route : null
  const orphaned = resolved?.status === 'owner_removed'

  return useQuery<ModelOptionsResponse>({
    queryKey: [ID, 'model-options', route ? botRouteKey(route) : 'active'],
    // No forced `refresh`: forcing a network read on EVERY mount bypassed the
    // staleTime cache, so each Bots view remount (tab re-front, dialog reopen,
    // pane visibility flip) knocked the picker back into its loading state and
    // discarded the user's staged selection mid-edit (#95279). The cached read
    // still refreshes per staleTime like every other surface's catalog.
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

/**
 * Model-first + provider dropdowns from the gateway's configured inventory.
 * `value = {provider, model}`; onChange receives the merged patch.
 */
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

import {
  buildCanonicalModelCatalog,
  isLocalOrConfiguredProvider,
  isStrictLocalProvider
} from '@/lib/canonical-models'

export function ModelPicker({
  bot = null,
  value,
  onChange,
  placeholderModel = 'gateway default',
  autoFallback = true
}: ModelPickerProps) {
  const { data, isLoading, error } = useModelOptions(bot)

  // Hooks are ALWAYS declared up front, before any conditional return.
  const NONE = '__default__'
  const CUSTOM = '__custom__'
  const providers = useMemo(() => (data?.providers || []).filter(p => p && p.slug), [data?.providers])

  // Build canonical deduplicated catalog grouped by family, version, and variant
  const { canonicalModels, canonicalMap, rawModelToCanonical, groupedByFamily } = useMemo(
    () => buildCanonicalModelCatalog(providers),
    [providers]
  )

  const currentCanonicalKey = useMemo(() => {
    if (!value.model || value.model === NONE) return NONE
    return rawModelToCanonical.get(value.model) || (canonicalMap.has(value.model) ? value.model : value.model)
  }, [value.model, rawModelToCanonical, canonicalMap, NONE])

  const isKnown =
    (!value.provider || value.provider === NONE || providers.some(p => p.slug === value.provider)) &&
    (!value.model ||
      value.model === NONE ||
      rawModelToCanonical.has(value.model) ||
      canonicalMap.has(value.model) ||
      canonicalModels.length === 0)

  const [useFreeText, setUseFreeText] = useState(!isKnown)

  if (isLoading) {
    return (
      <div className="flex justify-center py-2">
        <GlyphSpinner className="text-(--ui-text-tertiary)" spinner="breathe" />
      </div>
    )
  }

  if (error || !providers.length) {
    // Fallback: free text (older gateway or empty inventory).
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
        <div className="grid grid-cols-[1.4fr_1fr] gap-2.5">
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

  // Determine available providers for the current canonical model (local/configured prioritized)
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
    <div className="grid grid-cols-[1.4fr_1fr] gap-2.5">
      {labeled(
        'Model',
        <Select
          onValueChange={v => {
            if (v === NONE) {
              onChange({
                model: '',
                provider: '',
                fallback_providers: []
              })
            } else if (v === CUSTOM) {
              setUseFreeText(true)
            } else {
              const modelEntry = canonicalMap.get(v)
              if (modelEntry && modelEntry.providers.length > 0) {
                // Check if the current provider is one of the providers for this model
                const existingBinding = modelEntry.providers.find(p => p.provider.slug === value.provider)
                // If current provider is valid for this model, keep it; otherwise pick the top-ranked provider (local GPU first)
                const bestBinding = existingBinding || modelEntry.providers[0]
                const chosenProvider = bestBinding.provider.slug
                const chosenRawModel = bestBinding.modelId

                // Build auto-fallback list across other supporting backup providers
                const fallbackBindings = modelEntry.providers.filter(p => p.provider.slug !== chosenProvider)
                const fallbacks = autoFallback
                  ? fallbackBindings.map(b => ({
                      provider: b.provider.slug,
                      model: b.modelId
                    }))
                  : []

                onChange({
                  model: chosenRawModel,
                  provider: chosenProvider,
                  ...(fallbacks.length ? { fallback_providers: fallbacks } : {})
                })
              } else {
                onChange({
                  model: v,
                  provider: value.provider || ''
                })
              }
            }
          }}
          value={currentCanonicalKey}
        >
          <SelectTrigger className="h-8 rounded-md">
            <SelectValue placeholder={placeholderModel || 'Select model...'} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Inherit (launch profile default)</SelectItem>
            {Array.from(groupedByFamily.entries()).map(([family, models]) => {
              if (!models.length) return null
              return (
                <div key={family} className="py-1">
                  <div className="px-2 py-1 text-[10px] font-semibold tracking-wider text-(--ui-text-tertiary) uppercase">
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
            <SelectItem value={CUSTOM}>✏️ Enter manually…</SelectItem>
          </SelectContent>
        </Select>
      )}

      {labeled(
        'Provider / Host',
        <Select
          disabled={!value.model && !value.provider}
          onValueChange={v => {
            if (v === NONE) {
              onChange({
                provider: '',
                fallback_providers: []
              })
            } else if (v === CUSTOM) {
              setUseFreeText(true)
            } else {
              const modelEntry = canonicalMap.get(currentCanonicalKey)
              if (modelEntry) {
                const binding = modelEntry.providers.find(p => p.provider.slug === v)
                const nextModel = binding ? binding.modelId : value.model
                const fallbackBindings = modelEntry.providers.filter(p => p.provider.slug !== v)
                const fallbacks = autoFallback
                  ? fallbackBindings.map(b => ({
                      provider: b.provider.slug,
                      model: b.modelId
                    }))
                  : []

                onChange({
                  model: nextModel,
                  provider: v,
                  ...(fallbacks.length ? { fallback_providers: fallbacks } : {})
                })
              } else {
                onChange({
                  provider: v
                })
              }
            }
          }}
          value={value.provider || NONE}
        >
          <SelectTrigger className="h-8 rounded-md">
            <SelectValue placeholder="Select provider..." />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>Inherit (default)</SelectItem>
            {displayProviders.map(p => (
              <SelectItem key={p.slug} value={p.slug}>
                {p.name}
              </SelectItem>
            ))}
            <SelectItem value={CUSTOM}>✏️ Enter manually…</SelectItem>
          </SelectContent>
        </Select>
      )}
    </div>
  )
}
