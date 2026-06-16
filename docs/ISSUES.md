# Implementation Issues — Tracer Bullet Slices

## Issue #1: Project scaffold + CLI skeleton
**Type**: AFK | **Blocked by**: None | **User Stories**: 1, 19

### What to build
Set up a Python project with dependency management (pyproject.toml / Poetry), a CLI entry point (Click or Typer), and .env loading (python-dotenv). The CLI should accept a `build` command with a natural-language argument and print a "hello world" placeholder. Include basic project structure: src/, tests/, .env.example.

### Acceptance criteria
- [ ] `pip install -e .` installs the package successfully
- [ ] Running the CLI with `--help` shows usage information
- [ ] Running the CLI `build "some request"` prints a placeholder and exits cleanly
- [ ] .env file loads DEEPSEEK_API_KEY if present
- [ ] Test suite runs with pytest and has at least one passing test

---

## Issue #2: Orchestrator — intent specification
**Type**: AFK | **Blocked by**: #1 | **User Stories**: 2, 25

### What to build
The Orchestrator receives the user's natural-language request, calls the LLM (DeepSeek-V4-Pro) to parse it into a structured intent document (fields: feature description, constraints, target modules, assumptions), and displays the structured result in the terminal for user confirmation or correction. Model selection is read from .env.

### Acceptance criteria
- [ ] Given a natural-language input, the Orchestrator produces a structured intent document
- [ ] The intent document contains all required fields (feature, constraints, target_modules, assumptions)
- [ ] The user can confirm the intent or provide corrections
- [ ] If corrected, the Orchestrator regenerates the intent with corrections incorporated
- [ ] Model name is configurable via .env (e.g., ORCHESTRATOR_MODEL=deepseek-v4-pro)
- [ ] Tests verify intent parsing with mock LLM responses

---

## Issue #3: Pipeline engine + session state + stub PM
**Type**: AFK | **Blocked by**: #2 | **User Stories**: 1, 24

### What to build
Implement the serial pipeline execution engine. The Orchestrator drives a sequence of agent executions, passing each agent's output as input to the next. Include in-memory session state that tracks the confirmed intent, all produced artifacts, and pipeline progress. Integrate a stub PM agent that returns a hardcoded artifact to verify the full pipeline flow end-to-end.

### Acceptance criteria
- [ ] Pipeline executes agents in serial order, passing artifacts between stages
- [ ] Session state holds intent document, artifacts, and progress
- [ ] Stub PM agent receives intent and returns a valid (hardcoded) requirements artifact
- [ ] The full pipeline (intent → stub PM → output) runs end-to-end
- [ ] Pipeline progress is logged (which stage is executing)
- [ ] Tests verify pipeline ordering and state management with stub agents

---

## Issue #4: Tool access layer
**Type**: AFK | **Blocked by**: #3 | **User Stories**: 18, 26

### What to build
Define a tool interface that agents use to interact with the codebase instead of direct filesystem access. Implement core tools: read_file, write_file, list_directory, search_symbol. Each tool has a permission model. Tool permission maps per role are defined as code constants. Unauthorized tool invocations raise a permission error.

### Acceptance criteria
- [ ] Tool interface is defined with a consistent invoke(tool_name, args) pattern
- [ ] read_file, write_file, list_directory tools are implemented
- [ ] Each role has a defined tool permission set (code constants)
- [ ] Invoking an unauthorized tool raises a clear permission error
- [ ] Tests verify that permitted tools succeed and unauthorized tools fail
- [ ] Tests verify tool operations against a temporary filesystem

---

## Issue #5: PM Agent (requirements analysis)
**Type**: AFK | **Blocked by**: #4 | **User Stories**: 3, 14

### What to build
Implement the PM agent with a system prompt defining its identity and responsibilities, and an artifact schema for its output (user stories, acceptance criteria, priority, dependencies). The PM agent consumes the confirmed intent document and produces a structured requirements artifact. The artifact includes both structured data (JSON) and a human-readable summary. Replace the stub PM from #3.

