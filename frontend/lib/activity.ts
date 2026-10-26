import type { ProgressEvent } from './chat-stream.ts';
/** Presentation only: callers retain the unmodified transport events. Failures remain visible. */
export function groupActivity(events: ProgressEvent[]) {
  const groups: (ProgressEvent & { count: number; failures: number })[] = [];
  for (const event of events) {
    let group = groups.find(g => g.action === event.action);
    if (!group) { group = { ...event, count: 0, failures: 0 }; groups.push(group); }
    if (event.status === 'started') group.count++;
    if (event.status === 'failed') group.failures++;
    group.status = event.status;
    group.label = event.label;
  }
  return groups;
}
