export interface Document {
  id: number
  filename: string
  file_type: string
  file_size: number
  upload_date: string | null
  processing_status: 'pending' | 'processing' | 'ready' | 'failed'
  page_count: number
  chunk_count: number
  error_message: string | null
  summary: string | null
  key_concepts: string[]
  topics: string[]
  privacy_note?: string
}

export interface SourceCitation {
  document: string
  page: number
  excerpt: string
  score: number
}

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
  sources?: SourceCitation[]
}

export interface Conversation {
  id: number
  title: string
  created_at: string | null
  updated_at: string | null
  messages?: Message[]
}

export interface AskResponse {
  answer: string
  sources: SourceCitation[]
  found_in_documents: boolean
  model: string
  provider: string
  latency_ms: number
  conversation_id: number | null
}

export interface QuizQuestion {
  id: number
  type: 'multiple_choice' | 'true_false' | 'short_answer'
  question: string
  options?: Record<string, string>
  correct_answer?: string
  explanation?: string
  topic: string
  difficulty: string
  user_answer?: string
  is_correct?: boolean
}

export interface QuizResult {
  quiz_id: string
  total_questions: number
  correct: number
  score_percent: number
  questions: QuizQuestion[]
  weak_topics: string[]
  strong_topics: string[]
  recommendations: string[]
}

export interface TopicMastery {
  topic: string
  score: number
  questions_attempted: number
  correct_answers: number
  last_studied: string | null
}

export interface DashboardStats {
  documents_uploaded: number
  topics_studied: number
  quiz_accuracy: number
  study_streak: number
  weak_topics: { topic: string; score: number; questions_attempted: number }[]
  recent_activity: { type: string; topic: string; is_correct: boolean; timestamp: string }[]
  total_questions_attempted: number
}

export interface ModelInfo {
  model: string
  provider: string
  backend: string
  device: string
  is_available: boolean
  supports_gpu: boolean
  supports_npu: boolean
  context_length: number
  embedding_dims: number
  metadata?: Record<string, unknown>
}

export interface BenchmarkResult {
  benchmark_id?: number
  run_at: string
  model: string
  backend: string
  device: string
  provider: string
  avg_embedding_latency_ms: number | null
  avg_generation_latency_ms: number | null
  avg_tokens_per_second: number | null
  memory_usage_mb: number | null
  iterations: number
  note: string
  raw_results?: unknown[]
  device_info?: Record<string, string>
}

export interface RevisionSession {
  session_id: number
  topic: string
  mastery_before: number
  explanation: string
  example: string
  questions: QuizQuestion[]
  sources: { document: string; page: number }[]
}
