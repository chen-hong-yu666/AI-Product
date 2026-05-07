# AI PDF 问答网站

一个最小可运行的全栈项目：

- **前端**：Next.js（聊天气泡 UI + PDF 上传 + 提问）
- **后端**：FastAPI
- **LLM**：OpenAI API
- **向量库**：ChromaDB

## 目录结构

```bash
.
├── frontend/   # Next.js
└── backend/    # FastAPI + ChromaDB + OpenAI
```

## 1) 启动后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY
uvicorn app.main:app --reload --port 8000
```

## 2) 启动前端

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

访问：`http://localhost:3000`

## 前端环境变量

在 `frontend/.env.local` 中配置：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## API

- `POST /upload`：上传 PDF，返回 `document_id`
- `POST /ask`：根据 `document_id` + `question` 返回答案
- `GET /health`：健康检查
