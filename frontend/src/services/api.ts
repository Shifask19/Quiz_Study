import axios from 'axios'
import type {
  Document, AskResponse, Conversation, QuizQuestion,
  QuizResult, DashboardStats, TopicMastery, ModelInfo,
  BenchmarkResult, RevisionSession,
} from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 120_000,
})

// ─── Documents ────────────────────────────────────────────────
export const documentsApi = {
  list: () => api.get<Document[]>('/documents/').then(r => r.data),

  upload: (file: File, onProgress?: (pct: number) => void) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Document>('/documents/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: e => onProgress && e.total
        ? onProgress(Math.round((e.loaded / e.total) * 100))
        : undefined,
    }).then(r => r.data)
  },

  get: (id: number) => api.get<Document>(`/documents/${id}`).then(r => r.data),

  delete: (id: number) => api.delete(`/documents/${id}`).then(r => r.data),

  summary: (id: number, type: 'quick' | 'exam' | 'simple' = 'quick') =>
    api.get(`/documents/${id}/summary`, { params: { summary_type: type } }).then(r => r.data),

  loadDemo: () => api.post('/documents/demo').then(r => r.data),
}

// ─── Tutor ────────────────────────────────────────────────────
export const tutorApi = {
  ask: (params: {
    question: string
    document_ids?: number[]
    conversation_id?: number
    mode?: string
  }) => api.post<AskResponse>('/tutor/ask', params).then(r => r.data),

  conversations: () => api.get<Conversation[]>('/tutor/conversations').then(r => r.data),

  createConversation: (title?: string, documentIds?: number[]) =>
    api.post<Conversation>('/tutor/conversations', {
      title: title || 'New Conversation',
      document_ids: documentIds,
    }).then(r => r.data),

  getConversation: (id: number) =>
    api.get<Conversation>(`/tutor/conversations/${id}`).then(r => r.data),

  deleteConversation: (id: number) =>
    api.delete(`/tutor/conversations/${id}`).then(r => r.data),
}

// ─── Quiz ─────────────────────────────────────────────────────
export const quizApi = {
  generate: (params: {
    document_id: number
    topic?: string
    difficulty?: string
    num_questions?: number
    question_types?: string[]
  }) => api.post('/quiz/generate', params).then(r => r.data),

  evaluate: (params: {
    quiz_id: string
    document_id?: number
    questions: QuizQuestion[]
    user_answers: Record<string, string>
  }) => api.post<QuizResult>('/quiz/evaluate', params).then(r => r.data),

  history: (limit = 20) =>
    api.get('/quiz/history', { params: { limit } }).then(r => r.data),
}

// ─── Analytics ────────────────────────────────────────────────
export const analyticsApi = {
  dashboard: () => api.get<DashboardStats>('/analytics/dashboard').then(r => r.data),

  mastery: () =>
    api.get<{ mastery: TopicMastery[] }>('/analytics/mastery').then(r => r.data),

  weakTopics: () =>
    api.get('/analytics/weak-topics').then(r => r.data),

  startRevision: (params: {
    topic?: string
    document_id?: number
    num_rounds?: number
  }) => api.post<RevisionSession>('/analytics/revision/start', params).then(r => r.data),

  completeRevision: (params: {
    session_id: number
    topic: string
    correct_answers: number
    total_questions: number
  }) => api.post('/analytics/revision/complete', params).then(r => r.data),

  modelInfo: () => api.get<ModelInfo>('/analytics/model-info').then(r => r.data),

  benchmark: () => api.get('/analytics/benchmark').then(r => r.data),

  runBenchmark: (iterations = 3) =>
    api.post<BenchmarkResult>('/analytics/benchmark/run', null, {
      params: { iterations },
      timeout: 300_000,
    }).then(r => r.data),
}

// ─── Health ───────────────────────────────────────────────────
export const healthApi = {
  check: () => api.get('/health').then(r => r.data),
}

export default api
