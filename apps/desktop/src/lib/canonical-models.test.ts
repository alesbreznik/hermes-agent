import { describe, expect, it } from 'vitest'
import {
  buildCanonicalModelCatalog,
  getModelCapabilityScore,
  isLocalOrConfiguredProvider,
  parseModelInfo
} from './canonical-models'

describe('canonical-models', () => {
  it('parses Hermes models accurately', () => {
    const info = parseModelInfo('Hermes-3-Llama-3.1-8B-exl3-6.0bpw')
    expect(info.family).toBe('Hermes')
    expect(info.version).toBe('Hermes 3')
    expect(info.variant).toContain('8B')
    expect(info.displayName).toContain('Hermes 3')
  })

  it('parses Gemma models from various providers', () => {
    const info1 = parseModelInfo('google/gemma-4-26B-A4B-it')
    const info2 = parseModelInfo('gemma-4-26B-A4B-it-exl3')
    const info3 = parseModelInfo('google/gemma-4-31b-it')

    expect(info1.family).toBe('Gemma')
    expect(info1.version).toBe('Gemma 4')
    expect(info1.variant).toContain('26B')

    expect(info2.canonicalKey).toBe(info1.canonicalKey)
    expect(info3.variant).toContain('31B')
  })

  it('parses Llama, Claude, DeepSeek, and Qwen models', () => {
    expect(parseModelInfo('meta-llama/Llama-3.1-8B-Instruct').family).toBe('Llama')
    expect(parseModelInfo('anthropic/claude-3-7-sonnet').family).toBe('Claude')
    expect(parseModelInfo('deepseek-ai/DeepSeek-V4-Flash').family).toBe('DeepSeek')
    expect(parseModelInfo('Qwen/Qwen3.6-35B-A3B').family).toBe('Qwen')
    expect(parseModelInfo('zai-org/GLM-5.2').family).toBe('GLM')
  })

  it('builds catalog with deduplication and local prioritization', () => {
    const mockProviders = [
      {
        slug: 'huggingface',
        name: 'Hugging Face',
        authenticated: true,
        models: ['google/gemma-4-26B-A4B-it', 'meta-llama/Llama-3.1-8B-Instruct']
      },
      {
        slug: 'openai-api',
        name: 'Local GPU',
        authenticated: true,
        models: [
          'gemma-4-26B-A4B-it-exl3',
          'Hermes-3-Llama-3.1-8B-exl3-6.0bpw',
          // Static cloud OpenAI models should NOT be tagged as Local GPU!
          'gpt-5.6-sol',
          'gpt-4o'
        ]
      }
    ]

    const catalog = buildCanonicalModelCatalog(mockProviders)

    // Gemma 4 26B should be deduplicated into 1 canonical model
    const gemmaModels = catalog.canonicalModels.filter(m => m.version === 'Gemma 4' && m.variant.includes('26B'))
    expect(gemmaModels).toHaveLength(1)

    const gemma = gemmaModels[0]
    expect(gemma.isLocal).toBe(true)
    // The first provider in the list should be Local GPU (openai-api)
    expect(gemma.providers[0].provider.slug).toBe('openai-api')
    expect(gemma.providers[0].modelId).toBe('gemma-4-26B-A4B-it-exl3')
    // Secondary provider should be Hugging Face
    expect(gemma.providers[1].provider.slug).toBe('huggingface')

    // Local GPU group must ONLY contain the two verified local models!
    const localGroup = catalog.groupedByFamily.get('Local GPU') || []
    expect(localGroup).toHaveLength(2)
    const localNames = localGroup.map(m => m.displayName)
    expect(localNames).toContain('Hermes 3 · 8B')
    expect(localNames).toContain('Gemma 4 · 26B A4B IT')
    expect(localNames).not.toContain('GPT-5.6 · Sol')

    // GPT-5.6 should be categorized in OpenAI, NOT Local GPU
    const openaiGroup = catalog.groupedByFamily.get('OpenAI') || []
    const gptModel = openaiGroup.find(m => m.displayName.includes('GPT-5.6'))
    expect(gptModel).toBeDefined()
    expect(gptModel?.isLocal).toBe(false)
  })

  it('orders models from best to worst within each family', () => {
    const mockProviders = [
      {
        slug: 'openrouter',
        name: 'OpenRouter',
        authenticated: true,
        models: [
          // Hermes family: 405B > 70B > 8B
          'hermes-3-8b',
          'hermes-3-405b',
          'hermes-3-70b',
          // Gemma family: 31B > 26B > 12B
          'google/gemma-4-12b-it',
          'google/gemma-4-31b-it',
          'google/gemma-4-26b-a4b-it',
          // Claude family: Thinking > Sonnet > Haiku
          'anthropic/claude-3-5-haiku',
          'anthropic/claude-3-7-sonnet:thinking',
          'anthropic/claude-3-7-sonnet'
        ]
      }
    ]

    const catalog = buildCanonicalModelCatalog(mockProviders)

    const hermesModels = catalog.groupedByFamily.get('Hermes') || []
    expect(hermesModels[0].displayName).toBe('Hermes 3 · 405B')
    expect(hermesModels[1].displayName).toBe('Hermes 3 · 70B')
    expect(hermesModels[2].displayName).toBe('Hermes 3 · 8B')

    const gemmaModels = catalog.groupedByFamily.get('Gemma') || []
    expect(gemmaModels[0].displayName).toBe('Gemma 4 · 31B IT')
    expect(gemmaModels[1].displayName).toBe('Gemma 4 · 26B A4B IT')
    expect(gemmaModels[2].displayName).toBe('Gemma 4 · 12B IT')

    const claudeModels = catalog.groupedByFamily.get('Claude') || []
    expect(claudeModels[0].displayName).toBe('Claude 3.7 · Sonnet (Thinking)')
    expect(claudeModels[1].displayName).toBe('Claude 3.7 · Sonnet')
    expect(claudeModels[2].displayName).toBe('Claude 3.5 · Haiku')
  })
})
