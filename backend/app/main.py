import os
import tempfile
import uuid
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel
from pypdf import PdfReader

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', './chroma_data')
COLLECTION_NAME = os.getenv('CHROMA_COLLECTION', 'pdf_qa_docs')

if not OPENAI_API_KEY:
  raise RuntimeError('OPENAI_API_KEY is required')

app = FastAPI(title='AI PDF QA API')

app.add_middleware(
  CORSMiddleware,
  allow_origins=['*'],
  allow_credentials=True,
  allow_methods=['*'],
  allow_headers=['*']
)

embeddings = OpenAIEmbeddings(model='text-embedding-3-small', api_key=OPENAI_API_KEY)
vector_store = Chroma(
  collection_name=COLLECTION_NAME,
  persist_directory=CHROMA_PERSIST_DIR,
  embedding_function=embeddings
)
llm = ChatOpenAI(model='gpt-4o-mini', temperature=0, api_key=OPENAI_API_KEY)
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


class AskRequest(BaseModel):
  document_id: str
  question: str


class AskResponse(BaseModel):
  answer: str
  sources: List[str]


@app.get('/health')
def health():
  return {'status': 'ok'}


@app.post('/upload')
async def upload_pdf(file: UploadFile = File(...)):
  if file.content_type != 'application/pdf':
    raise HTTPException(status_code=400, detail='Only PDF is allowed')

  document_id = str(uuid.uuid4())
  with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
    tmp.write(await file.read())
    tmp_path = tmp.name

  try:
    reader = PdfReader(tmp_path)
    pages = [page.extract_text() or '' for page in reader.pages]
    full_text = '\n\n'.join(pages).strip()
    if not full_text:
      raise HTTPException(status_code=400, detail='No extractable text in PDF')

    chunks = splitter.split_text(full_text)
    docs = []
    for idx, chunk in enumerate(chunks):
      docs.append({
        'id': f'{document_id}_{idx}',
        'text': chunk,
        'metadata': {'document_id': document_id, 'chunk': idx, 'filename': file.filename or 'unknown.pdf'}
      })

    vector_store.add_texts(
      texts=[d['text'] for d in docs],
      ids=[d['id'] for d in docs],
      metadatas=[d['metadata'] for d in docs]
    )
  finally:
    if os.path.exists(tmp_path):
      os.remove(tmp_path)

  return {'document_id': document_id, 'chunks': len(chunks)}


@app.post('/ask', response_model=AskResponse)
def ask(req: AskRequest):
  retriever = vector_store.as_retriever(
    search_type='similarity',
    search_kwargs={'k': 4, 'filter': {'document_id': req.document_id}}
  )
  docs = retriever.invoke(req.question)

  if not docs:
    raise HTTPException(status_code=404, detail='Document not found or no relevant content')

  context = '\n\n'.join([d.page_content for d in docs])
  prompt = f"""
你是一个 PDF 问答助手。请仅基于给定上下文回答。
如果答案不在上下文里，请明确说不知道。

问题：{req.question}

上下文：
{context}
"""
  answer = llm.invoke(prompt).content
  sources = [f"chunk:{d.metadata.get('chunk')}" for d in docs]

  return AskResponse(answer=answer, sources=sources)
