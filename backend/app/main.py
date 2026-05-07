import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
from pypdf import PdfReader

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
OPENROUTER_CHAT_MODEL = os.getenv('OPENROUTER_CHAT_MODEL', 'openai/gpt-4o-mini')
OPENROUTER_EMBEDDING_MODEL = os.getenv('OPENROUTER_EMBEDDING_MODEL', 'openai/text-embedding-3-small')
CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', './chroma_data')
COLLECTION_NAME = os.getenv('CHROMA_COLLECTION', 'pdf_qa_docs')
META_STORE_PATH = Path(os.getenv('META_STORE_PATH', './data/documents.json'))
CHAT_STORE_PATH = Path(os.getenv('CHAT_STORE_PATH', './data/chat_history.json'))

if not OPENROUTER_API_KEY:
  raise RuntimeError('OPENROUTER_API_KEY is required')

app = FastAPI(title='AI PDF QA API')

app.add_middleware(
  CORSMiddleware,
  allow_origins=['*'],
  allow_credentials=True,
  allow_methods=['*'],
  allow_headers=['*']
)

embeddings = OpenAIEmbeddings(
  model=OPENROUTER_EMBEDDING_MODEL,
  api_key=OPENROUTER_API_KEY,
  base_url=OPENROUTER_BASE_URL
)
vector_store = Chroma(
  collection_name=COLLECTION_NAME,
  persist_directory=CHROMA_PERSIST_DIR,
  embedding_function=embeddings
)
llm = ChatOpenAI(
  model=OPENROUTER_CHAT_MODEL,
  temperature=0,
  api_key=OPENROUTER_API_KEY,
  base_url=OPENROUTER_BASE_URL
)
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


class SourceItem(BaseModel):
  document_id: str
  filename: str
  page: int
  snippet: str


class AskRequest(BaseModel):
  question: str


class AskResponse(BaseModel):
  answer: str
  sources: List[SourceItem]
  document_ids: List[str]


class SummaryResponse(BaseModel):
  document_id: str
  filename: str
  summary: str


def ensure_store(path: Path, default_value: Any):
  path.parent.mkdir(parents=True, exist_ok=True)
  if not path.exists():
    path.write_text(json.dumps(default_value, ensure_ascii=False, indent=2), encoding='utf-8')


def read_json(path: Path, default_value: Any):
  ensure_store(path, default_value)
  with path.open('r', encoding='utf-8') as f:
    return json.load(f)


