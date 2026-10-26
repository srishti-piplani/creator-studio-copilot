import type { ChatResponse, Session } from './types';
export class ApiError extends Error {
  status: number;
  constructor(message: string, status = 0) { super(message); this.status = status; }
}
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
async function request(path: string, init?: RequestInit): Promise<unknown> {
  try {
    const res = await fetch(`${BASE}${path}`, { ...init, signal: AbortSignal.timeout(240_000), cache: 'no-store', headers: { 'Content-Type': 'application/json', ...init?.headers } });
    if (!res.ok) {
      throw new ApiError(res.status === 404 ? 'This session is no longer available. The backend may have restarted.' : res.status === 503 ? 'The assistant is temporarily unavailable. Please try again.' : `The request could not be completed (HTTP ${res.status}).`, res.status);
    }
    return await res.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError('Could not reach the studio assistant. Check that FastAPI is running at the configured API URL, then retry.');
  }
}
export function parseChatResponse(input: unknown): ChatResponse {
  const value = input as ChatResponse;
  if (!value || typeof value.answer !== 'string' || typeof value.session_id !== 'string' || !['learn', 'troubleshoot', 'discover', 'clarify'].includes(value.intent) || !Array.isArray(value.citations) || !Array.isArray(value.resource_cards)) throw new ApiError('The backend returned an unexpected response. Please retry.');
  return value;
}
export async function sendChat(message: string, sessionId: string | null, equipment: string[], requestId?: string): Promise<ChatResponse> {
  const value = await request('/chat', { method: 'POST', body: JSON.stringify({ message, ...(requestId ? { request_id: requestId } : {}), ...(sessionId ? { session_id: sessionId } : {}), ...(equipment.length ? { equipment } : {}) }) }) as ChatResponse;
  return parseChatResponse(value);
}
export async function getSession(id: string): Promise<Session> {
  const value = await request(`/sessions/${encodeURIComponent(id)}`) as Session;
  if (!value || value.session_id !== id || !Array.isArray(value.steps)) throw new ApiError('Session details could not be read.');
  return value;
}
