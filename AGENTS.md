# ScholarMate Architecture & Design

ScholarMate is an intelligent study assistant that transforms how you read and understand documents. Instead of opening PDFs or EPUBs in a traditional viewer, this application provides an interactive learning environment where an AI companion helps you comprehend complex content in real-time.

**Last Updated:** December 2025

## Core Concept

The application features a dual-pane layout:
- **Left Pane**: Document viewer (PDF or EPUB) for natural reading experience
- **Right Pane**: Tabbed interface with:
  - AI Analysis: Contextual insights and summaries with streaming responses
  - Chat Interface: Interactive conversation about document content (single or dual LLM modes)
  - Notes: Persistent note-taking with full CRUD operations
  - Highlights: Color-coded text highlighting with management

The AI processes the current page/section along with surrounding context to provide relevant assistance, maintaining conversation history throughout your reading session. Support for multiple LLM providers through configurable endpoints.

## Current Architecture (Production Ready)

### **Frontend: React 19 + TypeScript + Vite**

#### **Document Rendering**
- **PDF Support**: `react-pdf` v9.2.1 (wrapper around PDF.js) for robust PDF rendering
- **EPUB Support**: Custom EPUB viewer with full navigation, styling, and image support
- **Universal Document Interface**: Unified API for both PDF and EPUB documents with type-safe document types

#### **UI Framework & Styling**
- **Tailwind CSS v4**: Modern utility-first CSS framework with responsive design and dark theme optimized for reading
- **Component Architecture**: Modular, reusable components with proper separation of concerns
- **Markdown Support**: `react-markdown` with syntax highlighting (`rehype-highlight`), KaTeX math support (`rehype-katex`), and GFM support (`remark-gfm`)
- **Data Visualization**: `recharts` v3.5.1 for reading statistics and analytics

#### **State Management**
- **React Hooks**: useState, useEffect for local component state
- **Context API**: HighlightsContext and SettingsContext for global state
- **Custom Hooks**: useHighlights for highlight management, useStatistics for reading analytics

#### **Key Pages & Components**
1. **Library Page**:
   - Unified grid view of all documents (PDFs and EPUBs)
   - Status-based filtering with tabs (All, New, Reading, Finished)
   - Reading progress visualization with status badges
   - Thumbnail generation and caching
   - Book management (status updates, deletion via action menu)
   - Parallel loading of PDF and EPUB documents

2. **Reader Page**:
   - Automatic document type detection (PDF/EPUB)
   - Resizable panel layout with SimpleResizablePanels component
   - Tabbed right panel (AI Analysis, Chat, Notes, Highlights)
   - Keyboard navigation support
   - Real-time progress tracking and persistence
   - Support for both single and dual LLM chat modes

3. **Statistics Page** (NEW):
   - Comprehensive reading analytics per document
   - Summary cards (total sessions, pages read, time spent, streak)
   - Reading speed chart with trend visualization
   - Pages per session chart
   - Session history table with detailed breakdowns
   - Timezone-aware time tracking

4. **Specialized Components**:
   - `PDFViewer`: Page-based PDF navigation with progress tracking
   - `EPUBViewer`: Chapter-based EPUB navigation with ToC
   - `TabbedRightPanel`: AI analysis, chat, notes, and highlights
   - `HighlightOverlay` & `EPUBHighlightMenu`: Text selection and highlight management
   - `ChatInterface` & `DualChatInterface`: Single and dual LLM chat interfaces
   - `ThinkBlock`: Collapsible thinking/reasoning display for LLM responses
   - `LLMConfigForm` & `LLMSelectionModal`: LLM configuration and selection UI
   - `SettingsModal`: Application settings management

### **Backend: FastAPI + Python 3.12**

#### **Core Services Architecture**
- **Modular Service Layer**: Separate services for PDFs, EPUBs, AI, database operations, LLM configuration
- **Base Database Service**: Abstract base class for all database-backed services with connection pooling
- **Database Service**: SQLite-based persistence for progress, notes, highlights, chat history, and reading sessions
- **Migration System**: Versioned database schema management with automatic migrations
- **Request Tracking Service**: Manages streaming requests with cancellation support

#### **PDF Processing**
- **PDF Service**: Text extraction, thumbnail generation, metadata parsing, status management
- **PDF Cache**: In-memory caching layer for EPUB data to reduce filesystem reads
- **Libraries**: PyMuPDF (fitz), PDFPlumber, PyPDF2 for robust PDF processing
- **Features**: Page-by-page text extraction, thumbnail caching, progress tracking, status counts