### Acceptance criteria
- [ ] PM agent has a system prompt stored as a code constant
- [ ] PM agent produces an artifact conforming to the requirements schema
- [ ] Artifact includes structured data (user_stories[], acceptance_criteria[]) and a summary
- [ ] PM agent is integrated into the pipeline (replacing the stub)
- [ ] Tests verify artifact schema conformance with mock LLM responses
- [ ] Tests verify the PM agent handles edge cases (vague input, very long input)

---

## Issue #6: Project context — iteration mode
**Type**: AFK | **Blocked by**: #5 | **User Stories**: 16, 17

### What to build
Implement the two-step project context generation for existing codebases: (1) a rule-based scanner that extracts structural data (file tree, dependencies from pyproject.toml/package.json, class/function signatures via AST parsing), and (2) an LLM refinement step that converts structural data into a semantic project summary. The Orchestrator auto-detects whether a project directory exists and selects Greenfield (empty context) or Iteration (scan + summarize) mode.

### Acceptance criteria
- [ ] Rule-based scanner extracts directory tree, dependencies, and function signatures
- [ ] LLM refinement produces a semantic summary from structural data
- [ ] Orchestrator auto-detects Greenfield vs Iteration mode based on project directory
- [ ] Project summary is injected into all agents' initial context
- [ ] Tests verify scanner output against a sample project structure
- [ ] Tests verify mode detection (directory exists → Iteration, no directory → Greenfield)

---

## Issue #7: Architect Agent (architecture design)
**Type**: AFK | **Blocked by**: #5, #6 | **User Stories**: 4, 14

### What to build
Implement the Architect agent with a system prompt and artifact schema. It consumes the PM's requirements artifact (and project context in Iteration mode) and produces an architecture artifact containing module breakdown, interface definitions, technology choices, and data flow descriptions. Both structured data and summary formats.

### Acceptance criteria
- [ ] Architect agent has a system prompt stored as a code constant
- [ ] Architect agent produces an artifact conforming to the architecture schema
- [ ] Artifact includes modules[], interfaces[], tech_choices[], and a summary
- [ ] Architect agent consumes PM artifact and project context (if available)
- [ ] Tests verify artifact schema conformance with mock LLM responses
- [ ] Tests verify the Architect agent handles both Greenfield and Iteration contexts

---

## Issue #8: Coder Agent (coding implementation)
**Type**: AFK | **Blocked by**: #7 | **User Stories**: 5, 14, 15

### What to build
Implement the Coder agent with a system prompt and write_file tool permissions. It consumes the Architect's artifact and produces code files via the tool access layer. The Coder artifact includes both the code files written (structured data: file paths + contents) and a summary of what was implemented.

### Acceptance criteria
- [ ] Coder agent has a system prompt stored as a code constant
- [ ] Coder agent has write_file and read_file tool permissions
- [ ] Coder agent produces code files that conform to the architecture specification
- [ ] Code artifact includes file list (paths + contents) and a summary
- [ ] In Greenfield mode, Coder creates project scaffolding + implementation
- [ ] In Iteration mode, Coder modifies/extends existing codebase
- [ ] Tests verify that produced files are syntactically valid

---

## Issue #9: Artifact validation + error handling
**Type**: AFK | **Blocked by**: #8 | **User Stories**: 11, 21, 22

### What to build
Implement artifact validation schemas for each role (PM, Architect, Coder). Validation runs after each agent produces an artifact. If validation fails, the error is fed back to the agent for a retry (with error context injected into the prompt). After a configurable max retry count, the system escalates to the user with the intermediate artifact and error context for manual decision (correct, skip, or abort).

### Acceptance criteria
- [ ] Validation schemas exist for each role's artifact (required fields, type checks, content rules)
- [ ] Invalid artifacts trigger a retry with error feedback
- [ ] Retry count is configurable and respected
- [ ] Exhausted retries escalate to the user with artifact + error context
- [ ] User can choose to correct, skip, or abort on escalation
- [ ] Tests verify valid artifacts pass and invalid artifacts trigger retries
- [ ] Tests verify escalation after max retries

