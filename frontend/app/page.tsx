'use client';
import { StudioArt } from '@/components/studio-art';
import { useEffect, useRef, useState } from 'react';
import { ArrowUp, ArrowUpRight, AudioLines, GraduationCap, Check, Compass, Headphones, LoaderCircle, Plus, RotateCcw, Wrench, X } from 'lucide-react';
import { useStudio } from '@/components/studio-provider';
import { Button } from '@/components/ui/button';
import { LandingSetup } from '@/components/landing-setup';
import { topicTitle } from '@/lib/storage';
import { Answer } from '@/components/answer';
import { LiveActivity } from '@/components/live-activity';
import { sendChatWithProgress, type ProgressEvent } from '@/lib/chat-stream';
import { ApiError, getSession } from '@/lib/api';
import { setupEquipment } from '@/lib/storage';
import type { Conversation, Message } from '@/lib/types';
const modes = [
  { name: 'Learn', Icon: GraduationCap, className: 'learn', description: 'Understand creative tools and techniques.', prompts: ['What does a compressor do?', 'How do I add an audio track in Logic Pro?', "What's the difference between EQ and compression?"] },
  { name: 'Troubleshoot', Icon: Wrench, className: 'troubleshoot', description: "Fix something that's not working.", prompts: ["My Scarlett has input signal, but Logic isn't recording.", 'Why do I hear my voice twice while recording?', "My MIDI keyboard isn't producing sound."] },
  { name: 'Discover', Icon: Compass, className: 'discover', description: 'Find samples, tutorials, and creative resources.', prompts: ['Find free tabla loops for a music cover.', 'Find tutorials for vocal mixing in Logic Pro.', 'Find resources for learning color grading in Resolve.'] },
];
export default function AssistantPage() {
  const { landing, ready, setup, conversation, setConversation, startConversation, busy, setBusy } = useStudio();
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [failedMessage, setFailedMessage] = useState<string | null>(null);
  const [sessionWarning, setSessionWarning] = useState<string | null>(null);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [progressFallback, setProgressFallback] = useState(false);
  const requestId = useRef<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const checkedSession = useRef<string | null>(null);
  const flight = useRef(false);
  const state = useRef(conversation);
  const update = useRef(setConversation);
  // Keep async completions current even while another page is open or the draft changes.
  useEffect(() => { state.current = conversation; update.current = setConversation; }, [conversation, setConversation]);
  useEffect(() => { if (conversation.messages.length) end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [conversation.messages.length, busy, progress.length]);
  useEffect(() => {
    if (!ready || !conversation.sessionId || checkedSession.current === conversation.sessionId) return;
    checkedSession.current = conversation.sessionId;
    let active = true;
    getSession(conversation.sessionId).then(session => {
      if (active) update.current({ ...state.current, steps: session.steps });
    }).catch(err => {
      if (!active) return;
      if (err instanceof ApiError && err.status === 404) setExpired(true);
      else setSessionWarning('Your conversation is saved in this browser. Live session details could not be checked; you can retry your request.');
    });
    return () => { active = false; };
  }, [ready, conversation.sessionId, conversation.id]);
  function prefill(value: string) { setConversation({ ...conversation, draft: value }); composer.current?.focus(); }
  async function send(value: string, retry = false) {
    const message = value.trim();
    if (!message || flight.current || busy || expired || message.length > 4000) return;
    flight.current = true; setBusy(true); setError(null); setFailedMessage(null); setSessionWarning(null);
    setProgress([]); setProgressFallback(false);
    if (!retry || !requestId.current) requestId.current = crypto.randomUUID();
    const snapshot = state.current;
    const messages: Message[] = retry ? snapshot.messages : [...snapshot.messages, { id: crypto.randomUUID(), role: 'user', text: message, createdAt: new Date().toISOString() }];
    const pending: Conversation = { ...snapshot, messages, draft: '' };
    state.current = pending; update.current(pending);
    try {
      const result = await sendChatWithProgress(message, snapshot.sessionId, setupEquipment(setup, message), {
        requestId: requestId.current,
        onProgress: event => setProgress(previous => {
          return [...previous, event];
        }),
        onFallback: () => setProgressFallback(true),
      });
      const next: Conversation = { ...state.current, sessionId: result.session_id, messages: [...messages, { id: crypto.randomUUID(), role: 'assistant', text: result.answer, question: message, topicTitle: topicTitle(message, snapshot.messages, result.topic_title, result.new_topic), response: result, createdAt: new Date().toISOString() }] };
      state.current = next; update.current(next); checkedSession.current = result.session_id;
      try { const details = await getSession(result.session_id); update.current({ ...state.current, steps: details.steps }); }
      catch { setSessionWarning('The answer arrived, but the diagnostic history could not be refreshed.'); }
    } catch (err) {
      // A terminal server error is safe to retry as new work. Transport errors
      // retain the ID because the original job may still be running.
      if (err instanceof ApiError && err.status > 0) requestId.current = null;
      setFailedMessage(message); setError(err instanceof Error ? err.message : 'Something went wrong. Please retry.');
      if (err instanceof ApiError && err.status === 404) setExpired(true);
    } finally { flight.current = false; setBusy(false); composer.current?.focus(); }
  }
  function newConversation() {
    if (busy) return;
    requestId.current = null; setProgress([]); setProgressFallback(false);
    const empty = startConversation();
    state.current = empty; setExpired(false); setError(null); setFailedMessage(null); setSessionWarning(null); checkedSession.current = null; setSelected(null);
  }
  function chooseMode(index: number) {
    if (busy) return;
    newConversation();
    setSelected(index);
    composer.current?.focus();
  }
  const started = conversation.messages.length > 0 && !landing;
  useEffect(() => {
    // Switching stored threads resets view-only errors and rechecks live state.
    checkedSession.current = null;
    queueMicrotask(() => { setExpired(false); setError(null); setFailedMessage(null); setSessionWarning(null); });
  }, [conversation.id]);
  const latest = conversation.messages.at(-1);
  return <section className={`assistant-workspace ${started ? 'conversation-active' : ''}`}>
    <div className="workspace-heading"><span className="eyebrow"><span className="status-dot"/> YOUR STUDIO, WITH A LITTLE GUIDANCE</span><Button variant="outline" size="sm" onClick={newConversation} disabled={busy || conversation.messages.length === 0}><Plus size={15}/> New conversation</Button></div>
    {!started && <div className="welcome"><div className="welcome-mark"><AudioLines size={29}/></div><div className="eyebrow welcome-eyebrow">LESS FRICTION. MORE CREATION.</div><h1>What would you like<br className="desktop-break"/> to work on?</h1><p className="welcome-subtitle">Get expert guidance for your creative workflow, solve studio problems, or discover new ideas.</p><div className="mode-grid">{modes.map(({ name, Icon, className, description }, i) => <button className={`mode-card ${className} ${selected === i ? 'selected' : ''}`} key={name} onClick={() => chooseMode(i)} aria-expanded={selected === i}><span className="mode-card-top"><StudioArt kind={className}/><span className="mode-icon"><Icon size={23} strokeWidth={1.7}/></span><ArrowUpRight size={18}/></span><h2>{name}</h2><p>{description}</p><span className="mode-card-footer">A starting point for your next idea <span>↗</span></span></button>)}</div>
      {selected !== null && <div className="prompt-tray"><div><span className="eyebrow">TRY A QUESTION · {modes[selected].name.toUpperCase()}</span><Button variant="ghost" size="icon" onClick={() => setSelected(null)} aria-label="Close example prompts"><X size={15}/></Button></div>{modes[selected].prompts.map(prompt => <button key={prompt} onClick={() => prefill(prompt)}>{prompt}<ArrowUpRight size={15}/></button>)}</div>}
    </div>}
    {!started && <LandingSetup/>}
    {started && <div className="messages" aria-label="Conversation" aria-live="polite">{conversation.messages.map(message => <article className={`message message-${message.role}`} key={message.id}>{message.role === 'user' ? <><div className="message-avatar user-avatar">YOU</div><div className="user-message"><span className="message-label">You</span><p>{message.text}</p></div></> : <><div className="message-avatar assistant-avatar"><AudioLines size={19}/></div><div className="assistant-message"><div className="message-title"><strong>Studio Copilot</strong><span className={`intent-label ${message.response?.intent}`}>{message.response?.intent || 'Assistant'}</span></div>{message.response && <Answer response={message.response} question={message.question || ''} title={message.topicTitle || topicTitle(message.question || '', conversation.messages.slice(0, conversation.messages.indexOf(message)), message.response.topic_title, message.response.new_topic)} entryId={message.id}/>}</div></>}</article>)}
      {busy && <LiveActivity events={progress} fallback={progressFallback}/>}
      </div>}
    {!landing && conversation.steps.length > 0 && <details className="diagnostic-history"><summary><Wrench size={15}/> Troubleshooting history <span>{conversation.steps.length} attempted {conversation.steps.length === 1 ? 'step' : 'steps'}</span></summary><ol>{conversation.steps.map((step, i) => <li key={`${step.action_key}-${i}`}><span className={`step-outcome ${step.outcome}`}>{step.outcome === 'resolved' ? <Check size={14}/> : step.outcome === 'failed' ? <X size={14}/> : <span>{i + 1}</span>}</span><div><p>{step.text}</p><small>{step.outcome === 'pending' ? 'Waiting for your result' : step.outcome === 'failed' ? "Didn't resolve the issue" : 'Reported resolved'}</small></div></li>)}</ol></details>}
    {expired && <div className="error-banner" role="alert"><strong>This session has expired.</strong><p>The backend may have restarted. Start a new conversation to continue. Your Notebook entries are still saved locally.</p><Button variant="outline" size="sm" onClick={newConversation}>Start new conversation</Button></div>}
    {error && !expired && <div className="error-banner" role="alert"><p>{error}</p>{failedMessage && <Button variant="outline" size="sm" disabled={busy} onClick={() => send(failedMessage, true)}><RotateCcw size={14}/> Retry message</Button>}<small>A retry resends the request. If the previous request completed after a connection error, the backend may have already processed it.</small></div>}
    {sessionWarning && <p role="status" className="evidence-note">{sessionWarning}</p>}
    <div className="composer-zone">{!landing && latest?.response?.intent === 'troubleshoot' && latest.response.troubleshooting_status === 'awaiting_outcome' && !busy && !expired && !failedMessage && <div className="outcome-actions"><span>How did that go?</span><Button variant="outline" size="sm" onClick={() => send('That worked. The problem is resolved.')}><Check size={14}/> That worked</Button><Button variant="outline" size="sm" onClick={() => send("That didn't work.")}>That didn&apos;t work</Button></div>}
      <form className="composer" onSubmit={e => { e.preventDefault(); send(conversation.draft); }}><label className="sr-only" htmlFor="message">Ask your studio assistant</label><textarea id="message" ref={composer} value={conversation.draft} onChange={e => setConversation({ ...conversation, draft: e.target.value })} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(conversation.draft); } }} maxLength={4000} rows={2} placeholder="What's on your mind? Ask anything about your studio…" disabled={!ready || busy || expired || !!failedMessage}/><div className="composer-bottom"><span><Headphones size={14}/> {setup.microphone || setup.audioInterface ? 'Using My Studio Setup' : 'Your ideas. Your tools. Your pace.'}</span><div><span className="keyboard-hint">↵ to send</span><Button type="submit" size="icon" aria-label="Send message" disabled={!ready || busy || expired || !!failedMessage || !conversation.draft.trim()}>{busy ? <LoaderCircle size={18} className="spin"/> : <ArrowUp size={19}/>}</Button></div></div></form>
      {failedMessage && !expired && <Button variant="ghost" size="sm" onClick={() => { setError(null); setFailedMessage(null); setConversation({ ...conversation, messages: conversation.messages.at(-1)?.role === 'user' ? conversation.messages.slice(0, -1) : conversation.messages, draft: failedMessage }); }}>Edit the failed question instead</Button>}
      <p className="composer-disclaimer">AI guidance can be imperfect. Check sources and confirm settings before making changes.</p></div>
    {started && <div ref={end} className="conversation-end"/>}
    {!started && <div className="suggested-questions" aria-label="Suggested questions">{['How do I add a track in Logic Pro?', 'Why do I hear my voice twice?', 'How do I make vocals sound warmer?', 'Find royalty-free percussion samples.'].map(prompt => <button key={prompt} onClick={() => prefill(prompt)}>{prompt}<ArrowUpRight size={14}/></button>)}</div>}
    {!started && <div className="welcome-bottom"><span className="tiny-rule"/> MADE FOR THE MOMENT BETWEEN AN IDEA AND MAKING IT HAPPEN <span className="tiny-rule"/></div>}
  </section>;
}
