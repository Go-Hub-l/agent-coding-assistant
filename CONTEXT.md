# Multi-Agent Programming Assistant

A multi-agent system that simulates a development team for individual developers. MVP uses serial execution (PM → Architect → Coder → Reviewer → Tester) orchestrated by a coordinator agent, with parallel execution as a future extension.

## Language

**Target User**:
An individual developer who directs a virtual team of agents to handle different aspects of software development.
_Avoid_: End user, customer, non-technical user

**Lifecycle Stage**:
A discrete phase in the software development process that one or more agents specialize in. The five stages in scope are: Requirements Analysis, Architecture Design, Coding Implementation, Code Review, and Testing. Deployment and operations are explicitly out of scope.
_Avoid_: Phase, step, task

**Agent Role**:
A specialized agent with a single lifecycle stage responsibility. The five roles are: PM (Requirements Analysis), Architect (Architecture Design), Coder (Coding Implementation), Reviewer (Code Review), Tester (Testing). One role per stage, no role merging.
_Avoid_: Persona, bot, worker

**Orchestrator**:
A coordinator agent that receives the user's intent, decomposes it into tasks for the five role agents, manages execution order and context passing, and aggregates their outputs into a coherent deliverable. The user interacts only with the Orchestrator.
_Avoid_: Dispatcher, router, controller

**Artifact**:
The output of an agent at a lifecycle stage, consisting of structured core data (machine-parseable, consumed by downstream agents) and a natural-language summary (human-readable, shown to the user). Each agent produces one artifact and consumes the upstream artifact(s).
_Avoid_: Document, output, payload

**Intervention**:
A user-initiated pause at any lifecycle stage boundary to inspect or modify an artifact before the pipeline continues. The default behavior is auto-advance; the user opts in to review at specific checkpoints. If no intervention occurs, the pipeline flows uninterrupted.
_Avoid_: Approval gate, checkpoint, gate

**Tool Access**:
A permission-scoped tool layer through which agents interact with the codebase. Agents never access the filesystem directly; they invoke tools (e.g. read_file, write_file, run_command) whose availability is restricted per role. The Orchestrator controls each role's tool permissions.
_Avoid_: Direct file access, raw filesystem, sandbox

**Feedback Loop**:
A local retry cycle between adjacent stages: Coder ↔ Reviewer and Coder ↔ Tester. When a downstream agent finds issues, the Orchestrator routes the feedback back to Coder for fixes, then re-runs the downstream check. Capped at a maximum retry count to prevent infinite loops. Global rollback (e.g. back to Architect) is not automatic — it surfaces as a recommendation to the user.
_Avoid_: Global rollback, full pipeline retry

**Interface**:
The user-facing entry point of the system. MVP is a CLI tool — the user invokes commands in the terminal, and the system streams pipeline progress and results to stdout. Web UI or IDE plugins are future extensions.
_Avoid_: Dashboard, web app, GUI

**Tech Stack**:
Python as the implementation language, chosen for its rich AI/LLM ecosystem and rapid prototyping. The CLI entry point is built with a Python CLI framework (e.g. Click or Typer).
_Avoid_: TypeScript, Rust, Go

**LLM**:
DeepSeek-V4-Pro as the default model. Each agent role can be independently configured to use a different model, allowing optimization per role (e.g. a code-specialized model for Coder, a reasoning-heavy model for Architect). Model selection is part of the agent configuration.
_Avoid_: Single-model-only, hardcoded model

**Role Specialization**:
The mechanism by which each agent acquires its domain expertise. In the MVP, specialization is achieved entirely through system prompts — each role has a carefully crafted prompt defining its identity, responsibilities, output format, constraints, and behavioral guidelines. Tool access boundaries further reinforce role differentiation. External knowledge bases are reserved as a future extension.
_Avoid_: Fine-tuning, external knowledge base (in MVP)

**Project Mode**:
The operating mode determined by whether an existing codebase is present. In Greenfield mode, the system creates a project from scratch — no prior context exists. In Iteration mode, the system works against an existing codebase using a project summary and on-demand retrieval. The Orchestrator detects the mode at startup.
_Avoid_: New vs. existing, create vs. edit

**Project Context**:
A condensed representation of an existing codebase used in Iteration mode, consisting of a project summary (directory structure, tech stack, key modules, entry points) generated once at startup, plus on-demand retrieval tools (e.g. read_file, search_symbol) for agents to drill into specific files during execution. The summary is generated in two steps: rule-based scanning extracts structural data (file tree, dependencies, class/function signatures), then an LLM refines it into a semantic summary. In Greenfield mode, project context is empty and built up as agents produce artifacts.
_Avoid_: Codebase dump, full code injection, RAG-only

**Intent Specification**:
The process of converting the user's natural-language request into a structured intent document. The Orchestrator parses the user's input, extracts key fields (feature description, constraints, target modules, assumptions), and presents the structured result for user confirmation or correction. Once confirmed, the intent document drives the pipeline — no further clarification rounds occur during execution.
_Avoid_: Multi-turn interrogation, form-filling, free-text-only

**Error Handling**:
A two-layer resilience strategy. The first layer validates each agent's artifact output against role-specific rules (e.g. schema conformance, syntax checks) and retries with error feedback injected if validation fails. The second layer escalates to the user after the retry budget is exhausted, presenting the intermediate artifact and error context so the user can manually correct, skip, or abort. Blind retries without error feedback are never used.
_Avoid_: Blind retry, silent failure, infinite retry

**Session State**:
In-memory state maintained for the duration of a single CLI session, including the confirmed intent document, all produced artifacts, pipeline progress, and feedback loop history. Supports pause, intervention, and resume within one session. State is discarded when the session ends. Cross-session persistence is reserved as a future extension.
_Avoid_: Persistent storage, database, cross-session memory

**Configuration**:
The split between runtime-volatile and code-baked settings. Model selection (API keys, model names per agent) lives in a .env file, allowing per-environment overrides without code changes. System prompts and tool permission definitions live as code constants, versioned with the codebase and changed only through code releases.
_Avoid_: Database-backed config, remote config service, YAML files

**Implementation Order**:
The sequential build order of agents: Orchestrator first (pipeline backbone, intent specification, session state), then PM, Architect, Coder, Reviewer, and Tester in pipeline order. Each new agent is integrated into the existing pipeline and validated end-to-end before moving to the next.
_Avoid_: Parallel agent development, bottom-up