def write_json(path: Path, data: Any):
  ensure_store(path, data)
  with path.open('w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


def now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def append_chat(role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None):
  history = read_json(CHAT_STORE_PATH, [])
  item: Dict[str, Any] = {
    'id': str(uuid.uuid4()),
    'created_at': now_iso(),
    'role': role,
    'content': content
  }
  if sources:
    item['sources'] = sources
  history.append(item)
  write_json(CHAT_STORE_PATH, history)


@app.get('/health')
def health():
  return {'status': 'ok'}


@app.get('/documents')
def list_documents():
  docs = read_json(META_STORE_PATH, [])
  return {'documents': docs}


@app.get('/history')
def get_history():
  return {'messages': read_json(CHAT_STORE_PATH, [])}


@app.post('/upload')
async def upload_pdf(file: UploadFile = File(...)):
  if file.content_type != 'application/pdf':
    raise HTTPException(status_code=400, detail='Only PDF is allowed')

  document_id = str(uuid.uuid4())
  uploaded_at = now_iso()
  with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
    tmp.write(await file.read())
    tmp_path = tmp.name

  chunk_count = 0
  try:
    reader = PdfReader(tmp_path)
    docs = []
    for page_idx, page in enumerate(reader.pages):
      page_text = (page.extract_text() or '').strip()
      if not page_text:
        continue
      page_chunks = splitter.split_text(page_text)
      for chunk_idx, chunk in enumerate(page_chunks):
        chunk_id = f'{document_id}_{page_idx}_{chunk_idx}'
        docs.append({
          'id': chunk_id,
          'text': chunk,
          'metadata': {
            'document_id': document_id,
            'chunk': chunk_idx,
            'page': page_idx + 1,
            'filename': file.filename or 'unknown.pdf',
            'uploaded_at': uploaded_at
          }
        })

    if not docs:
      raise HTTPException(status_code=400, detail='No extractable text in PDF')

    vector_store.add_texts(
      texts=[d['text'] for d in docs],
      ids=[d['id'] for d in docs],
      metadatas=[d['metadata'] for d in docs]
    )
    chunk_count = len(docs)

    stored_docs = read_json(META_STORE_PATH, [])
    stored_docs.append({
      'document_id': document_id,
      'filename': file.filename or 'unknown.pdf',
      'uploaded_at': uploaded_at,
      'chunks': chunk_count
    })
    write_json(META_STORE_PATH, stored_docs)
  finally:
    if os.path.exists(tmp_path):
      os.remove(tmp_path)

  return {'document_id': document_id, 'chunks': chunk_count, 'uploaded_at': uploaded_at}


@app.post('/ask', response_model=AskResponse)
def ask(req: AskRequest):
  retriever = vector_store.as_retriever(search_type='similarity', search_kwargs={'k': 6})
  docs = retriever.invoke(req.question)

  if not docs:
    raise HTTPException(status_code=404, detail='No relevant content found in knowledge base')

  context_blocks = []
  source_items: List[SourceItem] = []
  seen_keys = set()
  for d in docs:
    filename = d.metadata.get('filename', 'unknown.pdf')
    page = int(d.metadata.get('page', 0) or 0)
    doc_id = d.metadata.get('document_id', '')
    snippet = d.page_content[:300].strip()
    key = (doc_id, page, snippet)
    if key in seen_keys:
      continue
    seen_keys.add(key)

    source_items.append(SourceItem(
      document_id=doc_id,
      filename=filename,
      page=page,
      snippet=snippet
    ))
    context_blocks.append(f'[{filename} - 第{page}页]\n{d.page_content}')

  context = '\n\n'.join(context_blocks)
  prompt = f"""
你是一个 PDF 学习助手。请仅基于给定上下文回答。
如果答案不在上下文里，请明确说不知道。
输出请使用 Markdown，先给出简明答案，再列出关键点。

问题：{req.question}

上下文：
{context}
"""
  answer = llm.invoke(prompt).content
  document_ids = sorted({s.document_id for s in source_items if s.document_id})

  append_chat('user', req.question)
  append_chat('assistant', answer, [s.model_dump() for s in source_items])

  return AskResponse(answer=answer, sources=source_items, document_ids=document_ids)


@app.post('/documents/{document_id}/summary', response_model=SummaryResponse)
def summarize_document(document_id: str):
  stored_docs = read_json(META_STORE_PATH, [])
  matched = next((d for d in stored_docs if d['document_id'] == document_id), None)
  if not matched:
    raise HTTPException(status_code=404, detail='Document not found')

  result = vector_store.get(where={'document_id': document_id}, include=['documents', 'metadatas'])
  doc_texts = result.get('documents') or []
  metadatas = result.get('metadatas') or []
  if not doc_texts:
    raise HTTPException(status_code=404, detail='No content found for this document')

  selected = doc_texts[:12]
  contexts = []
  for idx, txt in enumerate(selected):
    page = metadatas[idx].get('page', '?') if idx < len(metadatas) else '?'
    contexts.append(f'第{page}页: {txt}')

  prompt = f"""
请基于以下 PDF 内容生成学习总结，使用 Markdown 标题和列表，必须包含以下部分：
1. 核心观点
2. 重点知识
3. 适合考试复习的要点
4. 可能出的题目（至少5题）

内容：
{'\n\n'.join(contexts)}
"""
  summary = llm.invoke(prompt).content
  return SummaryResponse(document_id=document_id, filename=matched['filename'], summary=summary)
