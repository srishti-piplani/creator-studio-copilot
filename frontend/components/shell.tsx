'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Plus, AudioLines, BookOpen, Headphones, MessageSquare, ArrowUpRight, SlidersHorizontal, Trash2, MessageCircle } from 'lucide-react';
import { useStudio } from './studio-provider';
const navigation = [ { href: '/', label: 'Studio Assistant', Icon: MessageSquare }, { href: '/notebook', label: 'My Studio Notebook', Icon: BookOpen }, { href: '/setup', label: 'My Studio Setup', Icon: SlidersHorizontal, Trash2, MessageCircle } ];
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const { notebook, setup, storageError, history, conversation, openConversation, deleteConversation, busy, startConversation, showLanding } = useStudio();
  return <div className="app-shell">
    <a className="skip-link" href="#main">Skip to workspace</a>
    <aside className="sidebar">
      <Link className="brand" href="/" onClick={showLanding} aria-label="Creator Studio Copilot home"><span className="brand-icon"><AudioLines size={24}/></span><span>Creator Studio<span className="brand-caption">C O P I L O T</span></span></Link>
      <div className="sidebar-label">YOUR CREATIVE SPACE</div>
      <nav aria-label="Main navigation">{navigation.map(({ href, label, Icon }) => <Link key={href} href={href} className={`nav-link ${path === href ? 'active' : ''}`} aria-current={path === href ? 'page' : undefined}><Icon size={18}/><span>{label}</span>{href === '/notebook' && notebook.length > 0 && <span className="nav-count" aria-hidden="true">{notebook.length}</span>}</Link>)}</nav>
      <Link href="/" className="sidebar-new" aria-disabled={busy} onClick={e => { if (busy) e.preventDefault(); else startConversation(); }}><Plus size={18}/> New Conversation</Link>
      <section className="recent-conversations" aria-labelledby="recent-heading"><h2 id="recent-heading">Recent Conversations</h2><p>20 recent threads · up to 80 messages each</p><div>{history.filter(thread => thread.messages.length > 0).map(thread => <div className={`recent-thread ${conversation.id === thread.id ? 'current' : ''}`} key={thread.id}><Link href="/" aria-current={conversation.id === thread.id ? 'true' : undefined} onClick={e => { if (busy) { e.preventDefault(); return; } openConversation(thread.id); }}><MessageCircle size={14}/><span>{thread.title}</span></Link><button disabled={busy} aria-label={`Delete conversation: ${thread.title}`} onClick={() => { if (window.confirm('Delete this conversation from this browser? Notebook entries will remain saved.')) deleteConversation(thread.id); }}><Trash2 size={13}/></button></div>)}</div></section>
      <div className="sidebar-bottom"><div className="studio-mini"><span className="mini-icon"><Headphones size={21}/></span><div><strong>Your studio, in focus.</strong><p>{setup.microphone || setup.audioInterface ? 'A little context. Better guidance.' : 'Make room for your next idea.'}</p></div></div><Link href="/setup" className="sidebar-setup">Edit My Studio Setup <ArrowUpRight size={14}/></Link><div className="local-label"><span/> LOCAL WORKSPACE</div></div>
    </aside>
    <div className="main-column"><header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{navigation.find(n => n.href === path)?.label || 'Studio Assistant'}</strong></div><span className="workspace-chip"><span className="small-wave"><AudioLines size={15}/></span> A space to create</span></header>
      <details className="mobile-history"><summary>Recent Conversations ({history.filter(t => t.messages.length).length})</summary>{history.filter(t => t.messages.length).map(thread => <div key={thread.id}><Link href="/" onClick={e => { if (busy) e.preventDefault(); else { openConversation(thread.id); e.currentTarget.closest('details')?.removeAttribute('open'); } }}>{thread.title}</Link><button disabled={busy} aria-label={`Delete conversation: ${thread.title}`} onClick={() => { if (window.confirm('Delete this conversation? Your Notebook stays saved.')) deleteConversation(thread.id); }}><Trash2 size={15}/></button></div>)}</details>
      <main id="main">{storageError && <div role="alert" className="storage-warning">{storageError}</div>}{children}</main>
      <nav className="mobile-nav" aria-label="Mobile navigation">{navigation.map(({ href, label, Icon }) => <Link key={href} href={href} className={path === href ? 'active' : ''} aria-current={path === href ? 'page' : undefined}><Icon size={19}/><span>{label.replace('My Studio ', '').replace('Studio ', '')}</span></Link>)}</nav>
    </div>
  </div>;
}
