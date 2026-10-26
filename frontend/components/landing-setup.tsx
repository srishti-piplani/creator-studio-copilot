'use client';
import Link from 'next/link';
import { StudioArt } from './studio-art';
import { AudioLines, Camera, Mic2, ArrowUpRight } from 'lucide-react';
import { InterfaceIcon } from './studio-icons';
import { useStudio } from './studio-provider';
export function LandingSetup() {
  const { setup, ready } = useStudio();
  const cards = [
    { category: 'Music production software', name: 'Logic Pro', detail: 'Documentation version 12.3', Icon: AudioLines, color: 'music' },
    { category: 'Video editing software', name: 'DaVinci Resolve', detail: 'Documentation version 21.1', Icon: Camera, color: 'video' },
    { category: 'Microphone', name: setup.microphone || 'No microphone selected', detail: setup.microphone ? 'Your selected microphone' : 'Optional · choose in My Studio Setup', Icon: Mic2, color: 'microphone' },
    { category: 'Audio interface', name: setup.audioInterface || 'No interface selected', detail: setup.audioInterface === 'Focusrite Scarlett Solo' ? '4th Gen · your selected interface' : setup.audioInterface ? '2nd Gen · your selected interface' : 'Optional · choose in My Studio Setup', Icon: InterfaceIcon, color: 'interface' },
  ];
  return <section className="landing-setup equipment-rack" aria-labelledby="landing-setup-heading"><div className="landing-setup-heading"><div><h2 id="landing-setup-heading">My Studio Setup</h2><p>Context for your questions. Always chosen by you.</p></div><Link href="/setup">Edit My Studio Setup <ArrowUpRight size={15}/></Link></div><div className="landing-setup-grid">{cards.map(({ category, name, detail, color }) => <article className={`landing-setup-card ${color}`} key={category}><span className="setup-card-icon"><StudioArt kind={color}/></span><div><span className="setup-card-category">{category}</span><h3>{ready ? name : 'Loading your setup…'}</h3><p>{detail}</p></div></article>)}</div></section>;
}
