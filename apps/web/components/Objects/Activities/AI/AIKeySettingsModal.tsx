import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { KeyRound, X, ExternalLink, Eye, EyeOff, Check, Trash2, Sparkles, ShieldCheck } from 'lucide-react'

export interface StudentBYOKData {
  apiKey: string
  provider: string
  model?: string
}

export const BYOK_STORAGE_KEY = 'learnhouse_student_byok'

export const getStoredBYOK = (): StudentBYOKData | null => {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(BYOK_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed.apiKey === 'string' && parsed.apiKey.trim()) {
      return parsed
    }
    return null
  } catch {
    return null
  }
}

export const saveStoredBYOK = (data: StudentBYOKData) => {
  if (typeof window === 'undefined') return
  localStorage.setItem(BYOK_STORAGE_KEY, JSON.stringify(data))
}

export const clearStoredBYOK = () => {
  if (typeof window === 'undefined') return
  localStorage.removeItem(BYOK_STORAGE_KEY)
}

export function useStudentBYOK() {
  const [byok, setByok] = useState<StudentBYOKData | null>(null)
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    setByok(getStoredBYOK())
    setIsLoaded(true)
  }, [])

  const saveBYOK = (data: StudentBYOKData) => {
    saveStoredBYOK(data)
    setByok(data)
  }

  const removeBYOK = () => {
    clearStoredBYOK()
    setByok(null)
  }

  return {
    byok,
    hasByokKey: Boolean(byok?.apiKey && byok.apiKey.trim().length > 0),
    saveBYOK,
    removeBYOK,
    isLoaded,
  }
}

export interface ProviderOption {
  id: string
  name: string
  badge: string
  badgeClass: string
  defaultModel: string
  models: string[]
  url: string
  urlLabel: string
  keyPrefixHint: string
  description: string
}

export const PROVIDER_OPTIONS: ProviderOption[] = [
  {
    id: 'gemini',
    name: 'Google Gemini',
    badge: 'Free & Recommended',
    badgeClass: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    defaultModel: 'gemini-1.5-flash',
    models: ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro'],
    url: 'https://aistudio.google.com/app/apikey',
    urlLabel: 'Get free key at Google AI Studio',
    keyPrefixHint: 'AIzaSy...',
    description: 'Generous free tier with fast response times. Best for student use.',
  },
  {
    id: 'groq',
    name: 'Groq',
    badge: 'Ultra Fast & Free',
    badgeClass: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
    defaultModel: 'llama-3.3-70b-versatile',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'],
    url: 'https://console.groq.com/keys',
    urlLabel: 'Get free key at Groq Console',
    keyPrefixHint: 'gsk_...',
    description: 'Blazing fast inference on open Llama 3 models with free tier.',
  },
  {
    id: 'openai',
    name: 'OpenAI',
    badge: 'Standard',
    badgeClass: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    defaultModel: 'gpt-4o-mini',
    models: ['gpt-4o-mini', 'gpt-4o'],
    url: 'https://platform.openai.com/api-keys',
    urlLabel: 'Get key at OpenAI Platform',
    keyPrefixHint: 'sk-proj-...',
    description: 'Industry standard models (GPT-4o mini, GPT-4o).',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    badge: 'Universal',
    badgeClass: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
    defaultModel: 'google/gemini-flash-1.5',
    models: ['google/gemini-flash-1.5', 'meta-llama/llama-3.3-70b-instruct'],
    url: 'https://openrouter.ai/keys',
    urlLabel: 'Get key at OpenRouter',
    keyPrefixHint: 'sk-or-...',
    description: 'Single key to access dozens of LLMs from multiple providers.',
  },
  {
    id: 'anthropic',
    name: 'Anthropic Claude',
    badge: 'High Quality',
    badgeClass: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    defaultModel: 'claude-3-5-haiku-20241022',
    models: ['claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022'],
    url: 'https://console.anthropic.com/',
    urlLabel: 'Get key at Anthropic Console',
    keyPrefixHint: 'sk-ant-...',
    description: 'Thoughtful reasoning models with Claude 3.5 Haiku & Sonnet.',
  },
]

interface AIKeySettingsModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (data: StudentBYOKData) => void
  onRemove: () => void
  currentData: StudentBYOKData | null
}