#### **EPUB Processing**
- **EPUB Service**: Complete EPUB parsing and content extraction with caching
- **EPUB Cache**: In-memory caching layer for EPUB data to reduce filesystem reads
- **Component Services**:
  - `EPUBMetadataExtractor`: Book metadata and cover extraction
  - `EPUBNavigationService`: Table of contents and navigation structure
  - `EPUBContentProcessor`: HTML content processing with relative URL resolution
  - `EPUBStyleProcessor`: CSS extraction and sanitization
  - `EPUBImageService`: Image extraction and serving
  - `EPUBURLHelper`: URL resolution and path handling
- **Features**: Navigation tree, content streaming, style processing, image handling

#### **AI Integration**
- **LLM Configuration Service**: Multi-LLM endpoint management with configurable base URLs, API keys, and model names
- **Ollama Service**: OpenAI-compatible client for any LLM provider (Ollama, LM Studio, OpenAI, etc.)
- **Dual Chat Service**: Simultaneous chat with two LLMs for comparison
- **Stream Parser**: Structured streaming with thinking/response separation using `<think>` tags
- **Context-Aware Analysis**: Processes current content with surrounding context
- **Streaming Responses**: Real-time AI response streaming with Server-Sent Events (SSE)
- **Chat Persistence**: Conversation history maintained per document in database
- **Request Cancellation**: Support for stopping active streaming requests

#### **API Endpoints**

**PDF Endpoints:**
- `GET /pdf/list` - List PDFs with metadata, progress, and notes info
- `GET /pdf/{filename}/info` - Detailed PDF information
- `GET /pdf/{filename}/text/{page_num}` - Extract text from specific page
- `PUT /pdf/{filename}/progress` - Save reading progress
- `PUT /pdf/{filename}/status` - Update book status
- `GET /pdf/{filename}/thumbnail` - Get/generate thumbnail
- `GET /pdf/status-counts` - Get counts for each status category

**EPUB Endpoints:**
- `GET /epub/list` - List EPUBs with metadata and progress
- `GET /epub/{filename}/navigation` - Get table of contents structure
- `GET /epub/{filename}/content/{nav_id}` - Get chapter content
- `GET /epub/{filename}/styles` - Get sanitized CSS styles
- `GET /epub/{filename}/image/{image_path}` - Serve EPUB images
- `PUT /epub/{filename}/progress` - Save reading progress
- `GET /epub/status-counts` - Get counts for each status category

**AI Endpoints:**
- `GET /ai/health` - Check AI service status
- `POST /ai/analyze` - Analyze PDF page (non-streaming)
- `POST /ai/analyze/stream` - Analyze PDF page with streaming response
- `POST /ai/analyze-epub-section` - Analyze EPUB section (non-streaming)
- `POST /ai/analyze-epub-section/stream` - Analyze EPUB section with streaming
- `POST /ai/chat` - Interactive chat about PDF content with structured streaming
- `POST /ai/chat/epub` - Interactive chat about EPUB content with structured streaming
- `POST /ai/chat/stop/{request_id}` - Stop active PDF chat request
- `POST /ai/chat/epub/stop/{request_id}` - Stop active EPUB chat request
- `POST /ai/dual-chat` - Chat with two LLMs simultaneously
- `POST /ai/dual-chat/stop/{request_id}` - Stop active dual chat request
- `GET /ai/{filename}/context/{page_num}` - Get text context around a page

**LLM Configuration Endpoints:**
- `GET /llm-config/list` - List all LLM configurations
- `GET /llm-config/{config_id}` - Get specific configuration
- `GET /llm-config/active` - Get currently active configuration
- `POST /llm-config` - Create new LLM configuration
- `PUT /llm-config/{config_id}` - Update existing configuration
- `DELETE /llm-config/{config_id}` - Delete configuration
- `POST /llm-config/{config_id}/activate` - Set as active configuration

**Notes & Highlights Endpoints:**
- Full CRUD operations for both PDFs and EPUBs (separate router modules)
- `GET /notes/{filename}` - Get all notes for a document
- `POST /notes/{filename}` - Create new note
- `PUT /notes/{note_id}` - Update note
- `DELETE /notes/{note_id}` - Delete note
- `GET /highlights/{filename}` - Get all highlights for a document
- `POST /highlights/{filename}` - Create new highlight
- `PUT /highlights/{highlight_id}` - Update highlight
- `DELETE /highlights/{highlight_id}` - Delete highlight
- Color-coded highlight system with RGB color storage

