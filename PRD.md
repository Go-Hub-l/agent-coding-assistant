## Problem Statement

Individual developers working on software projects lack a structured team to handle different aspects of the development lifecycle. When building features — whether from scratch or iterating on existing codebases — they must personally manage requirements analysis, architecture design, coding, code review, and testing. This context-switching is mentally taxing and error-prone, especially for solo developers who have no peers to review their work or challenge their architectural decisions. Existing AI coding assistants operate as a single monolithic agent, lacking the specialized role differentiation and structured pipeline that a real development team provides.

## Solution

A multi-agent CLI programming assistant that simulates a virtual development team for individual developers. The system consists of six specialized agents — an Orchestrator plus five role agents (PM, Architect, Coder, Reviewer, Tester) — that execute in a serial pipeline. The user provides a natural-language request, the Orchestrator structures it into a confirmed intent document, and the pipeline runs each agent in sequence, producing structured artifacts at each stage. The user can optionally intervene at any stage boundary to inspect or modify intermediate results. The system supports both greenfield project creation and iteration on existing codebases.

## User Stories

1. As a solo developer, I want to describe a feature in natural language and have a team of AI agents execute the full development lifecycle, so that I can produce higher-quality code with less manual effort
2. As a solo developer, I want the system to parse my vague request into a structured intent document before starting work, so that I can confirm or correct the scope before any agent begins
3. As a solo developer, I want a PM agent to analyze my request and produce structured requirements with user stories and acceptance criteria, so that the downstream agents have a clear specification to work from
4. As a solo developer, I want an Architect agent to produce a technical design with module breakdown, interface definitions, and technology choices, so that the Coder has a sound blueprint to implement
5. As a solo developer, I want a Coder agent to implement code based on the architecture artifact, so that I get working code aligned with the design
6. As a solo developer, I want a Reviewer agent to examine the generated code for quality, security, and style issues, so that problems are caught before I merge the code
7. As a solo developer, I want a Tester agent to generate and run tests against the generated code, so that I can verify correctness automatically
8. As a solo developer, I want the Reviewer and Coder to form a local feedback loop where review issues are automatically sent back for fixes, so that minor problems are resolved without my intervention
9. As a solo developer, I want the Tester and Coder to form a local feedback loop where test failures trigger automatic fixes, so that simple bugs are corrected without manual effort
10. As a solo developer, I want feedback loops to be capped at a maximum retry count, so that the system doesn't get stuck in an infinite correction cycle
11. As a solo developer, I want to be notified when feedback loops are exhausted without resolution, so that I can decide whether to manually fix, skip, or abort
12. As a solo developer, I want to optionally pause the pipeline at any stage boundary to inspect or modify an artifact, so that I can catch direction errors early without slowing down the default flow
13. As a solo developer, I want the pipeline to auto-advance by default when I don't intervene, so that I'm not forced to approve every step
14. As a solo developer, I want each agent's output to include both structured data (for downstream agents) and a human-readable summary (for me), so that both machine and human consumers are served
15. As a solo developer, I want to start a brand-new project from scratch using the system, so that I can scaffold complete applications with AI assistance
16. As a solo developer, I want to iterate on an existing codebase by having the system understand the project structure first, so that new code integrates correctly with what already exists
17. As a solo developer, I want the system to automatically generate a project summary (directory structure, tech stack, key modules) when working on an existing project, so that all agents have shared context about the codebase
18. As a solo developer, I want agents to access the codebase through a permission-scoped tool layer rather than raw filesystem access, so that the Reviewer can't accidentally modify code and the Coder can only write to appropriate directories
19. As a solo developer, I want to see streaming progress output in the terminal as each agent works, so that I understand what's happening at any given moment
20. As a solo developer, I want to configure which LLM model each agent uses via environment variables, so that I can optimize model selection per role (e.g., a code-specialized model for Coder)
21. As a solo developer, I want each agent's artifact to be validated against role-specific rules before passing downstream, so that malformed outputs don't corrupt the entire pipeline
22. As a solo developer, I want failed agent outputs to be retried with error feedback rather than blindly resent, so that retries have a higher chance of success
23. As a solo developer, I want the system to recommend a global rollback to an earlier stage when a fundamental issue is detected, so that I'm informed when the problem is bigger than a local fix
24. As a solo developer, I want to be able to resume an interrupted session within the same CLI session, so that a temporary disruption doesn't force me to start over
25. As a solo developer, I want the system to support configuring API keys and model names in a .env file, so that I can switch environments without modifying code
26. As a solo developer, I want system prompts and tool permissions to be defined as code constants, so that role behavior is version-controlled and reproducible

## Implementation Decisions

**Agent Architecture**: Six agents total — one Orchestrator and five role agents (PM, Architect, Coder, Reviewer, Tester). Each role agent maps 1:1 to a lifecycle stage. No role merging. The Orchestrator is the sole user-facing entry point; users never interact with role agents directly.

**Pipeline Execution**: Serial execution order: PM → Architect → Coder → Reviewer → Tester. Parallel execution is explicitly deferred to a future iteration. The Orchestrator manages execution order and context passing between stages.

