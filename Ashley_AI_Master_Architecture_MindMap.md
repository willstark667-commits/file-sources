# Ashley AI: Master Architecture & Mind Map

## 1. High-Level Mind Map
```text
Ashley AI Studio
├── 1. Modern User Interface (GUI)
│   ├── Sidebar (Chat History, Sessions, Personas)
│   ├── Main Chat Window (Dark Theme, ChatGPT/Claude Style)
│   ├── Input Area (Multi-line text, Send Button)
│   └── Toolbar / Settings (Theme toggle, DB Management, Tools)
├── 2. Core Engine (Phases 1-3)
│   ├── Scanner (Reads raw text/input)
│   ├── Tokenizer (Splits text into words/symbols)
│   ├── Parser (Understands grammar/structure)
│   ├── NLP Module (POS tagging, Tense, Entities)
│   └── Probability Engine (Markov chains, next-word prediction)
├── 3. Data & Memory Management
│   ├── SQLite Databases (generic.db, ashley.db)
│   ├── Vector Memory (Semantic search, RAG)
│   ├── Buffer Logger (Short-term context)
│   └── History Manager (Long-term conversation logs)
├── 4. Developer & System Tools
│   ├── File Manager (Auto-sorting code, images, video)
│   ├── Diagnostics (Syntax checking, error detection)
│   ├── Web Research (Internal browser, scraping)
│   └── Self-Improvement (Auto-patching, backups)
└── 5. Training Pipeline
    ├── Imports Directory (Raw .txt, .py, .html files)
    ├── Importer Tool (Reads and cleans files)
    └── Database Trainer (Updates weights and probabilities)
```

## 2. Processing Pipeline (The Loop)
1. **Input:** User types a message in the Modern GUI.
2. **Routing:** The `ActionRouter` determines if it's a general chat, coding request, or system command.
3. **Scanning & Tokenizing:** The `Scanner` and `Tokenizer` break the input into processable tokens.
4. **Understanding:** The `NLPProcessor` detects nouns, verbs, tenses, and entities.
5. **Retrieval (RAG):** The `VectorMemory` searches the SQLite DB and uploaded files for relevant context.
6. **Prediction:** The `ProbabilityEngine` (or LLM if active) generates the most likely response based on patterns.
7. **Output:** The response is sent back to the GUI and logged in `history.db`.
8. **Self-Correction:** Background diagnostics check for errors or inefficiencies.

## 3. Directory Scaffolding & File Paths
```text
AshleyAI_Modern/
│
├── Ashley.py                 # Main Entry Point
├── config.py                 # Global Settings & Paths
├── requirements.txt          # Python Dependencies
│
├── gui/                      # Modern UI Components
│   ├── modern_shell.py       # ChatGPT-style Dark Theme Interface
│   ├── settings_ui.py        # Configuration Menus
│   └── theme.py              # Color palettes (#343541, #202123)
│
├── engine/                   # Core AI Logic (Phases 1-3)
│   ├── chatbot.py            # Main chat loop
│   ├── scanner.py            # Text scanner
│   ├── tokenizer.py          # Token extraction
│   ├── parser.py             # Grammar parsing
│   ├── nlp.py                # Natural Language Processing
│   └── probability.py        # Markov/Prediction engine
│
├── database/                 # Memory Storage
│   ├── database.py           # SQLite wrapper
│   ├── generic.db            # General knowledge & vocabulary
│   └── ashley.db             # Persona-specific memory
│
├── tools/                    # Utilities
│   ├── importer.py           # Training data ingestion
│   ├── diagnostics.py        # Code checking
│   └── logger.py             # System logging
│
└── data/                     # Organized Uploads & Training Data
    ├── text/                 # .txt, .md, .json
    ├── code/                 # .py, .js, .html
    ├── images/               # .png, .jpg
    └── video/                # .mp4
```

## 4. Uploaded Files Integration
All uploaded files (`new_text_document_*.txt`, `plan_*.txt`, etc.) are routed to `data/text/user_uploads/`. The `importer.py` tool reads these files line-by-line, extracts the vocabulary, and updates the `generic.db` to expand Ashley's knowledge base and prediction accuracy.