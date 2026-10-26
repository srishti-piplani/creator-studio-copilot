export type Intent = 'learn' | 'troubleshoot' | 'discover' | 'clarify';
export type Citation = {
  id: string; title?: string; source_type?: string; url?: string; source?: string;
  guide_title?: string; guide_path?: string; reference_urls?: string[]; sources?: Citation[];
};
export type Resource = { title: string; url: string; source: string; source_type?: string; description: string; license?: string; usage?: 'view' | 'reuse'; license_verified?: boolean; license_source_url?: string; published_at?: string | null };
export type ChatResponse = {
  answer: string; intent: Intent; session_id: string; citations: Citation[];
  diagnostic_question: string | null; resource_cards: Resource[];
  troubleshooting_status: string; limitations: string[];
  activities?: ResearchActivity[];
  topic_title?: string;
  new_topic?: boolean;
  evidence_evaluation?: { sufficient?: boolean; contradictory?: boolean; reason?: string };
};
export type DiagnosticStep = { action_key: string; text: string; outcome: string; user_report?: string };
export type Session = { session_id: string; messages: { role: string; content: string }[]; steps: DiagnosticStep[]; questions_asked: string[]; status: string; equipment: string[] };
export type Message = { id: string; role: 'user' | 'assistant'; text: string; response?: ChatResponse; question?: string; topicTitle?: string; createdAt: string };
export type SavedAnswer = { id: string; question: string; response: ChatResponse; savedAt: string; title?: string };
export type Setup = { microphone: 'Audio-Technica AT2020' | 'Audio-Technica AT2035' | null; audioInterface: 'Focusrite Scarlett Solo' | 'Focusrite Scarlett 2i2' | null };
export type Conversation = { id?: string; title?: string; createdAt?: string; updatedAt?: string; messages: Message[]; sessionId: string | null; steps: DiagnosticStep[]; draft: string };
export type ConversationRecord = Conversation & { id: string; title: string; createdAt: string; updatedAt: string };
export type ResearchActivity = { action: string; status: 'completed' | 'failed'; label: string; result_count?: number };
