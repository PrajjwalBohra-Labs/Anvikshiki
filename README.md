# Anvikshiki

**Status: Building phase**

Anvikshiki is a sophisticated, locally-hosted AI-powered conversation system designed to provide intelligent dialogue capabilities with advanced reasoning, research, and memory management. Built with FastAPI on the backend and Vite + React on the frontend, it's currently under active development with breaking changes possible as we refine the architecture.

## What is Anvikshiki?

Think of Anvikshiki as a conversational AI engine that goes beyond simple chat. It's designed to handle complex dialogues with features like conversation memory, semantic context building, multi-step reasoning, and real-time web search integration. The system intelligently manages conversation context, validates inputs against prompt injection attacks, and provides observable, traceable interactions through comprehensive logging and event streaming.

## Project Structure

The codebase is organized into clear, functional domains:

- **`app/`** — Core backend implementation with modular architecture
- **`frontend/`** — React-based UI with real-time communication
- **`data/`** — Local runtime artifacts, vector stores, and persistent caches (git-ignored)
- **`tests/`** — Comprehensive automated test suite covering services, integrations, and end-to-end flows
- **`.env.example`** — Template for environment configuration
- **`requirements.txt`** — Python dependencies with pinned versions

## Backend Architecture

The backend is organized around a service-oriented architecture with clear separation of concerns:

**Core Services:**
- **Conversation Management** — Handles session lifecycle, conversation state, and event-based message flow
- **Generation Engine** — Orchestrates LLM calls with safety checks, retry logic, and graceful degradation
- **Memory & Context** — Manages conversation history, semantic context building, and memory recall through vector embeddings
- **Reasoning & Planning** — Implements multi-step reasoning chains and task decomposition
- **Research & Retrieval** — Integrates web search capabilities and knowledge base retrieval with caching
- **Intent Analysis & Validation** — Analyzes user input, detects intent, and applies prompt injection protection

**Infrastructure Layer:**
- **Event Bus** — Async-first event streaming for decoupled component communication
- **Cache Layer** — Smart caching with Redis integration for fast retrieval and LLM responses
- **LLM Adapter** — Abstraction layer for different LLM providers (Claude, GPT, etc.)
- **Vector Store** — Semantic search and embedding storage for retrieval augmented generation
- **Observability** — Request tracing, structured logging, and performance monitoring
- **Security** — Rate limiting, authentication, audit logging, and prompt sanitization
- **Persistence** — Multi-storage strategy combining SQLite for structure, files for documents, and vectors for embeddings

The backend uses FastAPI's async capabilities extensively, allowing high-concurrency handling without blocking. Request tracing propagates context through the entire call stack, making it easy to debug and monitor production issues.

**Frontend Integration:**
The frontend communicates via REST endpoints and maintains real-time state synchronization. The API is designed for both human-readable responses and structured data for UI rendering.

## Local Development Setup

Getting Anvikshiki running locally is straightforward, but there are a few things to configure:

**Backend Setup:**

1. Create and activate a Python virtual environment (Python 3.9+):
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Configure your environment:
   ```bash
   cp .env.example .env
   ```
   Update `.env` with your LLM API keys (Claude, OpenAI, etc.), database paths, and any external service credentials. The system will gracefully degrade if optional services like web search aren't configured.

**Frontend Setup:**

1. Install Node dependencies (Node 16+):
   ```bash
   cd frontend
   npm install
   ```

2. The frontend uses Vite for lightning-fast development builds and HMR (Hot Module Reloading).

## Running the System

**Start the Backend:**

```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` with auto-reloading on file changes during development. The `/docs` endpoint provides interactive Swagger documentation of all available endpoints. Behind the scenes, the system initializes the event bus, cache connections, vector store indices, and database migrations.

**Start the Frontend:**

```bash
cd frontend
npm run dev
```

Vite typically serves on `http://localhost:5173` with instant HMR feedback. The frontend consumes the backend API and handles real-time conversation display, request queueing, and optimistic UI updates.

## Testing Strategy

Anvikshiki includes a comprehensive test suite covering unit tests, integration tests, and end-to-end scenarios:

