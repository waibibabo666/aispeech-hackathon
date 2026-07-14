# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

48-hour hackathon project: **Multimodal Task Recognition Manager** ("多模态识别任务管理器").

Extract personal schedule/task information from multiple input formats (voice, text, images, chat records) using AI, then present a visual task schedule UI.

Target platform: **Windows Demo**.

## Repository Conventions

- README and design docs are in Chinese (Simplified); code and CLAUDE.md use English.

## Key Design Documents

- `多模态识别任务管理器.md` — Architecture specification: pipeline design, per-format parser code samples, confidence routing rules, risk matrix, time estimates.
- `调研结果.md` — Feasibility research report: 104-agent deep research validating what's achievable in 48h. Includes confirmed architectures, debunked approaches, and tech recommendations.

**Read these before making architectural decisions.** They represent extensive research and design work.

## Architecture

```
File Dispatch → Text Extraction → LLM Structured Extraction → Confidence Router → Visual UI
```

1. **File dispatch** — route by extension: `.jpg/.png` → Vision API OCR, `.mp3/.wav` → Whisper ASR, `.docx/.pdf` → document parsers, `.txt` → pass through
2. **LLM extraction** — all text converges into a single LLM call that outputs structured JSON (title, datetime, location, attendees, notes, confidence, source)
3. **Confidence routing** — ≥80% auto-add, 50–79% user confirms, <50% discard
4. **Visualization** — timeline/calendar/task board UI

## Critical Development Rules

### Priority order (hard cutoff)
- **P0 (must deliver):** Text input → LLM extraction → JSON output → confidence routing → visual timeline. ~25-34h.
- **P1 (important):** User confirmation UI, multi-format text import.
- **P2 (stretch):** Voice input (Whisper API), image OCR (GPT-4o Vision). Single API call each — add only if P0 is solid.

### Do NOT
- **Do NOT use local models** (Whisper local, Tesseract, Ollama, llama.cpp). Every verified hackathon success used cloud APIs exclusively. Local models cause dependency hell, memory issues, and Windows incompatibility.
- **Do NOT attempt offline capability** — not needed for a demo, and it will consume the entire time budget.
- **Do NOT use Gemini 2.5 Flash** — deprecated June 2026. Use GPT-4o, Claude, or Gemini 2.5 Pro instead.

### Do
- Use cloud APIs for everything: OpenAI GPT-4o/Vision, Whisper API, Anthropic Claude.
- Build the UI as a local web server + browser (Python backend + React frontend). Fastest path to a working Windows demo.
- Prepare fallback/demo data in case of network issues during presentation.

### Anti-patterns (debunked by research)
- "8B local model for timeline extraction" — requires fine-tuning + GPU, not viable in 48h
- "Offline multimodal RAG (Whisper+OCR+CLIP+Mistral)" — integration complexity far exceeds 48h
- "Small model (360M) fine-tuned for calendar events" — JSON format correctness ~4%
