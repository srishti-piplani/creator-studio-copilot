'use client';
import { groupActivity } from '@/lib/activity';
import { Check, LoaderCircle, CircleAlert } from 'lucide-react';
import type { ProgressEvent } from '@/lib/chat-stream';

export function LiveActivity({ events, fallback }: { events: ProgressEvent[]; fallback: boolean }) {
  return <div className="live-activity" role="status" aria-live="polite" aria-label="Assistant activity">
    <div className="live-activity-heading"><LoaderCircle size={16} className="spin"/>{fallback ? 'Waiting for your answer…' : events.length ? 'Working on your request' : 'Connecting to your assistant…'}</div>
    {events.length > 0 && <ul>{groupActivity(events).map((event, index) => <li key={`${event.action}-${index}`} data-status={event.status}>{event.status === 'completed' ? <Check size={14}/> : event.status === 'failed' ? <CircleAlert size={14}/> : <LoaderCircle size={14} className="spin"/>}<span>{event.label}{event.count > 1 && ` · ${event.count} operations`}{event.failures > 0 && ` · ${event.failures} failed`}</span><small>{event.status === 'completed' ? event.failures ? 'Some checks unavailable' : 'Done' : event.status === 'failed' ? 'Unavailable' : 'In progress'}</small></li>)}</ul>}
    {fallback && <p>Live updates are unavailable. Your original request is still being checked.</p>}
  </div>;
}
