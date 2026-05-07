# AI PDF 学习助手（增量升级版）

## 已实现能力
- 多 PDF 知识库（上传后持久化文档元信息）
- 基于所有 PDF 的统一检索问答
- 每次回答返回参考来源（文件名、页码、原文片段）
- 聊天历史持久化（刷新后可见）
- 每个 PDF 支持一键总结（核心观点/重点知识/复习要点/预测题）
- 更完整的三栏式学习助手 UI（左侧文档、中间聊天、底部输入）

## 启动后端（FastAPI）
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## 启动前端（Next.js）
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

访问：`http://localhost:3000`

## 环境变量
### backend/.env
```bash
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_CHAT_MODEL=openai/gpt-4o-mini
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
CHROMA_PERSIST_DIR=./chroma_data
CHROMA_COLLECTION=pdf_qa_docs
META_STORE_PATH=./data/documents.json
CHAT_STORE_PATH=./data/chat_history.json
```

### frontend/.env.local
```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## API
- `POST /upload` 上传单个 PDF（可重复调用，形成多文档库）
- `GET /documents` 获取已上传 PDF 列表
- `POST /ask` 基于全部 PDF 检索并回答
- `GET /history` 获取聊天历史
- `POST /documents/{document_id}/summary` 生成文档总结
- `GET /health` 健康检查
