import type { ModelProviderOption } from '@/plugins/hermes-bots/model-picker'

export interface ProviderBinding {
  isLocal: boolean
  isAuthenticated: boolean
  modelId: string
  provider: ModelProviderOption
}

export interface CanonicalModel {
  canonicalKey: string
  displayName: string
  family: string
  hasConfigured: boolean
  isLocal: boolean
  providers: ProviderBinding[]
  variant: string
  version: string
}

export function isLocalOrConfiguredProvider(p?: ModelProviderOption | null): boolean {
  if (!p) return false
  const s = (p.slug || '').toLowerCase()
  if (['openai-api', 'local', 'custom', 'tabby', 'ollama', 'omniroute', 'omnirouter'].includes(s)) return true
  if (p.authenticated === true) return true
  return false
}

export const VERIFIED_LOCAL_MODELS = new Set([
  'hermes-3-llama-3.1-8b-exl3-6.0bpw',
  'gemma-4-26b-a4b-it-exl3'
])

export function isStrictLocalModel(rawModelId: string, p?: ModelProviderOption | null): boolean {
  if (!p) return false
  const s = (p.slug || '').toLowerCase()
  const m = (rawModelId || '').toLowerCase()
  if (
    VERIFIED_LOCAL_MODELS.has(m) ||
    (m.includes('hermes-3') && m.includes('exl3')) ||
    (m.includes('gemma-4-26b') && m.includes('exl3'))
  ) {
    if (['openai-api', 'local', 'custom', 'tabby', 'ollama'].includes(s)) {
      return true
    }
  }
  return false
}

export function isStrictLocalProvider(p?: ModelProviderOption | null): boolean {
  if (!p) return false
  const s = (p.slug || '').toLowerCase()
  return ['openai-api', 'local', 'custom', 'tabby', 'ollama'].includes(s)
}

/** Strip quantization, file formats and date pins to get canonical model ID */
function stripFormatAndDate(text: string): string {
  return text
    .replace(/-exl[23]/gi, '')
    .replace(/-\d+(\.\d+)?bpw/gi, '')
    .replace(/-(gguf|awq|gptq|fp16|bf16|q4_k_m|q8_0)/gi, '')
    .replace(/-\d{8}$/, '')
    .replace(/[-_]+/g, '-')
    .trim()
}