**Feedback Loop Strategy (ADR-0001)**: Local-only feedback loops between adjacent stages — Coder ↔ Reviewer and Coder ↔ Tester. Capped at a configurable maximum retry count. Global rollback (e.g., back to Architect) is not automatic; it surfaces as a recommendation to the user.

**Artifact Format**: Each agent produces a hybrid artifact consisting of structured core data (machine-parseable, consumed by downstream agents) and a natural-language summary (human-readable, shown to the user). The structured data follows a schema specific to each role.

**Intent Specification**: The Orchestrator converts the user's natural-language request into a structured intent document, extracts key fields (feature description, constraints, target modules, assumptions), and presents it for a single confirmation/correction round. Once confirmed, the intent document drives the pipeline with no further clarification rounds.

**Tool Access Layer**: Agents interact with the codebase through a permission-scoped tool layer (e.g., read_file, write_file, run_command, search_symbol). Each role has a distinct tool permission set defined as code constants. Agents never access the filesystem directly.

**Project Modes**: Two operating modes — Greenfield (no existing codebase, project built from scratch) and Iteration (existing codebase, project summary + on-demand retrieval). The Orchestrator auto-detects the mode at startup.

**Project Context Generation**: In Iteration mode, a two-step process generates the project summary: (1) rule-based scanning extracts structural data (file tree, dependencies, class/function signatures) using tools like tree-sitter, (2) an LLM refines the structural data into a semantic summary. This summary is injected into all agents' initial context.

**Role Specialization**: System prompts define each agent's identity, responsibilities, output format, constraints, and behavioral guidelines. Prompts are stored as code constants. External knowledge bases are deferred as a future extension.

**Model Configuration**: DeepSeek-V4-Pro as the default model. Each agent role can be independently configured to use a different model via .env file variables (e.g., ORCHESTRATOR_MODEL, CODER_MODEL). API keys also configured via .env.

**Error Handling**: Two-layer strategy — (1) artifact output validation against role-specific rules (schema conformance, syntax checks) with error-feedback-injected retries, (2) escalation to the user after retry budget exhaustion, presenting intermediate artifact and error context for manual decision.

**Session State**: In-memory state for the duration of a single CLI session — intent document, all artifacts, pipeline progress, feedback loop history. Supports pause, intervention, and resume. No cross-session persistence in the MVP.

**User Interface**: CLI tool built with Python (e.g., Click or Typer). Streaming output shows pipeline progress, current agent, and artifact summaries. User interactions (intent confirmation, intervention, error escalation) use stdin/stdout prompts.

**Implementation Order**: Orchestrator first (pipeline backbone, intent specification, session state, CLI framework), then PM, Architect, Coder, Reviewer, and Tester — each integrated into the existing pipeline and validated end-to-end before moving to the next.

## Testing Decisions

**Testing Philosophy**: Tests should validate external behavior (pipeline input → artifact output), not internal implementation details (which prompt was used, how many LLM calls were made).

**Orchestrator Tests**: Validate the full pipeline flow — given a natural-language input, verify the intent document structure, stage-by-stage artifact progression, feedback loop activation, and final aggregated output. Mock LLM responses to test orchestration logic deterministically.

**Agent Role Tests**: For each role agent, validate that given a well-formed upstream artifact, the agent produces a valid artifact conforming to its role-specific schema. Use mock LLM responses for deterministic testing.

**Feedback Loop Tests**: Verify that when a Reviewer/Tester artifact contains issues, the Coder is re-invoked with the feedback, and the loop respects the maximum retry count. Verify that exhausted loops produce the correct escalation signal.

**Tool Access Tests**: Verify that each role can only invoke its permitted tools. Attempting unauthorized tool access should raise a permission error.

**Error Handling Tests**: Verify that malformed artifact outputs trigger validation errors and error-feedback retries. Verify that exhausted retry budgets escalate to the user with correct context.

**Project Context Tests**: In Iteration mode, verify that the rule-based scanner extracts correct structural data and that the project summary is well-formed. In Greenfield mode, verify that the project context starts empty and accumulates as artifacts are produced.

**CLI Integration Tests**: End-to-end tests that invoke the CLI with a natural-language command and verify stdout output includes progress streaming, artifact summaries, and correct exit codes.

## Out of Scope

- Deployment and operations (CI/CD, containerization, monitoring)
- Parallel execution of pipeline stages (deferred to post-MVP)
- Cross-session state persistence
- Web UI or IDE plugin interfaces
- Multi-model orchestration within a single agent role
- External knowledge base integration for role specialization
- Global rollback automation (back to Architect/PM)
- Team/multi-user scenarios
- Fine-tuning of LLM models

## Further Notes

- The project uses Python as the implementation language with a CLI framework such as Click or Typer.
- DeepSeek-V4-Pro is the default LLM, chosen for its cost-effectiveness and code generation capabilities. The system is designed to allow per-agent model configuration via .env for future flexibility.
- The .env configuration approach for models follows the principle of keeping secrets and environment-specific values out of version control, while system prompts and tool permissions are code constants to ensure reproducibility.
- ADR-0001 documents the decision to use local-only feedback loops. This is the most architecturally significant decision as it affects the orchestration engine's state machine design.
- The sequential implementation order (Orchestrator → PM → Architect → Coder → Reviewer → Tester) means each agent can be validated in isolation before integration, reducing debugging complexity.
