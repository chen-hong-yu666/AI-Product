'use client';

import { FormEvent, useMemo, useState } from 'react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function ChatApp() {
  const [file, setFile] = useState<File | null>(null);
  const [docId, setDocId] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const canAsk = useMemo(() => !!docId && !!question.trim() && !loading, [docId, question, loading]);

  const onUpload = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setDocId(data.document_id);
      setMessages([{ role: 'assistant', content: `文档已上传，可开始提问。Document ID: ${data.document_id}` }]);
    } catch (err) {
      setMessages((p) => [...p, { role: 'assistant', content: `上传失败: ${(err as Error).message}` }]);
    } finally {
      setLoading(false);
    }
  };

  const onAsk = async (e: FormEvent) => {
    e.preventDefault();
    if (!canAsk) return;
    const userQuestion = question.trim();
    setQuestion('');
    setMessages((prev) => [...prev, { role: 'user', content: userQuestion }]);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: docId, question: userQuestion })
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `提问失败: ${(err as Error).message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1>AI PDF 问答网站</h1>
      <p className="small">技术栈：Next.js + FastAPI + OpenRouter API + ChromaDB</p>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>1) 上传 PDF</h3>
        <div className="row">
          <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button onClick={onUpload} disabled={!file || loading}>上传</button>
        </div>
        {docId ? <p className="small">当前文档 ID: {docId}</p> : null}
      </div>

      <div className="card">
        <h3>2) 聊天提问</h3>
        <div className="chat">
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role === 'user' ? 'user' : 'assistant'}`}>
              {m.content}
            </div>
          ))}
        </div>
        <form onSubmit={onAsk} style={{ marginTop: 12 }}>
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} placeholder="请输入你的问题..." />
          <div style={{ marginTop: 8 }}>
            <button type="submit" disabled={!canAsk}>{loading ? '处理中...' : '发送'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