/** Parse any raw model string into structured Family, Version, and Variant */
export function parseModelInfo(rawModelId: string): {
  family: string
  version: string
  variant: string
  canonicalKey: string
  displayName: string
} {
  const trimmed = (rawModelId || '').trim()
  const slash = trimmed.lastIndexOf('/')
  const base = slash >= 0 ? trimmed.slice(slash + 1) : trimmed
  const cleanedBase = stripFormatAndDate(base)
  const lower = cleanedBase.toLowerCase()

  // 0. OmniRoute Combos
  if (lower.startsWith('auto/best-') || lower.startsWith('omniroute/best-') || lower.startsWith('auto/pro-')) {
    const rawVariant = base.replace(/^best-/, '').replace(/^pro-/, '').replace(/-/g, ' ')
    const title = rawVariant.charAt(0).toUpperCase() + rawVariant.slice(1)
    const isPro = lower.includes('pro-')
    return {
      family: 'OmniRoute Combos',
      version: 'OmniRoute',
      variant: `${isPro ? 'Pro ' : 'Best '}${title}`,
      canonicalKey: `omniroute:auto:${base.toLowerCase()}`,
      displayName: `OmniRoute · ${isPro ? 'Pro' : 'Best'} ${title}`
    }
  }

  // 1. Hermes / Nous
  if (lower.includes('hermes')) {
    const is3 = lower.includes('3')
    const version = is3 ? 'Hermes 3' : 'Hermes'
    let variant = '8B'
    if (lower.includes('405b')) variant = '405B'
    else if (lower.includes('70b')) variant = '70B'
    else if (lower.includes('8b')) variant = '8B'

    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'Hermes',
      version,
      variant,
      canonicalKey: `hermes:${is3 ? '3' : 'legacy'}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 2. Gemma
  if (lower.includes('gemma')) {
    const matchVer = lower.match(/gemma[-_\s]?([0-9]+)/)
    const verNum = matchVer ? matchVer[1] : '4'
    const version = `Gemma ${verNum}`
    const matchSize = cleanedBase.match(/([0-9]+[bB](?:[-_]?[a-zA-Z0-9]+)*)/)
    let variant = matchSize ? matchSize[1].toUpperCase().replace(/-IT$/, '').replace(/-/g, ' ').trim() : 'Instruct'
    if (lower.includes('it') && !variant.includes('IT')) {
      variant += ' IT'
    }
    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'Gemma',
      version,
      variant,
      canonicalKey: `gemma:${verNum}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 3. Llama
  if (lower.includes('llama')) {
    const matchVer = lower.match(/llama[-_\s]?([0-9.]+)/)
    const verNum = matchVer ? matchVer[1] : '3.1'
    const version = `Llama ${verNum}`
    const matchSize = cleanedBase.match(/([0-9]+[bB])/)
    const size = matchSize ? matchSize[1].toUpperCase() : '8B'
    const isInstruct = lower.includes('instruct')
    const variant = `${size}${isInstruct ? ' Instruct' : ''}`
    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'Llama',
      version,
      variant,
      canonicalKey: `llama:${verNum}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 4. Claude
  if (lower.includes('claude')) {
    let version = 'Claude 3.7'
    if (lower.includes('3-5') || lower.includes('3.5')) version = 'Claude 3.5'
    else if (lower.includes('3-7') || lower.includes('3.7')) version = 'Claude 3.7'
    else if (lower.includes('opus-5') || lower.includes('fable-5') || lower.includes('opus-5')) version = 'Claude 5'

    let variant = 'Sonnet'
    if (lower.includes('opus')) variant = 'Opus'
    else if (lower.includes('haiku')) variant = 'Haiku'
    else if (lower.includes('fable')) variant = 'Fable'

    if (lower.includes('thinking')) variant += ' (Thinking)'
    else if (lower.includes('fast')) variant += ' (Fast)'

    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'Claude',
      version,
      variant,
      canonicalKey: `claude:${version.toLowerCase().replace(/[^a-z0-9]/g, '')}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 5. DeepSeek
  if (lower.includes('deepseek')) {
    let version = 'DeepSeek V4'
    if (lower.includes('r1')) version = 'DeepSeek R1'
    else if (lower.includes('v3')) version = 'DeepSeek V3'
    else if (lower.includes('v4')) version = 'DeepSeek V4'

    let variant = 'Chat'
    if (lower.includes('flash')) variant = 'Flash'
    else if (lower.includes('pro')) variant = 'Pro'
    else if (lower.includes('reasoner') || lower.includes('r1')) variant = 'Reasoning'

    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'DeepSeek',
      version,
      variant,
      canonicalKey: `deepseek:${version.toLowerCase().replace(/[^a-z0-9]/g, '')}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 6. Qwen
  if (lower.includes('qwen')) {
    const matchVer = lower.match(/qwen[-_\s]?([0-9.]+)/)
    const verNum = matchVer ? matchVer[1] : '3.6'
    const version = `Qwen ${verNum}`
    const matchSize = cleanedBase.match(/([0-9.]+[bBtT](?:[-_]?[a-zA-Z0-9]+)*)/)
    const variant = matchSize ? matchSize[1].toUpperCase() : 'Chat'
    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'Qwen',
      version,
      variant,
      canonicalKey: `qwen:${verNum}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 7. GLM
  if (lower.includes('glm')) {
    const matchVer = cleanedBase.match(/glm[-_\s]?([0-9.]+)/i)
    const verNum = matchVer ? matchVer[1] : '5'
    const version = `GLM ${verNum}`
    const variant = cleanedBase.replace(/glm[-_\s]?[0-9.]+/i, '').replace(/^[-_\s]+/, '').trim() || 'Standard'
    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'GLM',
      version,
      variant,
      canonicalKey: `glm:${verNum}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 8. Gemini
  if (lower.includes('gemini')) {
    const matchVer = lower.match(/gemini[-_\s]?([0-9.]+)/)
    const verNum = matchVer ? matchVer[1] : '2.5'
    const version = `Gemini ${verNum}`
    let variant = 'Flash'
    if (lower.includes('pro')) variant = 'Pro'
    else if (lower.includes('flash-lite')) variant = 'Flash Lite'
    else if (lower.includes('flash')) variant = 'Flash'
    if (lower.includes('preview')) variant += ' (Preview)'

    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'Gemini',
      version,
      variant,
      canonicalKey: `gemini:${verNum}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // 9. OpenAI / GPT
  if (lower.includes('gpt') || lower.startsWith('o1') || lower.startsWith('o3') || lower.startsWith('o4')) {
    let version = 'GPT-4o'
    if (lower.includes('5.6') || lower.includes('5-6')) version = 'GPT-5.6'
    else if (lower.includes('4.5') || lower.includes('4-5')) version = 'GPT-4.5'
    else if (lower.includes('4o')) version = 'GPT-4o'
    else if (lower.includes('o3')) version = 'o3'
    else if (lower.includes('o1')) version = 'o1'

    let variant = 'Standard'
    if (lower.includes('mini')) variant = 'Mini'
    else if (lower.includes('pro')) variant = 'Pro'
    else if (lower.includes('sol')) variant = 'Sol'

    const keyVariant = variant.toLowerCase().replace(/[^a-z0-9]/g, '')
    return {
      family: 'OpenAI',
      version,
      variant,
      canonicalKey: `openai:${version.toLowerCase().replace(/[^a-z0-9]/g, '')}:${keyVariant}`,
      displayName: `${version} · ${variant}`
    }
  }

  // Fallback: Clean base name
  const clean = base.replace(/[-_]/g, ' ')
  return {
    family: 'Other',
    version: 'Other',
    variant: clean,
    canonicalKey: `other:${base.toLowerCase().replace(/[^a-z0-9]/g, '')}`,
    displayName: clean
  }
}

/** Compute capability score to order models inside each family from best to worst */
export function getModelCapabilityScore(model: CanonicalModel): number {
  let score = 0
  const name = (model.displayName + ' ' + model.variant + ' ' + model.version).toLowerCase()

  // 1. Parameter size weighting (highest/largest first)
  if (name.includes('405b') || name.includes('400b')) score += 5000
  else if (name.includes('2.4t') || name.includes('1t')) score += 4000
  else if (name.includes('70b') || name.includes('72b')) score += 3000
  else if (name.includes('35b') || name.includes('31b') || name.includes('32b')) score += 2000
  else if (name.includes('26b') || name.includes('27b')) score += 1800
  else if (name.includes('14b') || name.includes('12b')) score += 1200
  else if (name.includes('8b') || name.includes('9b') || name.includes('7b')) score += 800
  else if (name.includes('3b') || name.includes('2b') || name.includes('1b')) score += 300

  // 2. Family version weighting (newer/higher versions get higher capability priority)
  const verMatch = name.match(/([0-9]+(?:\.[0-9]+)?)/)
  if (verMatch) {
    score += parseFloat(verMatch[1]) * 100
  }

  // 3. Tier / capability modifiers
  if (name.includes('thinking') || name.includes('reasoning') || name.includes('r1')) score += 400
  if (name.includes('opus')) score += 500
  if (name.includes('pro')) score += 350
  if (name.includes('sonnet')) score += 300
  if (name.includes('plus')) score += 250
  if (name.includes('flash')) score += 100
  if (name.includes('mini') || name.includes('lite') || name.includes('haiku')) score -= 200
  if (name.includes('nano')) score -= 300

  return score
}

const FAMILY_ORDER = [
  'Local GPU',
  'OmniRoute Combos',
  'Hermes',
  'Gemma',
  'Llama',
  'Claude',
  'DeepSeek',
  'Qwen',
  'GLM',
  'Gemini',
  'OpenAI',
  'Other'
]

export function buildCanonicalModelCatalog(providers: ModelProviderOption[]) {
  const canonicalMap = new Map<string, CanonicalModel>()
  const rawModelToCanonical = new Map<string, string>()

  // Sort providers so local and authenticated providers are bound with top priority
  const sortedProviders = [...providers].sort((a, b) => {
    const aScore = isStrictLocalProvider(a) ? 20 : a.authenticated ? 10 : 0
    const bScore = isStrictLocalProvider(b) ? 20 : b.authenticated ? 10 : 0
    return bScore - aScore
  })

  for (const prov of sortedProviders) {
    const isAuthenticated = isLocalOrConfiguredProvider(prov)
    const provModels = (prov.models || []).map((m: any) => (typeof m === 'string' ? m : m.id || m.name || ''))

    for (const rawId of provModels) {
      if (!rawId) continue
      const isLocal = isStrictLocalModel(rawId, prov)
      const info = parseModelInfo(rawId)
      rawModelToCanonical.set(rawId, info.canonicalKey)

      let modelEntry = canonicalMap.get(info.canonicalKey)
      if (!modelEntry) {
        modelEntry = {
          canonicalKey: info.canonicalKey,
          family: isLocal ? 'Local GPU' : info.family,
          version: info.version,
          variant: info.variant,
          displayName: info.displayName,
          isLocal,
          hasConfigured: isAuthenticated,
          providers: []
        }
        canonicalMap.set(info.canonicalKey, modelEntry)
      }

      if (isLocal) {
        modelEntry.isLocal = true
      }
      if (isAuthenticated) {
        modelEntry.hasConfigured = true
      }

      if (!modelEntry.providers.some(p => p.provider.slug === prov.slug)) {
        modelEntry.providers.push({
          provider: prov,
          modelId: rawId,
          isLocal,
          isAuthenticated
        })
      }
    }
  }

  // Sort providers within each canonical model (local first, then authenticated)
  for (const model of canonicalMap.values()) {
    model.providers.sort((a, b) => {
      const aScore = a.isLocal ? 20 : a.isAuthenticated ? 10 : 0
      const bScore = b.isLocal ? 20 : b.isAuthenticated ? 10 : 0
      return bScore - aScore
    })
  }

  // Group models by Family
  const groupedByFamily = new Map<string, CanonicalModel[]>()
  for (const fam of FAMILY_ORDER) {
    groupedByFamily.set(fam, [])
  }

  for (const model of canonicalMap.values()) {
    const fam = model.isLocal ? 'Local GPU' : groupedByFamily.has(model.family) ? model.family : 'Other'
    groupedByFamily.get(fam)?.push(model)
  }

  // Sort models within each family from BEST to WORST using capability score
  for (const [fam, list] of groupedByFamily.entries()) {
    list.sort((a, b) => {
      // Configured models take priority over unconfigured
      if (a.hasConfigured !== b.hasConfigured) {
        return a.hasConfigured ? -1 : 1
      }
      // Capability score descending (best model at index 0)
      const scoreA = getModelCapabilityScore(a)
      const scoreB = getModelCapabilityScore(b)
      if (scoreA !== scoreB) {
        return scoreB - scoreA
      }
      return a.displayName.localeCompare(b.displayName, undefined, { sensitivity: 'base', numeric: true })
    })
  }

  const allCanonicalModels = Array.from(canonicalMap.values())

  return {
    canonicalModels: allCanonicalModels,
    canonicalMap,
    rawModelToCanonical,
    groupedByFamily
  }
}
