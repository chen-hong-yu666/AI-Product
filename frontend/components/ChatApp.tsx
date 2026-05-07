'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';

type Source = {
  document_id: string;
  filename: string;
  page: number;
  snippet: string;
};

type Message = {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
};

type DocumentItem = {
  document_id: string;
  filename: string;
  uploaded_at: string;
  chunks: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function ChatApp() {
  const [file, setFile] = useState<File | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [uploading, setUploading] = useState(false);
  const [asking, setAsking] = useState(false);
  const [summarizingId, setSummarizingId] = useState<string>('');

  const canAsk = useMemo(() => !!question.trim() && !asking && documents.length > 0, [question, asking, documents.length]);

  const loadInitialData = async () => {
    const [docsRes, historyRes] = await Promise.all([
      fetch(`${API_BASE}/documents`),
      fetch(`${API_BASE}/history`)
    ]);
    if (docsRes.ok) {
      const data = await docsRes.json();
      setDocuments(data.documents || []);
    }
    if (historyRes.ok) {
      const data = await historyRes.json();
      setMessages(data.messages || []);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const onUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form });
      if (!res.ok) throw new Error(await res.text());
      setFile(null);
      await loadInitialData();
    } catch (err) {
      setMessages((p) => [...p, { role: 'assistant', content: `上传失败: ${(err as Error).message}` }]);
    } finally {
      setUploading(false);
    }
  };

  const onAsk = async (e: FormEvent) => {
    e.preventDefault();
    if (!canAsk) return;
    const userQuestion = question.trim();
    setQuestion('');
    setMessages((prev) => [...prev, { role: 'user', content: userQuestion }]);
    setAsking(true);
    try {
      const res = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userQuestion })
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMessages((prev) => [...prev, { role: 'assistant', content: data.answer, sources: data.sources }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `提问失败: ${(err as Error).message}` }]);
    } finally {
      setAsking(false);
    }
  };

  const onSummary = async (doc: DocumentItem) => {
    setSummarizingId(doc.document_id);
    try {
      const res = await fetch(`${API_BASE}/documents/${doc.document_id}/summary`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `### ${doc.filename} 总结\n\n${data.summary}` }
      ]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: `总结失败: ${(err as Error).message}` }]);
    } finally {
      setSummarizingId('');
    }
  };

  return (
    <div className="appLayout">
      <aside className="sidebar">
        <h2>📚 PDF 知识库</h2>
        <div className="uploadBox">
          <input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          <button onClick={onUpload} disabled={!file || uploading}>{uploading ? '上传中...' : '上传 PDF'}</button>
        </div>
        <div className="docList">
          {documents.map((doc) => (
            <div className="docCard" key={doc.document_id}>
              <p className="docTitle">{doc.filename}</p>
              <p className="small">ID: {doc.document_id.slice(0, 8)}...</p>
              <p className="small">上传: {new Date(doc.uploaded_at).toLocaleString()}</p>
              <button onClick={() => onSummary(doc)} disabled={summarizingId === doc.document_id}>
                {summarizingId === doc.document_id ? '总结中...' : '一键总结'}
              </button>
            </div>
          ))}
        </div>
      </aside>

      <main className="chatMain">
        <h1>AI PDF 学习助手</h1>
        <div className="chat">
          {messages.map((m, i) => (
            <div key={m.id ?? i} className={`bubble ${m.role === 'user' ? 'user' : 'assistant'}`}>
              <div className="markdown">{m.content}</div>
              {m.sources?.length ? (
                <div className="sources">
                  <h4>参考来源</h4>
                  {m.sources.map((s, idx) => (
                    <div key={`${s.document_id}-${idx}`} className="sourceItem">
                      <strong>{s.filename}</strong> · 第 {s.page} 页
                      <p>{s.snippet}</p>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
          {asking ? <div className="small">AI 回答中...</div> : null}
        </div>

        <form onSubmit={onAsk} className="inputBar">
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3} placeholder="输入问题，基于全部 PDF 检索回答..." />
          <button type="submit" disabled={!canAsk}>{asking ? '处理中...' : '发送'}</button>
        </form>
      </main>
    </div>
  );
}
