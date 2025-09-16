# ScholarMate Architecture & Design

ScholarMate is an intelligent study assistant that transforms how you read and understand documents. Instead of opening PDFs or EPUBs in a traditional viewer, this application provides an interactive learning environment where an AI companion helps you comprehend complex content in real-time.

## Core Concept

The application features a dual-pane layout:
- **Left Pane**: Document viewer (PDF or EPUB) for natural reading experience
- **Right Pane**: AI-powered analysis panel with:
  - Contextual insights and summaries
  - Interactive chat interface
  - Note-taking capabilities
  - Highlight management

The AI processes the current page/section along with surrounding context to provide relevant assistance, maintaining conversation history throughout your reading session.

## Current Architecture (Production Ready)

### **Frontend: React + TypeScript + Vite**

#### **Document Rendering**
- **PDF Support**: `react-pdf` (wrapper around PDF.js) for robust PDF rendering
- **EPUB Support**: Custom EPUB viewer with full navigation, styling, and image support
- **Universal Document Interface**: Unified API for both PDF and EPUB documents

#### **UI Framework & Styling**
- **Tailwind CSS**: Responsive design with dark theme optimized for reading
- **Component Architecture**: Modular, reusable components with proper separation of concerns
- **Responsive Design**: Optimized for desktop reading with mobile compatibility

#### **State Management**
- **React Hooks**: useState, useEffect for local component state
- **Context API**: HighlightsContext and SettingsContext for global state
- **Custom Hooks**: useHighlights for complex highlight management logic

#### **Key Pages & Components**
1. **Library Page**:
   - Grid view of all documents (PDFs and EPUBs)
   - Status-based filtering (New, Reading, Finished)
   - Reading progress visualization
   - Thumbnail generation and caching
   - Book management (status updates, deletion)

2. **Reader Page**:
   - Auto-detection of document type (PDF/EPUB)
   - Resizable panel layout
   - Tabbed right panel (AI, Chat, Notes, Highlights)
   - Keyboard navigation support
   - Real-time progress tracking

3. **Specialized Components**:
   - `PDFViewer`: Page-based PDF navigation
   - `EPUBViewer`: Chapter-based EPUB navigation with ToC
   - `TabbedRightPanel`: AI analysis, chat, notes, and highlights
   - `HighlightOverlay`: Text selection and highlight management

### **Backend: FastAPI + Python**

#### **Core Services Architecture**
- **Modular Service Layer**: Separate services for PDFs, EPUBs, AI, database operations
- **Database Service**: SQLite-based persistence for progress, notes, highlights
- **Migration System**: Versioned database schema management

#### **PDF Processing**
- **PDF Service**: Text extraction, thumbnail generation, metadata parsing
- **Libraries**: PyMuPDF (fitz) for robust PDF processing
- **Features**: Page-by-page text extraction, thumbnail caching, progress tracking

#### **EPUB Processing**
- **EPUB Service**: Complete EPUB parsing and content extraction
- **Component Services**:
  - `EPUBMetadataExtractor`: Book metadata and cover extraction
  - `EPUBNavigationService`: Table of contents and navigation structure
  - `EPUBContentProcessor`: HTML content processing with relative URL resolution
  - `EPUBStyleProcessor`: CSS extraction and sanitization
  - `EPUBImageService`: Image extraction and serving
- **Features**: Navigation tree, content streaming, style processing, image handling

#### **AI Integration**
- **Ollama Service**: Local AI model integration (qwen3:30b)
- **Context-Aware Analysis**: Processes current content with surrounding context
- **Streaming Responses**: Real-time AI response streaming
- **Chat Persistence**: Conversation history maintained per document

#### **API Endpoints**

**PDF Endpoints:**
- `GET /pdf/list` - List PDFs with metadata, progress, and notes info
- `GET /pdf/{filename}/info` - Detailed PDF information
- `GET /pdf/{filename}/text/{page_num}` - Extract text from specific page
- `PUT /pdf/{filename}/progress` - Save reading progress
- `PUT /pdf/{filename}/status` - Update book status
- `GET /pdf/{filename}/thumbnail` - Get/generate thumbnail

