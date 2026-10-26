'use client';
import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { KEYS, validSetup, DEFAULT_SETUP, boundHistory, notebookTitle, conversationTitle } from '@/lib/storage';
import type { Conversation, ConversationRecord, SavedAnswer, Setup } from '@/lib/types';
const blank = (): Conversation => ({ messages: [], sessionId: null, steps: [], draft: '' });
function fresh(): ConversationRecord {
  const now = new Date().toISOString();
  return { ...blank(), id: crypto.randomUUID(), title: 'New conversation', createdAt: now, updatedAt: now };
}
type StudioContext = {
  landing: boolean; showLanding: () => void; ready: boolean; notebook: SavedAnswer[]; setup: Setup; conversation: Conversation;
  history: ConversationRecord[]; startConversation: () => ConversationRecord;
  openConversation: (id: string) => void; deleteConversation: (id: string) => void;
  setConversation: (value: Conversation) => void; saveAnswer: (value: SavedAnswer) => void;
  renameAnswer: (id: string, title: string) => void; removeAnswer: (id: string) => void;
  saveSetup: (value: Setup) => boolean; storageError: string | null;
  busy: boolean; setBusy: (value: boolean) => void;
};
const Context = createContext<StudioContext | null>(null);
export function StudioProvider({ children }: { children: React.ReactNode }) {
  const [landing, setLanding] = useState(false);
  const [ready, setReady] = useState(false);
  const [notebook, setNotebook] = useState<SavedAnswer[]>([]);
  const [setup, setSetup] = useState<Setup>(DEFAULT_SETUP);
  const [conversation, setCurrent] = useState<Conversation>(blank);
  const [history, setHistory] = useState<ConversationRecord[]>([]);
  const [storageError, setStorageError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const records = useRef<ConversationRecord[]>([]);
  const active = useRef<ConversationRecord | null>(null);
  const loaded = useRef(false);
  function persist(key: string, value: unknown) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch { setStorageError('Browser storage is unavailable or full. Recent changes may not survive a refresh.'); return false; }
  }
  /* eslint-disable react-hooks/set-state-in-effect -- Hydrate browser-only storage after SSR, keeping the initial render consistent. */
  useEffect(() => {
    if (loaded.current) return;
    loaded.current = true;
    let restored: ConversationRecord[] = [];
    let current = fresh();
    try {
      const read = (key: string) => JSON.parse(localStorage.getItem(key) || 'null');
      const storedSetup = localStorage.getItem(KEYS.setup);
      // Absence means new user. An explicitly saved null selection stays cleared.
      setSetup(storedSetup === null ? DEFAULT_SETUP : validSetup(JSON.parse(storedSetup)));
      const storedHistory = read(KEYS.history);
      if (Array.isArray(storedHistory)) restored = storedHistory.filter(r => r && typeof r.id === 'string' && typeof r.updatedAt === 'string' && Array.isArray(r.messages) && Array.isArray(r.steps));
      const legacy = read(KEYS.conversation);
      if (!restored.length && legacy && Array.isArray(legacy.messages) && Array.isArray(legacy.steps)) {
        current = { ...current, ...legacy, id: current.id,
          title: conversationTitle(legacy.messages) };
        if (current.messages.length) restored = [current];
      }
      const activeId = read(KEYS.active);
      current = typeof activeId === 'string' ? restored.find(r => r.id === activeId) || current : restored[0] || current;
      const saved = read(KEYS.notebook);
      if (Array.isArray(saved)) setNotebook(saved.filter(v => v && typeof v.id === 'string' && typeof v.question === 'string' && v.response && typeof v.response.answer === 'string' && Array.isArray(v.response.citations) && Array.isArray(v.response.resource_cards)).map(v => {
        const thread = restored.find(r => r.messages.some(m => m.id === v.id));
        return { ...v, title: notebookTitle(v, thread?.messages || []) };
      }));
      restored = boundHistory(restored);
      if (persist(KEYS.history, restored)) localStorage.removeItem(KEYS.conversation);
    } catch { setStorageError('Some browser data could not be read. Existing stored entries have not been cleared.'); }
    records.current = restored; active.current = current;
    setHistory(restored); setCurrent(current); setReady(true);
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */
  function storeHistory(next: ConversationRecord[]) {
    const bounded = boundHistory(next);
    records.current = bounded; setHistory(bounded); persist(KEYS.history, bounded);
  }
  function setConversation(value: Conversation) {
    if (value.messages.length > (active.current?.messages.length || 0)) setLanding(false);
    const base = records.current.find(r => r.id === value.id) || active.current || fresh();
    const updated = { ...base, ...value, id: value.id || base.id, updatedAt: new Date().toISOString() };
    if (base.title === 'New conversation' && updated.messages.length) {
      updated.title = conversationTitle(updated.messages);
    }
    // In-flight work updates its own thread; it cannot overwrite another active one.
    if (!active.current || updated.id === active.current.id) {
      active.current = updated; setCurrent(updated); persist(KEYS.active, updated.id);
    }
    storeHistory([...records.current.filter(r => r.id !== updated.id), updated]);
  }
  function startConversation() {
    setLanding(false);
    const next = fresh(); active.current = next; setCurrent(next); persist(KEYS.active, next.id); return next;
  }
  function openConversation(id: string) {
    if (busy) return;
    const next = records.current.find(r => r.id === id);
    if (next) { setLanding(false); active.current = next; setCurrent(next); persist(KEYS.active, next.id); }
  }
  function deleteConversation(id: string) {
    if (busy) return;
    storeHistory(records.current.filter(r => r.id !== id));
    if (active.current?.id === id) startConversation();
  }
  function saveAnswer(value: SavedAnswer) {
    if (notebook.some(n => n.id === value.id)) return;
    const title = notebookTitle(value, active.current?.messages || []);
    const next = [{ ...value, title }, ...notebook]; setNotebook(next); persist(KEYS.notebook, next);
  }
  function renameAnswer(id: string, title: string) {
    if (!title.trim()) return;
    const next = notebook.map(n => n.id === id ? { ...n, title: title.trim().slice(0, 180) } : n);
    setNotebook(next); persist(KEYS.notebook, next);
  }
  function removeAnswer(id: string) { const next = notebook.filter(n => n.id !== id); setNotebook(next); persist(KEYS.notebook, next); }
  function saveSetup(value: Setup) { setSetup(value); return persist(KEYS.setup, value); }
  return <Context.Provider value={{ landing, showLanding: () => setLanding(true), ready, notebook, setup, conversation, history, startConversation, openConversation, deleteConversation, setConversation, saveAnswer, renameAnswer, removeAnswer, saveSetup, storageError, busy, setBusy }}>{children}</Context.Provider>;
}
export function useStudio() { const value = useContext(Context); if (!value) throw new Error('StudioProvider is required'); return value; }
