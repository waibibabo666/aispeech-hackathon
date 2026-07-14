# 多模态识别任务管理器

48小时黑客松项目：借用 AI，从多种格式文件（语音、文字、图片、聊天记录）中提取个人时间安排信息，并给出可视化任务安排界面。

## 平台

**Windows Demo** — 本地 Web 服务器 + 浏览器

## 架构

```
文件调度 → 文本提取 → LLM 结构化提取 → 置信度路由 → 可视化 UI
   │            │                                │
   │  .jpg/.png → Vision API OCR                 ├─ ≥80% 自动添加
   │  .mp3/.wav → Whisper ASR                   ├─ 50-79% 用户确认
   │  .docx/.pdf → 文档解析                      └─ <50% 丢弃
   │  .txt → 直接传递
   ▼            ▼
         纯文本汇聚 → GPT-4o/5.5 → 结构化 JSON
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Windows 10/11

### 1. 克隆项目

```bash
git clone <repo-url>
cd aispeech-hackathon
```

### 2. 配置后端

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置 .env（参考 .env.example）
cp .env.example .env
# 编辑 .env 填入 API Key 和模型名
```

**.env 示例：**

```
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o
HOST=127.0.0.1
PORT=8000
```

### 3. 启动后端

```bash
venv\Scripts\activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

后端运行在 http://127.0.0.1:8000

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端运行在 http://127.0.0.1:5173

### 5. 使用

1. 打开浏览器访问 http://127.0.0.1:5173
2. **文字输入**：粘贴聊天记录、会议笔记等，点击「提取任务」
3. **文件上传**：上传 .txt / .docx / .pdf / .jpg / .mp3 等文件
4. **加载 Demo**：点击右上角「加载Demo」查看预置数据
5. **待确认任务**：右下角浮动按钮查看需要确认的低置信度任务

## 支持的文件格式

| 格式 | 后缀 | 解析方式 |
|------|------|----------|
| 纯文本 | .txt .md .csv | 直接读取 |
| Word 文档 | .docx | python-docx |
| PDF | .pdf | PyMuPDF |
| 图片 | .jpg .png .gif .webp .bmp | Vision API OCR |
| 音频 | .mp3 .wav .m4a .ogg .flac | Whisper API |

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/extract` | 文字输入 → LLM 提取任务 |
| `POST` | `/api/upload` | 文件上传 → 自动调度解析 → LLM 提取 |
| `GET` | `/api/tasks` | 获取所有任务 |
| `GET` | `/api/tasks/pending` | 获取待确认任务 |
| `POST` | `/api/tasks/{id}/confirm` | 确认任务 |
| `POST` | `/api/tasks/{id}/reject` | 拒绝任务 |
| `DELETE` | `/api/tasks/{id}` | 删除任务 |
| `POST` | `/api/tasks/demo` | 加载演示数据 |

## 项目结构

```
aispeech-hackathon/
├── .env                    # API 配置（需自行创建）
├── .env.example            # 配置模板
├── requirements.txt        # Python 依赖
├── README.md
├── 开发日志.md
├── 多模态识别任务管理器.md  # 架构设计文档（中文）
├── 调研结果.md              # 可行性调研报告（中文）
├── backend/
│   ├── main.py             # FastAPI 入口
│   ├── config.py           # 读取 .env 配置
│   ├── routers/
│   │   ├── upload.py       # 上传 & 提取 API
│   │   └── tasks.py        # 任务 CRUD API
│   ├── services/
│   │   ├── dispatcher.py   # 文件调度器（按后缀分发）
│   │   ├── llm_extractor.py       # LLM 结构化提取
│   │   ├── confidence_router.py   # 置信度路由
│   │   └── parsers/        # 各格式解析器
│   │       ├── text_parser.py
│   │       ├── docx_parser.py
│   │       ├── pdf_parser.py
│   │       ├── image_parser.py    # Vision API OCR
│   │       └── audio_parser.py    # Whisper API
│   ├── models/
│   │   └── task.py         # Pydantic 数据模型
│   └── storage/
│       └── task_store.py   # 内存任务存储
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts   # API 调用封装
│       ├── hooks/useTasks.tsx  # 全局状态管理
│       ├── types/index.ts
│       └── components/
│           ├── Layout.tsx
│           ├── InputPanel.tsx   # 输入面板（文字 / 文件）
│           ├── TextInput.tsx
│           ├── FileUpload.tsx
│           ├── TaskTimeline.tsx  # FullCalendar 时间线
│           ├── TaskCard.tsx
│           ├── TaskDetail.tsx    # 任务详情弹窗
│           └── PendingBadge.tsx  # 待确认浮动按钮
└── data/
    └── demo_tasks.json     # 7条演示任务
```

## 技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI + Uvicorn |
| AI API | OpenAI SDK（GPT-4o/5.5 Vision + Whisper） |
| 文档解析 | python-docx + PyMuPDF |
| 前端框架 | React 18 + TypeScript |
| 日历组件 | FullCalendar v6 |
| 样式 | Tailwind CSS v4 |
| 构建工具 | Vite 6 |

## 设计决策

- **不使用本地模型**：全部走云端 API，避免依赖地狱和 Windows 兼容问题
- **不追求离线能力**：黑客松 Demo 不需要隐私保护
- **先做文本输入**（P0），多模态作为扩展（P2）
- **优先保证核心链路**：文字输入 → LLM 提取 → 置信度路由 → 可视化
