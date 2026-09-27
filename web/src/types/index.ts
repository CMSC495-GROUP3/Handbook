export interface Message {
  role: 'user' | 'assistant'
  content: string
}

/**
 * Which check refused a turn. `no_match`: retrieval similarity missed the
 * threshold. `not_covered`: similarity cleared it but the coverage judge said
 * the passages do not answer the question. Absent on turns stored before #269.
 */
export type RefusalReason = 'no_match' | 'not_covered'

export interface ChatResponse {
  answer: string
  sources: string[]
  confidence: number | null
  follow_ups: string[]
  /** True when the grounding gate or the coverage judge refused and no answer was generated. */
  refused: boolean
  refusal_reason?: RefusalReason | null
  session_id: string | null
}

export interface Conversation {
  session_id: string
  title: string
  project_id: string | null
  updated_at: string
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
  created_at: string
}

export interface Project {
  project_id: string
  name: string
  created_at: string
}

/** One indexed policy document, as shown in the document library. */
export interface PolicyDocument {
  source: string
  doc_id: string
  title: string
  category: string | null
  owner: string | null
  effective_date: string | null
  passage_count: number
  preview: string
}

export interface DocumentsResponse {
  items: PolicyDocument[]
  total: number
}

/** One document's full markdown body, from GET /api/documents/body. */
export interface DocumentBody {
  source: string
  body: string
}

export type EscalationReason = 'refused' | 'unhelpful'
export type EscalationStatus = 'open' | 'resolved'

/** One hand-off of a question to a person. Mirrors the record in sourcebook/api/routes/escalations.py. */
export interface Escalation {
  escalation_id: string
  status: EscalationStatus
  reason: EscalationReason
  contact: string
  session_id: string
  message_index: number
  question: string
  answer_excerpt: string
  refused: boolean
  confidence: number | null
  sources: string[]
  note: string | null
  resolution: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null

  /** Computed per response: `not_configured` means no webhook and nothing was sent. */
  delivery_status: 'pending' | 'delivered' | 'failed' | 'not_configured'
  delivery_attempts: number
  delivery_last_attempt_at: string | null
  delivery_claimed_at: string | null
  /** True when the retry-delivery endpoint would send right now. */
  delivery_retryable: boolean
}

/** Another wording grouped under a question's most asked one. */
export interface OtherWording {
  question: string | null
  count: number
}

/** One question in the coverage report: wordings grouped by meaning (#287). */
export interface QuestionGroup {
  /** The most asked wording's hash, stable enough for a list key. */
  question_hash: string
  /** The most asked wording, or null when none was stored. */
  question: string | null
  /** Every ask across every wording, including one person asking again. */
  count: number
  /**
   * Distinct conversations across every wording; the closest the log gets to
   * people. A conversation that used two wordings counts once.
   */
  conversations: number
  /** Up to five other wordings, most asked first. */
  other_wordings: OtherWording[]
  /** Every other wording, including any not listed. */
  other_wording_count: number
}

export interface CoverageReport {
  since: string
  until: string
  days: number
  /** "exact" when grouping by meaning was unavailable and each wording is its own row. */
  grouping: 'meaning' | 'exact'
  /** Every chat request in the window. */
  total: number
  refused: number
  /** Refused questions, most frequent first. */
  gaps: QuestionGroup[]
  /** Questions asked at least twice, with how many of those asks were refused. */
  faq: (QuestionGroup & { refused: number })[]
}