```bash
pytest -q
```

The test suite includes:
- **Unit Tests** — Individual service and component testing
- **Integration Tests** — Cache behavior, database operations, event bus messaging
- **API Tests** — HTTP endpoint validation and response schemas
- **Conversation Flow Tests** — Full dialogue scenarios with memory recall and context building
- **Security Tests** — Prompt injection detection, rate limiting, input sanitization
- **Observability Tests** — Request tracing and structured logging validation
- **Performance Benchmarks** — Latency and throughput measurements for critical paths
- **Live Integration Tests** — Real LLM calls for regression testing (runs only with specific flags)

Tests use pytest fixtures for setup, context management, and teardown. The test data includes realistic conversation scenarios and edge cases.

## Key Technical Features

**Retrieval-Augmented Generation (RAG)**
- Hybrid semantic + keyword retrieval from a local knowledge base
- Document ingestion pipeline: parse → validate → chunk → normalize → embed → index → store
- Retrieval cache to avoid re-embedding identical queries
- Vector store (SQLite with embeddings) for efficient semantic search
- Metadata-based filtering for precise document retrieval
- Web augmentation available as an opt-in enhancement to local knowledge
- Support for multiple document formats with configurable parsers

**Sophisticated Memory Architecture (7-Tier System)**
- **In-Process Tiers**: Working Memory, Dialogue Memory, Session Memory (cleared on restart)
- **Persistent Tiers**: Concept Memory, Project Memory, Research Memory, System Memory
- Memory pipeline: Extraction → Classification → Persistence
- Automatic memory classification with tier hints
- Event-driven memory updates for real-time synchronization
- Scoped memory access (per-conversation, per-user, or global)

**Multi-Stage Execution Planning**
- Intent-driven execution planning with 8 strategic steps:
  1. Clarification detection (if user input needs disambiguation)
  2. Retrieval (if knowledge base lookup is needed)
  3. Tool invocation (for external integrations)
  4. Reasoning (for complex multi-step problems)
  5. Response generation (LLM synthesis)
  6. Validation (citation & consistency checking)
  7. Uncertainty exposure (honest limitation acknowledgment)
  8. Memory update (long-term learning)
- Rule-based planning (no LLM calls during planning phase) for deterministic behavior

**Advanced Reasoning Engine**
- 10-layer reasoning pipeline:
  - Problem decomposition
  - Definition extraction from concept memory
  - Fact gathering from retrieved evidence
  - Evidence sourcing with document attribution
  - Assumption extraction and surfacing
  - Constraint identification and enforcement
  - Relationship mapping across concepts
  - Comparative analysis across sources
  - Inference chain building
  - Alternative hypothesis generation
- Confidence scoring with 5-component breakdown:
  - Source availability (quantity of evidence)
  - Agreement among sources (consistency/divergence)
  - Reasoning completeness (coverage of problem space)
  - Context quality (relevance of available context)
  - Retrieval quality (score averaging from semantic search)
- Automatic detection of contradictions between sources

**Layered Prompt Engineering**
- 7-layer prompt orchestration (each layer is independently composable):
  1. System role definition
  2. Architecture policy (core system constraints)
  3. Module policy (per-query instructions)
  4. Task instructions (specific ask)
  5. Retrieved knowledge (sourced evidence)
  6. Conversation history (multi-turn context)
  7. User message (current question)
- Empty layers are automatically omitted
- Injection sanitization on all user inputs and retrieved documents
- Confidence scoring injection into the prompt
- Distinction between LOCAL (ingested) and WEB (external) evidence

**Multi-Stage Validation Pipeline**
- Citation validation: every reference must match retrieved sources
- Consistency checking: claimed confidence scores must match computed scores
- Confidence language validation: low-confidence responses must expose uncertainty
- Completeness checking: responses must acknowledge when evidence is absent
- Forced validation before response delivery (never bypassed)
- Generate-and-validate pattern enforces validation as mandatory step

**Reflection Engine**
- Post-generation reflection checks:
  - Insufficient evidence detection
  - Confidence/tone mismatch identification
  - Citation accuracy verification
  - Uncertainty exposure validation
  - Completeness of evidence acknowledgment

