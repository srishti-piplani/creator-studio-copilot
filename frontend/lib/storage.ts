import type { Setup, Message, ConversationRecord, SavedAnswer } from './types';
export const KEYS = { notebook: 'creator-studio:notebook:v1', setup: 'creator-studio:setup:v1', conversation: 'creator-studio:conversation:v1', history: 'creator-studio:history:v1', active: 'creator-studio:active:v1' };
export const DEFAULT_SETUP: Setup = { microphone: 'Audio-Technica AT2035', audioInterface: 'Focusrite Scarlett 2i2' };
export const EMPTY_SETUP: Setup = { microphone: null, audioInterface: null };
export function validSetup(value: unknown): Setup {
  if (!value || typeof value !== 'object') return EMPTY_SETUP;
  const row = value as Setup;
  return { microphone: ['Audio-Technica AT2020', 'Audio-Technica AT2035'].includes(row.microphone || '') ? row.microphone : null,
    audioInterface: ['Focusrite Scarlett Solo', 'Focusrite Scarlett 2i2'].includes(row.audioInterface || '') ? row.audioInterface : null };
}
export function setupEquipment(setup: Setup, message: string): string[] {
  // Explicit mentions override the saved default in the same hardware category.
  // Other equipment remains intact; the backend still classifies the user's intent.
  const mentionedMic = message.match(/\bAT[ -]?(2020|2035)\b/i)?.[1];
  const mic = mentionedMic && !setup.microphone?.includes(mentionedMic) ? null : setup.microphone;
  const otherInterface = (/(?:\bsolo\b)/i.test(message) && setup.audioInterface?.includes('2i2')) || (/\b2i2\b/i.test(message) && setup.audioInterface?.includes('Solo'));
  const differentGeneration = setup.audioInterface?.includes('2i2') ? /\b(?:3rd|4th)\s+gen/i.test(message) : /\b(?:1st|2nd|3rd)\s+gen/i.test(message);
  const iface = otherInterface || differentGeneration ? null : setup.audioInterface;
  const software = [
    'Logic Pro (documentation reference 12.3; installed version unknown)',
    'DaVinci Resolve (documentation reference 21.1; installed version unknown)',
  ];
  return [...software, mic, iface === 'Focusrite Scarlett Solo' ? 'Focusrite Scarlett Solo — 4th Gen' : iface === 'Focusrite Scarlett 2i2' ? 'Focusrite Scarlett 2i2 — 2nd Gen' : null].filter((v): v is string => !!v);
}
export function safeUrl(value?: string): string | undefined {
  if (!value) return;
  try { const url = new URL(value); if (['http:', 'https:'].includes(url.protocol) && !url.username && !url.password) return url.href; } catch { /* non-web citation */ }
}

export function isClarificationReply(question: string): boolean {
  const reply = question.trim().replace(/’/g, "'");
  if (/^(?:(?:yes[, ]+)?(?:it(?:'s| is)|the switch is) (?:on|off|enabled|disabled)|on|off|enabled|disabled|i don.t know|i.?m not sure|not sure|that fixed it|still happening|still doubled)[.! ]*$/i.test(reply)) return true;
  return /^(?:(?:logic pro|davinci resolve|usb(?:[- ][abc])?|thunderbolt|yes|no|yeah|nope|ok|okay|that (?:did not|didn.t) work|that worked|scarlett (?:2i2|solo)(?:[ ,—-]*(?:2nd|4th) gen)?|(?:audio-technica )?at20(?:20|35))[\s,./!?—-]*)+$/i.test(question.trim());
}

/** Presentation titles only; intent and topic routing remain on the backend. */
export function isFollowUp(question: string): boolean {
  if (isClarificationReply(question)) return true;
  return /^(?:(?:hi|hello|hey|help|thanks)[!.? ]*$|can you (?:explain|simplify|elaborate|show|make)|(?:please )?(?:explain (?:it|that|this)|simplify|more simply|that |it |this |yes\b|no\b|thanks\b|what (?:about|next)|how (?:about|so)|why is that|tell me more))/i.test(question.trim());
}
export function topicTitle(question: string, messages: Message[] = [], backendTopic?: string, newTopic = false): string {
  const previous = [...messages].reverse().find(m => m.role === 'assistant');
  const diagnosticAnswer = !newTopic && previous?.response?.intent === 'troubleshoot'
    && previous.response.diagnostic_question
    && !/^(?:how|why|what|where|when|can|could|find|explain|help)\b/i.test(question.trim());
  if (!isFollowUp(question) && !diagnosticAnswer) return question.trim().slice(0, 180);
  if (!isClarificationReply(question) && newTopic && backendTopic?.trim() && !isFollowUp(backendTopic)) return backendTopic.trim().slice(0, 180);
  const prior = [...messages].reverse().find(m => m.role === 'user' && !isFollowUp(m.text));
  return (previous?.topicTitle || prior?.text || (backendTopic && !isFollowUp(backendTopic) ? backendTopic : undefined) || 'Studio conversation').trim().slice(0, 180);
}
/** Save against the selected answer's topic, never the thread's latest turn. */
export function notebookTitle(value: SavedAnswer, messages: Message[] = []): string {
  if (value.title) return value.title; // Existing and manually edited titles are authoritative.
  const index = messages.findIndex(message => message.id === value.id);
  const answer = index >= 0 ? messages[index] : undefined;
  return answer?.topicTitle || topicTitle(value.question,
    index >= 0 ? messages.slice(0, index) : messages,
    value.response.topic_title, value.response.new_topic);
}

export const HISTORY_LIMIT = 20;
export const MESSAGE_LIMIT = 80;
export const HISTORY_CHAR_LIMIT = 1_000_000;
export function boundHistory(records: ConversationRecord[]): ConversationRecord[] {
  const unique = [...new Map(records.map(r => [r.id, r])).values()];
  const bounded = unique.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)).slice(0, HISTORY_LIMIT)
    .map(r => ({ ...r, messages: r.messages.slice(-MESSAGE_LIMIT), steps: r.steps.slice(-40), draft: r.draft.slice(0, 4000) }));
  while (JSON.stringify(bounded).length > HISTORY_CHAR_LIMIT && bounded.length > 1) bounded.pop();
  while (JSON.stringify(bounded).length > HISTORY_CHAR_LIMIT && bounded[0]?.messages.length) {
    bounded[0].messages = bounded[0].messages.slice(2);
  }
  return bounded;
}

export function conversationTitle(messages: Message[]): string {
  const substantive = messages.find(m => m.role === 'user' && !isFollowUp(m.text));
  return substantive ? substantive.text.trim().slice(0, 180) : 'New conversation';
}
