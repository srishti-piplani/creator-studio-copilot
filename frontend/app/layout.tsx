import type { Metadata } from 'next';
import './globals.css';
import './premium.css';
import { StudioProvider } from '@/components/studio-provider';
import { Shell } from '@/components/shell';
export const metadata: Metadata = { title: 'Creator Studio Copilot', description: 'Your workspace for learning, troubleshooting, and finding your next creative resource.' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><StudioProvider><Shell>{children}</Shell></StudioProvider></body></html>;
}
