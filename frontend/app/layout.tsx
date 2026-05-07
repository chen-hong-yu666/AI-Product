import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AI PDF QA',
  description: 'Upload PDF and chat with it'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