---

## Issue #10: Reviewer Agent + Coder ↔ Reviewer feedback loop
**Type**: AFK | **Blocked by**: #8, #9 | **User Stories**: 6, 8, 10, 23

### What to build
Implement the Reviewer agent with a system prompt, read-only tool permissions, and a review artifact schema (issues list with severity, location, suggestion). Implement the Coder ↔ Reviewer feedback loop: if the Reviewer finds issues, the Orchestrator routes them back to the Coder for fixes, then re-runs the Reviewer. Loop is capped at a configurable max retry count. If the Reviewer identifies a fundamental architecture issue, the system recommends global rollback to the user.

### Acceptance criteria
- [ ] Reviewer agent has a system prompt and read-only tool permissions
- [ ] Reviewer produces a review artifact with issues[], severity, and recommendations
- [ ] Feedback loop routes review issues back to Coder and re-runs Reviewer
- [ ] Loop respects max retry count and escalates when exhausted
- [ ] Fundamental issues trigger a global rollback recommendation to the user
- [ ] Tests verify the feedback loop activates on review failures
- [ ] Tests verify the loop terminates after max retries

---

## Issue #11: Tester Agent + Coder ↔ Tester feedback loop
**Type**: AFK | **Blocked by**: #10 | **User Stories**: 7, 9, 10

### What to build
Implement the Tester agent with a system prompt, run_test and read_file tool permissions, and a test artifact schema (test files generated, test results, coverage). Implement the Coder ↔ Tester feedback loop: if tests fail, the Orchestrator routes failure details to the Coder for fixes, then re-runs the Tester. Loop capped at max retry count.

### Acceptance criteria
- [ ] Tester agent has a system prompt and run_test/read_file tool permissions
- [ ] Tester produces a test artifact with test_files[], results, and summary
- [ ] Tester can execute tests and capture pass/fail results
- [ ] Feedback loop routes test failures to Coder and re-runs Tester
- [ ] Loop respects max retry count and escalates when exhausted
- [ ] Tests verify the feedback loop activates on test failures
- [ ] Tests verify the loop terminates after max retries

---

## Issue #12: Intervention system (user-selectable checkpoints)
**Type**: AFK | **Blocked by**: #11 | **User Stories**: 12, 13

### What to build
Implement optional user intervention at any stage boundary. Before each stage transition, if the user has opted in to review at that checkpoint, the pipeline pauses and displays the current artifact. The user can inspect, modify (via inline editing or replacement), or approve to continue. If no intervention is configured for a checkpoint, the pipeline auto-advances.

### Acceptance criteria
- [ ] User can configure which checkpoints to pause at (all, none, or specific stages)
- [ ] At a configured checkpoint, the pipeline pauses and displays the artifact
- [ ] User can approve (continue), modify (edit and continue), or abort
- [ ] Non-configured checkpoints auto-advance without pausing
- [ ] Modified artifacts are re-validated before continuing
- [ ] Tests verify pause/resume behavior at configured checkpoints
- [ ] Tests verify auto-advance at non-configured checkpoints

---

## Issue #13: Streaming progress + CLI polish
**Type**: AFK | **Blocked by**: #12 | **User Stories**: 19, 20

### What to build
Polish the CLI experience with streaming progress output: show which agent is currently executing, display artifact summaries as they complete, use color coding for stages (e.g., green for success, yellow for warnings, red for errors), and provide clean error messages. Add proper exit codes (0 for success, 1 for user abort, 2 for error).

### Acceptance criteria
- [ ] CLI streams real-time progress (current stage, agent name, elapsed time)
- [ ] Artifact summaries are displayed as each stage completes
- [ ] Color coding distinguishes success, warning, and error states
- [ ] Error messages are user-friendly and actionable
- [ ] Exit codes: 0 (success), 1 (user abort), 2 (error/escalation)
- [ ] Tests verify exit codes for different pipeline outcomes
