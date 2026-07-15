# 日知

48小时黑客松项目：多模态日程提取 Agent。从多种格式文件（语音、文字、图片、聊天记录）中提取日程信息，支持自然语言增删改查（"删除所有晚餐"、"本周每天下午2点锻炼"），可视化任务安排界面。

## 平台

**Windows Desktop** — pywebview 原生窗口，双击 `run.bat` 启动。

## 架构

```
输入 → 本地文字提取 → LLM 意图识别 → 操作路由 → 任务存储 → 可视化 UI
  │         │                  │
  │ .jpg → RapidOCR    ┌──────┼──────┐
  │ .mp3 → SenseVoice  │extract│delete│ chat
  │ .pdf → PyMuPDF     │(添加)  │(删除)│(回复)
  │ .docx→ python-docx ├───────┤      │
  │ .pptx→ python-pptx │modify │undo  │
  │ .txt → 直接读取    │(修改)  │(恢复)│
  │ 🎤 → AudioContext  └───────┴──────┘
  │      → SenseVoice        │
  ▼                          ▼
本地 ONNX 模型         任意 LLM API
(零 PyTorch 依赖)       (设置面板 ⚙️ 配置)
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Windows 10/11

### 1. 安装依赖（仅首次）

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. 一键启动

```bash
python launch.py          # 或双击 run.bat
```

菜单选择：
- **1. Dev mode** — Vite 热更新 + 后端自动重载，浏览器打开 `http://localhost:5173`
- **2. Desktop** — pywebview 原生 Windows 窗口，自动构建前端

### 3. 配置 LLM API

点击右上角 **⚙️** → 填写 LLM API 信息 → 保存。

### 4. 使用

- **文字输入**：粘贴聊天记录、会议笔记等，点击「发送」或 Ctrl+Enter
  - 自动识别意图：描述日程 → 提取任务，`删除XXX` → 删除任务，问候 → 闲聊回复
- **语音输入**：点击 🎤 按钮开始说话，文字实时显示，说完点击停止
  - 使用本地 SenseVoice-Small 转录，完全离线，1 秒刷新
- **文件上传**：拖拽 .txt / .docx / .pdf / .pptx / .jpg / .mp3 等文件
- **自然语言管理**：
  - `周五下午三点开会` → 自动提取并添加到日历
  - `删除所有晚餐` → LLM 匹配并删除
  - `跑步改到明天晚上8点` → 自动删除旧任务 + 创建新任务
  - `把事儿都推了` → 儿化音/口语自动标准化为"把事情全部取消"
  - `刚删错了，恢复` → 撤销上一次删除
  - `明天和女神约会` → 自动识别为社交类型，默认 18:00，持续 2 小时
  - `8点化妆，8点半出门` → LLM 自动推理前一事件的结束时间
- **编辑任务**：点击日历上的任务 → 点「✏️ 编辑」→ 修改时间/类型/标题 → 保存
- **任务类型**：
  - 📅 时间段事件（开会、吃饭、跑步）— 有时间段，虚线框
  - 🔴 截止日（还款、DL、交房租）— 单时间点，红色标记
  - ⭐ 纪念日（生日、纪念日、春节）— 年度重复，紫色标记
- **冲突检测**：时间重叠的任务自动标红并呼吸闪烁

## 支持的文件格式

| 格式 | 后缀 | 解析方式 |
|------|------|----------|
| 纯文本 | .txt .md .csv | 直接读取 |
| Word 文档 | .docx | python-docx（本地） |
| PowerPoint | .pptx | python-pptx（本地，含表格+备注） |
| PDF | .pdf | PyMuPDF（本地）+ 扫描件 OCR 回退 |
| 图片 | .jpg .png .gif .webp .bmp | RapidOCR（本地，~30MB） |
| 音频 | .mp3 .wav .m4a .ogg .flac | SenseVoice-Small（本地，~227MB） |
| 语音输入 | webm → WAV | AudioContext → SenseVoice（实时，1s 流式） |

## 本地模型

| 模型 | 大小 | 用途 |
|------|------|------|
| RapidOCR | ~30MB | 图片文字识别，纯 ONNX，中文优化 |
| SenseVoice-Small | ~227MB | 语音转文字，中文准确率 96%+ |

## LLM API 兼容性

