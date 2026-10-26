import { ApiError, parseChatResponse, sendChat } from './api.ts';
import type { ChatResponse } from './types';

export type ProgressEvent = { action: string; label: string; status: 'started' | 'completed' | 'failed' };
type Options = { requestId?: string; onProgress: (event: ProgressEvent) => void; onFallback?: () => void };
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '');

/** Fetch supports POST SSE; EventSource cannot send the existing JSON chat body. */
export async function sendChatWithProgress(message: string, sessionId: string | null, equipment: string[], options: Options): Promise<ChatResponse> {
  const requestId = options.requestId || crypto.randomUUID();
  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    const response = await fetch(`${BASE}/chat/stream`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ message, request_id: requestId, ...(sessionId ? { session_id: sessionId } : {}), ...(equipment.length ? { equipment } : {}) }),
      signal: AbortSignal.timeout(240_000), cache: 'no-store',
    });
    if ([404, 405, 501].includes(response.status)) throw new Error('Streaming endpoint unavailable');
    if (!response.ok) throw new ApiError('The assistant could not complete this request. Please retry.', response.status);
    if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) throw new Error('Streaming unavailable');
    reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    for (;;) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      // Accept CRLF boundaries too; do not alter JSON payload strings.
      buffer = buffer.replace(/\r\n/g, '\n');
      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
        const lines = frame.split('\n');
        const event = lines.find(line => line.startsWith('event:'))?.slice(6).trim();
        const data = lines.filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (!event || !data) continue; // Includes transport keepalive comments.
        const payload = JSON.parse(data);
        if (event === 'progress') {
          if (typeof payload.action !== 'string' || typeof payload.label !== 'string' || !['started', 'completed', 'failed'].includes(payload.status)) throw new Error('Invalid progress event');
          options.onProgress(payload as ProgressEvent);
        } else if (event === 'final') {
          return parseChatResponse(payload);
        } else if (event === 'error') {
          throw new ApiError(typeof payload.message === 'string' ? payload.message : 'Assistant unavailable', Number(payload.status) || 503);
        }
      }
      if (done) throw new Error('Stream ended before a final response');
    }
  } catch (error) {
    // Application errors (e.g. expired session) are not silently retried.
    if (error instanceof ApiError && error.status > 0) throw error;
    options.onFallback?.();
    // Same ID joins the original job, including after partial progress delivery.
    return sendChat(message, sessionId, equipment, requestId);
  } finally {
    await reader?.cancel().catch(() => {});
  }
}
