# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**日知 (Rizhi)** — 48-hour hackathon project: multimodal schedule extraction agent.

Extract personal schedule/task information from multiple input formats (voice, text, images, chat records) using AI, then present a visual task schedule UI. Supports natural language task management (add/delete/query/modify/undo) via a unified intent dispatch endpoint.

Target platform: **Windows Desktop** (pywebview native window).

## Repository Conventions

- README and design docs are in Chinese (Simplified); code and CLAUDE.md use English.
- All new features should be registered in `开发日志.md`.

## Key Design Documents

- `多模态识别任务管理器.md` — Original architecture specification
- `调研结果.md` — Feasibility research report
- `开发日志.md` — Development log

## Architecture

```
Input → Local Text Extraction → LLM Intent Dispatch → Action Router → Task Store → Visual UI
  │              │                        │
  │ .jpg → RapidOCR         ┌────────────┼────────────┐
  │ .mp3 → SenseVoice       │ extract    │ delete     │ chat
  │ .docx/.pdf/.pptx →      │ (add/mod)  │ (LLM       │ (reply)
  │        parsers          │            │ matches    │
  │ .txt → direct           ├────────────┤            │
  │ .webm (voice) →         │ undo       │ memory     │
  │     SenseVoice          │ (trash)    │ (3 turns)  │
  ▼              ▼          └────────────┴────────────┘
Local models   Any LLM API         │
(ONNX, zero   (user-configured     ▼
PyTorch deps) via Settings ⚙️)  Task Store (JSON persistence, trash)
```

**Key architectural decisions:**
- Local text extraction (RapidOCR, SenseVoice-Small, PyMuPDF, python-docx, python-pptx) — all ONNX Runtime, zero torch dependency
- LLM API exclusively user-configured via Settings panel — supports any OpenAI Chat API-compatible service
- **Unified intent dispatch**: `POST /api/tasks/intent` — one endpoint for extract/delete/chat/modify/undo, LLM classifies intent
- **time_resolver.py**: Single source of truth for all Chinese fuzzy time rules (15+ patterns), auto-synced to system prompt
- **context_hints.py**: Task type defaults (65 entries), fuzzy ranges, attendee extraction — LLM prompt + Python post-process use same data
- **lang/**: Modular colloquial language pack (321 rules across 9 categories) — normalizes slang before LLM sees it
- **conversation_memory.py**: 3-turn context retention injected into LLM prompt for pronoun resolution
- **Model profiles**: Per-model tuning (max_tokens, temperature, response_format) auto-detected from model name
- **Trash + undo**: Batch-based trash with `POST /api/tasks/undo` for recovering deleted tasks
- **Task kinds**: event (duration), deadline (point-in-time), milestone (annual) — each with visual differentiation

## Startup

```bash
double-click run.bat       # Opens CMD and runs launch.py
python launch.py           # Interactive menu: 1=Dev 2=Desktop
python app.py              # Desktop mode directly (requires frontend/dist built)
python app.py --dev        # Dev mode (requires Vite running on :5173)
```

## Critical Development Rules

### Do
- Use cloud APIs ONLY for LLM semantic understanding
- All text extraction (image, audio, documents) is local and offline
- LLM API supports any OpenAI Chat API-compatible service
- All file paths use `Path(__file__).resolve().parent` — no relative paths
- Add fuzzy time rules in `time_resolver.py` — system prompt auto-updates
- Add task type hints in `context_hints.py` — prompt + Python fallback auto-sync
- Add colloquial normalizations in `lang/data.py` under the appropriate category
- Add model-specific params in `MODEL_PRESETS` dict — auto-detected by model name
- All LLM API calls use `_retry_api_call()` (3 retries, exponential backoff)
- `task_store.add_all()` deduplicates by (title, date, hour)
- Note new features in `开发日志.md`

### Do NOT
- Do NOT use `Path("data/...")` — always compute from `__file__`
- Do NOT hardcode time rules outside `time_resolver.py`
- Do NOT hardcode `max_tokens=4096` — use `_detect_profile()`
- Do NOT pass `temperature` to reasoning models (deepseek-v4-pro-max, o1, o3)
- Do NOT use `response_format` with DeepSeek models (not supported)
- Do NOT use async generator for retry loops — exceptions don't propagate into generator yields

### Anti-patterns
- Frameless pywebview windows with custom JS window controls → use native frame
- Frontend regex for intent classification → use `dispatch_intent()` (single LLM call)
- Hardcoded `max_tokens` → use `ModelProfile`
- `slotEventOverlap={true}` + CSS `left:0;right:0` for event column fixes

## Key Subsystems

| Module | Purpose |
|--------|---------|
| `backend/services/time_resolver.py` | Chinese fuzzy time → concrete hour/minute; recurring pattern detection; duration extraction; auto-generates LLM prompt rules |
| `backend/services/llm_extractor.py` | `extract_tasks()`, `dispatch_intent()`, `match_tasks_to_delete()` — all LLM calls with retry |
| `backend/services/context_hints.py` | Task type defaults (65 entries × 5-tuple), fuzzy ranges, attendee extraction |
| `backend/services/lang/` | Modular colloquial normalization (321 rules), auto-generated LLM prompt |
| `backend/services/conversation_memory.py` | 3-turn conversation context for pronoun resolution |
| `app.py` | Desktop launcher (pywebview native window, no frameless hacks) |
| `launch.py` | Interactive Python menu (dev/desktop), auto port cleanup, auto frontend build |
| `run.bat` | Double-click launcher script |