export function AIKeySettingsModal({
  isOpen,
  onClose,
  onSave,
  onRemove,
  currentData,
}: AIKeySettingsModalProps) {
  const [provider, setProvider] = useState<string>('gemini')
  const [apiKey, setApiKey] = useState<string>('')
  const [model, setModel] = useState<string>('')
  const [showKey, setShowKey] = useState<boolean>(false)
  const [savedSuccess, setSavedSuccess] = useState<boolean>(false)

  useEffect(() => {
    if (isOpen) {
      if (currentData?.apiKey) {
        setProvider(currentData.provider || 'gemini')
        setApiKey(currentData.apiKey)
        setModel(currentData.model || '')
      } else {
        setProvider('gemini')
        setApiKey('')
        setModel('gemini-1.5-flash')
      }
      setSavedSuccess(false)
      setShowKey(false)
    }
  }, [isOpen, currentData])

  const selectedProvider =
    PROVIDER_OPTIONS.find((p) => p.id === provider) || PROVIDER_OPTIONS[0]

  const handleProviderSelect = (pId: string) => {
    setProvider(pId)
    const opt = PROVIDER_OPTIONS.find((p) => p.id === pId)
    if (opt) {
      setModel(opt.defaultModel)
    }
  }

  const handleSave = () => {
    if (!apiKey.trim()) return
    onSave({
      apiKey: apiKey.trim(),
      provider,
      model: model.trim() || selectedProvider.defaultModel,
    })
    setSavedSuccess(true)
    setTimeout(() => {
      onClose()
    }, 600)
  }

  const handleRemove = () => {
    onRemove()
    setApiKey('')
    setModel(selectedProvider.defaultModel)
    onClose()
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[10005] flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/75 backdrop-blur-sm"
          />

          {/* Modal Card */}
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 15 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 15 }}
            transition={{ type: 'spring', duration: 0.3, bounce: 0.15 }}
            className="relative w-full max-w-lg bg-[#0d0f1a] border border-white/10 rounded-2xl p-6 text-white shadow-2xl z-10 max-h-[90vh] overflow-y-auto"
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-white/10">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  <KeyRound size={20} />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-white">
                    AI API Key Settings (BYOK)
                  </h2>
                  <p className="text-xs text-white/50">
                    Bring Your Own Key model for student-facing AI
                  </p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="text-white/40 hover:text-white hover:bg-white/10 p-1.5 rounded-full transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Privacy notice banner */}
            <div className="mt-4 p-3 rounded-xl bg-purple-950/30 border border-purple-800/30 flex items-start space-x-2.5 text-xs text-purple-200/90 leading-relaxed">
              <ShieldCheck size={18} className="shrink-0 text-purple-400 mt-0.5" />
              <span>
                <strong>Your key stays private:</strong> Your API key is stored only inside your browser&apos;s local storage and used directly to ask questions. It is never saved to the database or shared with others.
              </span>
            </div>

            {/* Provider selection */}
            <div className="mt-5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-white/60 mb-2">
                Select AI Provider
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {PROVIDER_OPTIONS.map((p) => {
                  const isSelected = p.id === provider
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => handleProviderSelect(p.id)}
                      className={`p-2.5 rounded-xl border text-left transition-all relative flex flex-col justify-between ${
                        isSelected
                          ? 'bg-purple-600/20 border-purple-500 text-white shadow-sm ring-1 ring-purple-500/50'
                          : 'bg-white/5 border-white/10 text-white/70 hover:bg-white/10 hover:border-white/20'
                      }`}
                    >
                      <div className="text-xs font-semibold flex items-center justify-between">
                        <span>{p.name}</span>
                        {isSelected && <Check size={13} className="text-purple-400" />}
                      </div>
                      <span
                        className={`mt-1 text-[10px] px-1.5 py-0.5 rounded border inline-block w-max ${p.badgeClass}`}
                      >
                        {p.badge}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* External link to get key */}
            <div className="mt-3 flex items-center justify-between text-xs">
              <span className="text-white/40">{selectedProvider.description}</span>
              <a
                href={selectedProvider.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-purple-400 hover:text-purple-300 underline inline-flex items-center space-x-1 shrink-0 ml-2"
              >
                <span>{selectedProvider.urlLabel}</span>
                <ExternalLink size={12} />
              </a>
            </div>

            {/* API Key Input */}
            <div className="mt-5">
              <label className="block text-xs font-semibold uppercase tracking-wider text-white/60 mb-1.5">
                API Key
              </label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={selectedProvider.keyPrefixHint}
                  className="w-full bg-black/50 border border-white/15 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 rounded-xl px-3.5 py-2.5 text-sm text-white placeholder:text-white/25 outline-hidden pr-10 font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white transition-colors"
                >
                  {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Model Input */}
            <div className="mt-4">
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                  Model
                </label>
                <div className="flex space-x-1.5">
                  {selectedProvider.models.map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setModel(m)}
                      className={`text-[11px] px-2 py-0.5 rounded transition-colors ${
                        model === m
                          ? 'bg-purple-600/30 text-purple-300 border border-purple-500/40 font-medium'
                          : 'bg-white/5 text-white/40 hover:bg-white/10 hover:text-white/70'
                      }`}
                    >
                      {m.replace('gemini-', '').replace('llama-', '').replace('claude-', '')}
                    </button>
                  ))}
                </div>
              </div>
              <input
                type="text"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder={selectedProvider.defaultModel}
                className="w-full bg-black/50 border border-white/15 focus:border-purple-500 focus:ring-1 focus:ring-purple-500 rounded-xl px-3.5 py-2 text-sm text-white placeholder:text-white/25 outline-hidden font-mono"
              />
            </div>

            {/* Buttons footer */}
            <div className="mt-6 pt-4 border-t border-white/10 flex items-center justify-between">
              {currentData?.apiKey ? (
                <button
                  type="button"
                  onClick={handleRemove}
                  className="text-red-400 hover:text-red-300 text-xs px-3 py-2 rounded-lg hover:bg-red-500/10 transition-colors flex items-center space-x-1.5"
                >
                  <Trash2 size={14} />
                  <span>Remove Key</span>
                </button>
              ) : (
                <span />
              )}

              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-medium text-white/60 hover:text-white hover:bg-white/10 rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!apiKey.trim()}
                  onClick={handleSave}
                  className={`px-4 py-2 text-xs font-semibold rounded-xl transition-all flex items-center space-x-1.5 ${
                    savedSuccess
                      ? 'bg-emerald-600 text-white'
                      : apiKey.trim()
                      ? 'bg-purple-600 hover:bg-purple-500 text-white shadow-md'
                      : 'bg-white/10 text-white/30 cursor-not-allowed'
                  }`}
                >
                  {savedSuccess ? (
                    <>
                      <Check size={14} />
                      <span>Saved!</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={14} />
                      <span>Save Key</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
