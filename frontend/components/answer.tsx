'use client';
import { useId } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ArrowUpRight, Bookmark, Check, Globe2, LibraryBig, ExternalLink, ShieldCheck } from 'lucide-react';
import type { ChatResponse, Citation } from '@/lib/types';
import { resourceLicenseLabel } from '@/lib/resources';
import { safeUrl } from '@/lib/storage';
import { Button } from './ui/button';
import { useStudio } from './studio-provider';

export function WebLink({ href, children, className }: { href?: string; children: React.ReactNode; className?: string }) {
  const url = safeUrl(href);
  return url ? <a href={url} target="_blank" rel="noopener noreferrer" className={className}>{children}</a> : <span className={className}>{children}</span>;
}
function Source({ citation }: { citation: Citation }) {
  const knowledge = citation.source_type === 'original_studio_knowledge' || !!citation.sources;
  return <><div className="source-heading">{knowledge ? <LibraryBig size={15}/> : <Globe2 size={15}/>}<span className="source-id">{citation.id}</span><strong>{citation.title || citation.guide_title || 'Source reference'}</strong><span className="tag">{knowledge ? 'Studio Knowledge' : citation.source_type === 'official' ? 'Official · live web' : 'Community · live web'}</span></div>
    {citation.url && <WebLink href={citation.url} className="source-url">{citation.source || citation.url} <ExternalLink size={12}/></WebLink>}
    {citation.sources?.map((source, i) => <div className="guide-reference" key={`${source.id}-${i}`}><strong>{source.guide_title || source.title}</strong><span>Original Studio guide</span>{source.reference_urls?.map((url, n) => <WebLink key={url} href={url}>Reference {n + 1} <ArrowUpRight size={12}/></WebLink>)}</div>)}
    {citation.reference_urls?.map((url, i) => <WebLink key={url} href={url}>Reference {i + 1} <ArrowUpRight size={12}/></WebLink>)}
  </>;
}
export function Answer({ response, question, title, entryId, savedView = false }: { response: ChatResponse; question: string; title?: string; entryId: string; savedView?: boolean }) {
  const { notebook, saveAnswer } = useStudio();
  const prefix = useId().replace(/:/g, '');
  const saved = notebook.some(n => n.id === entryId);
  const text = response.answer.replace(/\[([KW]\d+)\]/g, (match, id) => response.citations.some(c => c.id === id) ? `[${id}](#${prefix}-${id})` : match);
  return <div className={`answer-content answer-${response.intent} status-${response.troubleshooting_status}`}>
    <div className="prose">{response.intent === 'troubleshoot' && response.troubleshooting_status === 'awaiting_outcome' && <strong>Try this next</strong>}<ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: ({ href, children }) => href?.startsWith(`#${prefix}-`) ? <a href={href} className="inline-citation" onClick={() => { const details = document.getElementById(href.slice(1))?.closest('details'); if (details) details.open = true; }}>{children}</a> : <WebLink href={href}>{children}</WebLink> }}>{text}</ReactMarkdown></div>
    {response.diagnostic_question && !response.answer.includes(response.diagnostic_question) && <div className="diagnostic-question"><strong>Next question</strong><p>{response.diagnostic_question}</p></div>}
    {response.troubleshooting_status === 'unsupported' && <div className="evidence-note">More context or stronger evidence is needed before continuing.</div>}
    {response.evidence_evaluation?.contradictory && <div role="note" className="evidence-note">The available sources conflict. Treat this as a limitation, not a verified fix.</div>}
    {response.limitations?.map((value, i) => <p className="evidence-note" key={i}>{value}</p>)}
    {response.resource_cards.length > 0 && <div className="resource-grid">{response.resource_cards.map((resource, i) => <article className="resource-card" key={`${resource.url}-${i}`}><div className="resource-top"><span className="tag">{resource.source_type === 'official' ? <ShieldCheck size={12}/> : <Globe2 size={12}/>} {resource.source_type === 'official' ? 'Official' : 'Community'}</span><ArrowUpRight size={17}/></div><h3><WebLink href={resource.url}>{resource.title}</WebLink></h3><p>{resource.description || 'Open the source to read more about this resource.'}</p><WebLink href={resource.url} className="resource-domain">{resource.source}</WebLink>{resourceLicenseLabel(resource, question) && <div className="license"><WebLink href={resource.license_verified ? resource.license_source_url || resource.url : resource.url}>{resourceLicenseLabel(resource, question)}</WebLink></div>}</article>)}</div>}
    {response.citations.length > 0 && <details className="sources"><summary><LibraryBig size={15}/> Sources & references <span>{response.citations.length}</span></summary><div className="source-list">{response.citations.map((citation, i) => <div tabIndex={-1} className="source-item" id={`${prefix}-${citation.id}`} key={`${citation.id}-${i}`}><Source citation={citation}/></div>)}</div></details>}
    {response.activities && response.activities.length > 0 && <details className="research-panel"><summary><Globe2 size={16}/> How I researched this</summary><ul>{response.activities.map((activity, index) => <li key={`${activity.action}-${index}`}><span className={`activity-status ${activity.status}`}>{activity.status === 'completed' ? <Check size={14}/> : '!'}</span><span>{activity.label}{typeof activity.result_count === 'number' && <small> · {activity.result_count} results</small>}</span></li>)}</ul><p>Actions taken for this answer. Automated checks can miss factual errors.</p></details>}
    {!savedView && <div className="answer-actions"><Button variant="ghost" size="sm" onClick={() => saveAnswer({ id: entryId, question, title, response, savedAt: new Date().toISOString() })} disabled={saved}>{saved ? <Check size={15}/> : <Bookmark size={15}/>} {saved ? 'Saved to Notebook' : 'Save Answer'}</Button><span>Grounded guidance. Always listen and verify.</span></div>}
  </div>;
}