**Reading Statistics Endpoints:**
- `GET /reading-statistics/{filename}` - Get comprehensive reading statistics for a document
- Returns session history, aggregate stats, and streak data
- Includes reading speed, pages per session, total time, and more

### **Deployment: Docker Compose**

#### **Multi-Service Architecture**
```yaml
services:
  ollama:        # AI model service (Ollama)
  backend:       # FastAPI application (Python 3.12 + uv)
  frontend:      # React application (Node 18 + nginx)
  model-init:    # One-time model download (qwen3:30b)
```

#### **Production Features**
- **Health Checks**: All services include comprehensive health monitoring
- **Volume Persistence**: AI models and document data persist across restarts
- **Environment Configuration**: Configurable URLs, ports, and API endpoints
- **Automatic Model Download**: Initial setup downloads required AI models
- **Build Optimization**: Multi-stage Docker builds for frontend (build + nginx), uv for Python dependency management
- **Service Dependencies**: Proper startup ordering with health check dependencies

## Updated High-Level Architecture:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    React 19 Frontend (Vite 6)                        │
├─────────────────┬────────────────────┬───────────────────────────────┤
│   Document      │   Tabbed Right     │   Pages & Features            │
│   Viewer        │   Panel            │                               │
│                 │                    │ • Library (unified PDF/EPUB)  │
│ • PDF Viewer    │ • AI Analysis      │ • Reader (auto-detect type)   │
│ • EPUB Viewer   │ • Chat (single/    │ • Statistics (analytics)      │
│ • Navigation    │   dual LLM)        │ • LLM Config (multi-endpoint) │
│ • Progress      │ • Notes            │ • Highlights & Notes          │
│   Tracking      │ • Highlights       │ • Settings                    │
└────────┬────────┴────────┬───────────┴──────────┬────────────────────┘
         │                 │                      │
         └─────────────────┴──────────────────────┘
                           │
                     FastAPI Backend
                           │
      ┌────────────────────┴────────────────────────┐
      │                                             │
  Document Services                            AI Services
      │                                             │
  ┌───┴────┬──────────┐                    ┌────────┴──────────┐
  │ PDF    │ EPUB     │                    │ LLM Config        │
  │Service │ Service  │                    │ Service           │
  │+ Cache │ + Cache  │                    ├───────────────────┤
  └────┬───┴────┬─────┘                    │ Ollama Service    │
       │        │                          │ (OpenAI-compat)   │
  ┌────┴────────┴─────┐                    ├───────────────────┤
  │  Base Database    │                    │ Dual Chat Service │
  │     Service       │                    ├───────────────────┤
  ├───────────────────┤                    │ Stream Parser     │
  │ Reading Progress  │                    │ (<think> tags)    │
  │ Notes & Highlights│                    └────────┬──────────┘
  │ Chat History      │                             │
  │ Reading Sessions  │                    ┌────────┴──────────┐
  │ LLM Configs       │                    │ LLM Providers:    │
  │ Migration System  │                    │ • Ollama          │
  └───────────────────┘                    │ • LM Studio       │
         (SQLite)                          │ • OpenAI-compat   │
                                           └───────────────────┘