支持所有兼容 OpenAI Chat API 的服务：OpenAI、DeepSeek、阿里百炼、智谱、Moonshot 等。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/extract` | 文字输入 → LLM 提取任务 |
| `POST` | `/api/upload` | 文件上传 → 解析 → LLM 提取 |
| `POST` | `/api/transcribe-voice` | 语音 → SenseVoice 转文字 |
| `POST` | `/api/tasks/intent` | **统一意图**：extract/delete/chat/modify/undo |
| `POST` | `/api/tasks/delete-by-intent` | LLM 匹配删除任务 |
| `POST` | `/api/tasks/undo` | 撤销上次删除（垃圾箱恢复） |
| `GET` | `/api/tasks` | 获取所有任务 |
| `GET` | `/api/tasks/pending` | 获取待确认任务 |
| `POST` | `/api/tasks/{id}/confirm` | 确认任务 |
| `POST` | `/api/tasks/{id}/reject` | 拒绝任务 |
| `PATCH` | `/api/tasks/{id}` | 编辑任务（时间/标题/类型） |
| `DELETE` | `/api/tasks/{id}` | 删除单个任务（可撤销） |
| `GET` | `/api/config` | 获取 LLM API 配置（Key 已掩码） |
| `POST` | `/api/config` | 更新 LLM API 配置 |
| `GET` | `/api/network-check` | 网络连通性诊断 |

## 项目结构

```
aispeech-hackathon/
├── run.bat                   # 双击启动脚本
├── launch.py                 # 一键启动菜单（Python，无编码问题）
├── app.py                    # 桌面模式入口（pywebview 原生窗口）
├── dev.py                    # 开发模式入口（Vite + uvicorn）
├── .env                      # 服务配置
├── requirements.txt
├── README.md
├── CLAUDE.md
├── 开发日志.md
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── routers/
│   │   ├── upload.py         # 上传 & 提取 & 语音转文字 API
│   │   ├── tasks.py          # 任务 CRUD + 统一意图 + 撤销 API
│   │   └── config.py         # LLM API 配置端点
│   ├── services/
│   │   ├── dispatcher.py     # 文件调度器
│   │   ├── llm_extractor.py  # LLM 提取 + 意图分发 + 删除匹配
│   │   ├── time_resolver.py  # 中文模糊时间规则（单一数据源）
│   │   ├── context_hints.py  # 任务类型默认值 + 与会人提取
│   │   ├── confidence_router.py
│   │   ├── runtime_config.py
│   │   ├── conversation_memory.py  # 3 轮对话记忆
│   │   ├── lang/
│   │   │   ├── __init__.py   # 口语标准化 + prompt 生成
│   │   │   └── data.py       # 321 条规则，9 个分类
│   │   └── parsers/          # text/docx/pdf/pptx/image/audio
│   ├── models/
│   │   └── task.py
│   └── storage/
│       └── task_store.py     # JSON 持久化 + 去重 + 垃圾箱
├── frontend/
│   └── src/
│       ├── App.tsx
│       ├── api/client.ts
│       ├── hooks/useTasks.tsx
│       ├── components/
│       │   ├── Layout.tsx
│       │   ├── InputPanel.tsx     # 统一输入（文字+语音+文件）
│       │   ├── TaskTimeline.tsx   # FullCalendar 日/周/月/列表
│       │   ├── TaskDetail.tsx     # 详情 + 编辑器
│       │   ├── PendingBadge.tsx
│       │   └── SettingsModal.tsx
│       └── types/index.ts
├── data/
│   ├── tasks.json
│   ├── trash.json             # 删除任务垃圾箱
│   ├── runtime_config.json
│   └── models/sensevoice/
└── frontend/dist/
```

## 技术栈

| 层 | 技术 |
|----|------|
| 桌面窗口 | pywebview (Edge WebView2) |
| 后端框架 | FastAPI + Uvicorn |
| LLM SDK | OpenAI Python SDK（含超时+重试） |
| 本地图片 OCR | RapidOCR（ONNX Runtime） |
| 本地语音识别 | SenseVoice-Small（sherpa-onnx） |
| 文档解析 | python-docx + python-pptx + PyMuPDF |
| 前端框架 | React 18 + TypeScript |
| 日历组件 | FullCalendar v6（自带工具栏日/周/月/列表） |
| 样式 | Tailwind CSS v4 |
| 构建工具 | Vite 6 |
| 语音录入 | AudioContext → PCM → WAV → SenseVoice |

## 设计决策

- **Agent 模式**：一次 LLM 调用同时完成意图分类 + 操作执行（extract/delete/chat/modify/undo）
- **文字提取本地化**：图片 OCR 和语音转文字均使用本地 ONNX 模型
- **口语标准化**：9 分类 321 条规则，在 LLM 看到文本前做标准化（儿化音→标准，网络用语→标准）
- **任务类型系统**：event（时间段）、deadline（截止日）、milestone（纪念日）三种，视觉区分
- **重复事件自动展开**：LLM + Python 双重兜底，确保"每天""本周每天"正确展开
- **模糊时间规则集中管理**：`time_resolver.py` 为单一数据源，system prompt 自动同步
- **任务类型默认值**：`context_hints.py` 65 种任务分类，L LLM prompt + Python fallback 使用同一份数据
- **模型适配层**：不同 LLM 的 max_tokens/temperature 自动检测，避免推理模型 token 不足
- **API 配置 UI 化**：设置面板一站式管理，数据持久化到 JSON
- **去重保护**：相同标题+日期+小时的任务不会重复添加
- **垃圾箱**：删除任务进入垃圾箱，可撤销最近一次删除
- **对话记忆**：保留最近 3 轮对话，支持"把这个改到明天"等代词指代
- **时长合理性守卫**：Python 后处理检测异常时长，用餐类上限 4× 典型时长，马拉松类不限制
- **隐含结束时间推理**：LLM prompt 指导从相邻事件推断前一个事件的结束时间
