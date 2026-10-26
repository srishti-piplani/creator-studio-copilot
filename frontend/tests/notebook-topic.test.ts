import assert from 'node:assert/strict';
import { test } from 'node:test';
import { notebookTitle, topicTitle } from '../lib/storage.ts';
import type { ChatResponse, Message, SavedAnswer } from '../lib/types.ts';

const original = 'Why do I hear my voice twice while recording?';
const response: ChatResponse = { answer: 'Synthetic answer', intent: 'troubleshoot', session_id: 'test', citations: [], resource_cards: [], diagnostic_question: 'Is Direct Monitor ON or OFF?', troubleshooting_status: 'diagnosing', limitations: [] };
function turn(messages: Message[], question: string, result = response) {
  const title = topicTitle(question, messages, result.topic_title, result.new_topic);
  messages.push({ id: `u${messages.length}`, role: 'user', text: question, createdAt: '' });
  const answer: Message = { id: `a${messages.length}`, role: 'assistant', text: result.answer, question, response: result, topicTitle: title, createdAt: '' };
  messages.push(answer);
  return { id: answer.id, question, response: result, savedAt: '' } as SavedAnswer;
}

test('Save Answer inherits the original problem after ON, resolution and explanation', () => {
  const messages: Message[] = [];
  turn(messages, original);
  for (const reply of ["It's ON.", 'Yes', 'No', "I don't know", 'That fixed it.', 'Still happening', 'Can you explain why that helped?']) {
    const saved = turn(messages, reply, { ...response, topic_title: reply, new_topic: true });
    assert.equal(notebookTitle(saved, messages), original);
  }
});

test('a new topic owns subsequent answers; old answers retain their own topic after reopening', () => {
  const messages: Message[] = [];
  turn(messages, original);
  const old = turn(messages, "It's ON.");
  const next = 'How do I export a video?';
  const learn = { ...response, intent: 'learn' as const, new_topic: true, topic_title: next };
  assert.equal(notebookTitle(turn(messages, next, learn), messages), next);
  const followup = turn(messages, 'Can you explain it more simply?', { ...learn, new_topic: false });
  const reopened: Message[] = JSON.parse(JSON.stringify(messages));
  assert.equal(notebookTitle(followup, reopened), next);
  assert.equal(notebookTitle(old, reopened), original);
  assert.equal(notebookTitle(followup, reopened.slice(-2)), next); // Original turns can be pruned.
});

test('legacy conversations inherit topics; existing Notebook titles remain untouched', () => {
  const messages: Message[] = [];
  turn(messages, original);
  const saved = turn(messages, "It's ON.");
  const legacy = messages.map(message => { const copy = { ...message }; delete copy.topicTitle; return copy; });
  assert.equal(notebookTitle(saved, legacy), original);
  assert.equal(notebookTitle({ ...saved, title: 'My edited title' }, messages), 'My edited title');
  assert.equal(notebookTitle({ ...saved, title: "It's ON." }, messages), "It's ON.");
});


test('Discover follow-ups keep their resource-search topic', () => {
  const messages: Message[] = [];
  const question = 'Find beginner Logic Pro mixing tutorials.';
  const discover = { ...response, intent: 'discover' as const, diagnostic_question: null };
  turn(messages, question, discover);
  const saved = turn(messages, 'Can you show more options?', discover);
  assert.equal(notebookTitle(saved, messages), question);
});