```

## Advanced Features Implemented:

### **Document Management**
1. **Universal Document Support**: Seamless handling of both PDF and EPUB formats with unified interface
2. **Smart Status Tracking**: Automatic status updates based on reading progress with manual override support
3. **Thumbnail Generation**: Cached thumbnails for quick library browsing
4. **Reading Progress Persistence**: Resume reading exactly where you left off with page/section tracking
5. **Status Counts**: Real-time counts for New, Reading, and Finished documents
6. **Parallel Loading**: Efficient parallel loading of PDFs and EPUBs in library view

### **AI-Powered Features**
1. **Multi-LLM Support**: Configure and switch between multiple LLM endpoints (Ollama, LM Studio, OpenAI, etc.)
2. **Dual Chat Mode**: Compare responses from two LLMs side-by-side simultaneously
3. **Context-Aware Analysis**: AI processes current content with surrounding context
4. **Structured Streaming**: Separated thinking/reasoning (`<think>` tags) and response content
5. **Persistent Chat History**: Conversations maintained per document in SQLite database
6. **Real-time Streaming**: Server-Sent Events (SSE) for real-time AI response delivery
7. **Request Cancellation**: Stop active streaming requests mid-generation
8. **Configurable Endpoints**: Store multiple LLM configurations with base URLs, API keys, and model names

### **Reading Analytics** (NEW)
1. **Reading Sessions**: Track individual reading sessions with start/end times
2. **Reading Speed**: Calculate and visualize reading speed over time
3. **Pages Per Session**: Track productivity with pages read per session
4. **Streak Tracking**: Monitor reading streaks and consistency
5. **Comprehensive Statistics**: Total time, pages, sessions, and more
6. **Timezone-Aware**: Proper handling of timezone conversions for accurate time tracking

### **Enhanced Reading Experience**
1. **Highlight System**: Color-coded highlights with RGB storage and persistent management
2. **Note Management**: Full CRUD operations for notes with document association
3. **Navigation Enhancement**: Keyboard shortcuts and intuitive controls
4. **Responsive Design**: Optimized for various screen sizes with dark theme
5. **Markdown Support**: Rich markdown rendering with syntax highlighting and KaTeX math
6. **Tabbed Interface**: Clean tabbed right panel for AI, Chat, Notes, and Highlights

### **Data Persistence & Performance**
1. **SQLite Database**: Lightweight, file-based persistence with multiple tables
2. **Migration System**: Schema versioning for data integrity and automatic migrations
3. **Backup-Friendly**: Simple file-based storage for easy backups
4. **Caching Layer**: In-memory caching for PDF and EPUB data to reduce filesystem I/O
5. **Connection Pooling**: Base database service with efficient connection management

## Technology Stack Summary:

**Frontend:**
- React 19.1.0 with TypeScript 5.8
- Vite 6.3.5 for fast development and building
- Tailwind CSS 4.1.7 for modern styling
- react-pdf 9.2.1 for PDF rendering
- react-router-dom 7.6.0 for routing
- axios 1.9.0 for HTTP requests
- react-markdown 10.1.0 with rehype-highlight, rehype-katex, remark-gfm
- recharts 3.5.1 for data visualization
- date-fns 4.1.0 for date handling
- Custom EPUB viewer implementation

**Backend:**
- FastAPI 0.115.12 with Python 3.12
- SQLite for data persistence
- PyMuPDF 1.25.3 for PDF processing
- ebooklib 0.18 for EPUB processing
- OpenAI SDK 1.82.0 for LLM integration (OpenAI-compatible)
- httpx 0.28.1 for async HTTP
- BeautifulSoup4 4.12.3 for HTML processing
- uvicorn 0.34.2 for ASGI server

**Development Tools:**
- uv package manager for Python dependencies
- npm for frontend dependencies
- Ruff 0.11.11 for Python linting and formatting
- ESLint 9.25.0 for TypeScript linting
- Prettier 3.5.3 for code formatting
- pre-commit 4.0.1 for Git hooks

**Deployment:**
- Docker Compose v3.8 for orchestration
- Multi-stage Docker builds
- uv for Python dependency management in containers
- nginx for frontend serving
- Health checks and monitoring
- Volume persistence

**AI/ML:**
- OpenAI-compatible API support (Ollama, LM Studio, OpenAI, etc.)
- Default: Ollama with qwen3:30b model
- Configurable LLM endpoints with multiple provider support
- Local or cloud processing depending on configuration
- Context-aware document analysis
- Structured streaming with thinking/response separation
- Dual LLM comparison mode

## Environment Setup

### **Prerequisites**

**Backend Development:**
- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) package manager
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh

  # Windows
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

**Frontend Development:**
- Node.js 18 or higher
- npm (comes with Node.js)

**Production Deployment:**
- Docker 20.10+ and Docker Compose 2.0+

### **Development Setup**

**Backend:**
```bash
cd backend
uv sync                    # Install dependencies
uv sync --dev             # Install dev dependencies
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install               # Install dependencies
npm run dev              # Start dev server
npm run build            # Build for production
npm run lint             # Run ESLint
npm run format           # Format with Prettier
```

**Docker Compose (Recommended for Production):**
```bash
docker compose up -d      # Start all services
docker compose down       # Stop all services
docker compose logs -f    # View logs
```

This architecture provides a production-ready, scalable foundation for intelligent document reading and analysis, with support for multiple document formats, comprehensive AI integration with multiple LLM providers, and advanced reading analytics.