**EPUB Endpoints:**
- `GET /epub/list` - List EPUBs with metadata and progress
- `GET /epub/{filename}/navigation` - Get table of contents structure
- `GET /epub/{filename}/content/{nav_id}` - Get chapter content
- `GET /epub/{filename}/styles` - Get sanitized CSS styles
- `GET /epub/{filename}/image/{image_path}` - Serve EPUB images
- `PUT /epub/{filename}/progress` - Save reading progress

**AI Endpoints:**
- `POST /ai/analyze` - Analyze current content with context
- `POST /ai/chat` - Interactive chat about document content
- `GET /ai/chat/{filename}` - Retrieve chat history

**Notes & Highlights:**
- Full CRUD operations for both PDFs and EPUBs
- Color-coded highlight system
- Searchable note management

### **Deployment: Docker Compose**

#### **Multi-Service Architecture**
```yaml
services:
  ollama:        # AI model service
  backend:       # FastAPI application
  frontend:      # React application
  model-init:    # One-time model download
```

#### **Production Features**
- **Health Checks**: All services include health monitoring
- **Volume Persistence**: AI models and document data persist across restarts
- **Environment Configuration**: Configurable URLs and ports
- **Automatic Model Download**: Initial setup downloads required AI models

## Updated High-Level Architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Vite)                   │
├──────────────────┬──────────────────┬──────────────────────┤
│   Document       │   AI Analysis    │   Interactive        │
│   Viewer         │   Panel          │   Features           │
│                  │                  │                      │
│ • PDF Viewer     │ • Context        │ • Chat Interface     │
│ • EPUB Viewer    │   Analysis       │ • Note Taking        │
│ • Navigation     │ • Summaries      │ • Highlighting       │
│ • Progress       │ • Insights       │ • Status Tracking    │
└─────────┬────────┴─────────┬────────┴─────────┬────────────┘
          │                  │                  │
          └──────────────────┴──────────────────┘
                             │
                       FastAPI Backend
                             │
        ┌────────────────────┴────────────────────┐
        │                                         │
   Document Services                         AI Services
        │                                         │
   ┌────┴────┐                            ┌─────┴─────┐
   │ PDF     │ EPUB                       │ Ollama    │
   │Service  │Service                     │ Client    │
   └─────────┘                            └───────────┘
        │                                         │
   ┌────┴────┐                              ┌────┴────┐
   │Database │                              │ Ollama  │
   │Service  │                              │ Server  │
   │(SQLite) │                              │(qwen3)  │
   └─────────┘                              └─────────┘
```

## Advanced Features Implemented:

### **Document Management**
1. **Universal Document Support**: Seamless handling of both PDF and EPUB formats
2. **Smart Status Tracking**: Automatic status updates based on reading progress
3. **Thumbnail Generation**: Cached thumbnails for quick library browsing
4. **Reading Progress Persistence**: Resume reading exactly where you left off

### **AI-Powered Features**
1. **Context-Aware Analysis**: AI processes current content with surrounding context
2. **Persistent Chat History**: Conversations maintained per document
3. **Streaming Responses**: Real-time AI response delivery
4. **Local Processing**: Complete privacy with local Ollama models

### **Enhanced Reading Experience**
1. **Highlight System**: Color-coded highlights with persistent storage
2. **Note Management**: Rich note-taking with search capabilities
3. **Navigation Enhancement**: Keyboard shortcuts and intuitive controls
4. **Responsive Design**: Optimized for various screen sizes

### **Data Persistence**
1. **SQLite Database**: Lightweight, file-based persistence
2. **Migration System**: Schema versioning for data integrity
3. **Backup-Friendly**: Simple file-based storage for easy backups

## Technology Stack Summary:

**Frontend:**
- React 19+ with TypeScript
- Vite for fast development and building
- Tailwind CSS for styling
- react-pdf for PDF rendering
- Custom EPUB viewer implementation

**Backend:**
- FastAPI with Python 3.12+
- SQLite for data persistence
- PyMuPDF for PDF processing
- ebooklib for EPUB processing
- Ollama integration for AI capabilities

**Deployment:**
- Docker Compose for orchestration
- Multi-service architecture
- Health checks and monitoring
- Volume persistence

**AI/ML:**
- Ollama with qwen3:30b model
- Local processing for privacy
- Context-aware document analysis
- Streaming response delivery

This architecture provides a production-ready, scalable foundation for intelligent document reading and analysis, with support for multiple document formats and comprehensive AI integration.