**Intelligent Conversation Management**
- Maintains multi-turn dialogue context with semantic awareness
- Session-based state management with automatic persistence
- Conversation events bubble through the system for real-time updates
- Dialogue state machine (multi-stage conversation tracking)
- Turn-by-turn result tracking and event publishing

**Intent Analysis & Task Classification**
- Automatic task type detection (research, chat, clarification, tool invocation)
- Clarification need detection (ambiguous queries flagged)
- Retrieval necessity scoring (determines if lookup needed)
- Tool invocation classification
- Confidence scoring per intent decision

**Research Pipeline**
- Multi-stage research for complex questions:
  1. Question decomposition into sub-questions
  2. Parallel search across local knowledge base and web
  3. Evidence comparison and contradiction detection
  4. Evidence synthesis with LLM
  5. Reference generation with source attribution
  6. Validation of synthesized response
- Research memory persistence for future recall
- Source ranking (local > web, by confidence)

**Safety & Security**
- Prompt injection detection and sanitization on all user inputs and retrieved documents
- Rate limiting per user and endpoint
- Request-level audit logging
- Authentication hooks for API security
- Document injection awareness (retrieved texts are sanitized before prompt insertion)

**Research Integration**
- Real-time web search augmentation via Tavily or similar providers
- Hybrid local + web evidence synthesis
- Caching of search results to avoid redundant queries
- Semantic matching between user queries and retrieved documents
- Citation validation to prevent hallucinated references
- Explicit LOCAL/WEB distinction in evidence sourcing

**Error Handling & Graceful Degradation**
- System continues functioning even if external services (search, LLM fallbacks) are unavailable
- Automatic retry logic with exponential backoff (3 attempts, 0.5s base delay)
- LLMProviderError handling across all adapter calls
- Fallback responses for degraded conditions
- Honest acknowledgment of insufficient evidence rather than fabrication
- LLM adapter abstraction for provider switching

**Context Building & Token Management**
- Automatic context assembly with token estimation
- Conversation history formatting
- Retrieved chunk formatting with source attribution
- Concept graph formatting for relationship visualization
- Project state inclusion (if applicable)
- Token budget enforcement and overflow prevention

**Observability & Tracing**
- Request tracing with correlation IDs across async boundaries
- Structured logging with context propagation
- Performance metrics and timing information
- Retrieval quality metrics and confidence scoring
- Cache hit/miss tracking
- Event-driven observability (all major operations publish events)
- Failure tracking and error categorization

**Event-Driven Architecture**
- Async-first event bus for decoupled component communication
- Named events for all major operations:
  - Document ingestion (DocumentImported, EmbeddingCreated)
  - Memory operations (MemoryUpdated)
  - Conversation state changes (ConversationStarted)
  - Cache operations
- Event logging for observability and debugging
- Proper event ordering and causality tracking

**Caching Strategy**
- Multi-level caching system:
  - **Retrieval Cache**: Identical queries return cached results without re-embedding
  - **Embedding Cache**: Cached embeddings avoid re-computation
  - **Prompt Cache**: LLM prompt caching (if provider supports)
- Cache invalidation on document updates (automatic)
- LRU eviction policies for memory efficiency

## Development Notes

- The project is actively under development, and the architecture continues to evolve. Breaking changes may occur as we refine the design.
- All services are built async-first using FastAPI, allowing efficient handling of I/O-heavy operations.
- The event-driven architecture enables loosely coupled services that can be developed and tested independently.
- State management is centralized through the persistence layer, making it easy to add new features without breaking existing functionality.

## Future Enhancements

Planned or under consideration:

- **Model Context Protocol (MCP)** — Integration of MCP servers for standardized tool use and extended context sources
- **Fine-tuning Pipelines** — On-device model fine-tuning with conversation data for personalized responses
- **Advanced Planning** — Multi-step planning with dependency graphs and task scheduling
- **Plugin System** — Pluggable adapters for custom knowledge sources and external services
- **Distributed Deployment** — Multi-node setup with shared state management
