import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import {
  Send, BookOpen, Sparkles, Plus, MessageSquare,
  FileText, Trash2, Lightbulb, HelpCircle,
} from 'lucide-react'
import { tutorApi, documentsApi } from '../services/api'
import type { Document, Message, Conversation, SourceCitation } from '../types'
import Spinner from '../components/ui/Spinner'
import PrivacyBadge from '../components/ui/PrivacyBadge'

function SourceChip({ src }: { src: SourceCitation }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-brand-600/10 border border-brand-500/20 rounded-lg text-xs text-brand-400">
      <FileText className="w-2.5 h-2.5" />
      {src.document} — Page {src.page}
    </span>
  )
}

function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-slide-up`}>
      <div className={`max-w-[80%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? 'bg-brand-600 text-white rounded-br-sm'
            : 'bg-[#1e2235] text-white/90 rounded-bl-sm border border-white/5'
        }`}>
          {isUser ? (
            <p>{msg.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          )}
        </div>
        {msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-1 px-1">
            <span className="text-[10px] text-white/30 w-full">Sources:</span>
            {msg.sources.map((s, i) => <SourceChip key={i} src={s} />)}
          </div>
        )}
        {msg.timestamp && (
          <span className="text-[10px] text-white/25 px-1">
            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
    </div>
  )
}

const QUICK_ACTIONS = [
  { icon: Lightbulb, label: 'Explain simpler', mode: 'explain_simpler' },
  { icon: BookOpen,  label: 'Give an example', mode: 'give_example' },
  { icon: Sparkles,  label: 'Summarize this',  mode: 'summarize' },
  { icon: HelpCircle,label: 'Quiz me',         mode: 'quiz_me' },
]

export default function Tutor() {
  const [docs, setDocs] = useState<Document[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedDocs, setSelectedDocs] = useState<number[]>([])
  const [mode, setMode] = useState('standard')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    documentsApi.list().then(d => setDocs(d.filter(doc => doc.processing_status === 'ready')))
    tutorApi.conversations().then(setConversations)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadConversation = async (id: number) => {
    setActiveConvId(id)
    const conv = await tutorApi.getConversation(id)
    setMessages(conv.messages ?? [])
  }

  const newConversation = async () => {
    const conv = await tutorApi.createConversation('New Conversation', selectedDocs)
    setConversations(prev => [conv, ...prev])
    setActiveConvId(conv.id)
    setMessages([])
  }

  const deleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation()
    await tutorApi.deleteConversation(id)
    setConversations(prev => prev.filter(c => c.id !== id))
    if (activeConvId === id) { setActiveConvId(null); setMessages([]) }
  }

  const send = async (question?: string, sendMode?: string) => {
    const q = (question ?? input).trim()
    if (!q || loading) return

    // Ensure we have an active conversation
    let convId = activeConvId
    if (!convId) {
      const conv = await tutorApi.createConversation(q.slice(0, 60), selectedDocs)
      setConversations(prev => [conv, ...prev])
      setActiveConvId(conv.id)
      convId = conv.id
    }

    const userMsg: Message = { role: 'user', content: q }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const resp = await tutorApi.ask({
        question: q,
        document_ids: selectedDocs.length ? selectedDocs : undefined,
        conversation_id: convId,
        mode: sendMode ?? mode,
      })

      const assistantMsg: Message = {
        role: 'assistant',
        content: resp.answer,
        sources: resp.sources,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, assistantMsg])

      // Update conversation title
      setConversations(prev => prev.map(c =>
        c.id === convId ? { ...c, title: q.slice(0, 50) } : c
      ))
    } catch (e: unknown) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error: ${(e as Error).message}. Please check that the backend is running.`,
      }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full">
      {/* Sidebar — conversations */}
      <div className="w-56 shrink-0 border-r border-white/5 flex flex-col bg-[#12151f]">
        <div className="p-3 border-b border-white/5">
          <button onClick={newConversation} className="btn-primary w-full text-sm justify-center py-2">
            <Plus className="w-4 h-4" /> New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
          {conversations.map(c => (
            <div
              key={c.id}
              onClick={() => loadConversation(c.id)}
              className={`flex items-center gap-2 px-3 py-2.5 rounded-xl cursor-pointer group transition-all ${
                activeConvId === c.id ? 'bg-brand-600/20 text-brand-300' : 'text-white/50 hover:bg-white/5 hover:text-white/80'
              }`}
            >
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <span className="text-xs flex-1 truncate">{c.title}</span>
              <button
                onClick={e => deleteConversation(c.id, e)}
                className="opacity-0 group-hover:opacity-100 hover:text-red-400 transition-all"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))}
          {conversations.length === 0 && (
            <p className="text-xs text-white/20 px-3 py-4 text-center">No conversations yet</p>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        {/* Top bar */}
        <div className="px-6 py-4 border-b border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-semibold text-white">AI Tutor</h1>
            <PrivacyBadge />
          </div>
          {/* Doc selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-white/40">Context:</span>
            <select
              className="input py-1.5 text-xs w-48"
              onChange={e => {
                const v = parseInt(e.target.value)
                if (!isNaN(v)) setSelectedDocs(prev =>
                  prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v]
                )
              }}
            >
              <option value="">All documents</option>
              {docs.map(d => (
                <option key={d.id} value={d.id}>{d.filename}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
              <div className="w-16 h-16 rounded-2xl bg-brand-600/10 flex items-center justify-center">
                <Sparkles className="w-8 h-8 text-brand-400" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-white">Ask about your study material</h2>
                <p className="text-white/40 text-sm mt-1 max-w-sm">
                  Upload documents first, then ask questions. Answers are grounded in your material with source citations.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2 w-full max-w-sm">
                {['What is database normalization?', 'Explain sorting algorithms', 'Summarize key concepts', 'What is TCP vs UDP?'].map(q => (
                  <button
                    key={q}
                    onClick={() => send(q)}
                    className="text-left px-3 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-sm text-white/60 hover:text-white/90 transition-all border border-white/5"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((msg, i) => <ChatMessage key={i} msg={msg} />)}
          {loading && (
            <div className="flex justify-start animate-slide-up">
              <div className="bg-[#1e2235] rounded-2xl rounded-bl-sm border border-white/5 px-4 py-3">
                <div className="flex gap-1.5 items-center">
                  <div className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Quick actions */}
        <div className="px-6 pb-2 flex gap-2 overflow-x-auto">
          {QUICK_ACTIONS.map(a => (
            <button
              key={a.mode}
              onClick={() => { setMode(a.mode); setInput(a.label + ': ') }}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-xs text-white/50 hover:text-white/80 transition-all border border-white/5"
            >
              <a.icon className="w-3.5 h-3.5" />
              {a.label}
            </button>
          ))}
        </div>

        {/* Input */}
        <div className="px-6 pb-6">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <textarea
                className="input resize-none"
                rows={2}
                placeholder="Ask about your study material…"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() }
                }}
              />
            </div>
            <button
              onClick={() => send()}
              disabled={!input.trim() || loading}
              className="btn-primary shrink-0 py-3.5"
            >
              {loading ? <Spinner className="w-4 h-4" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
