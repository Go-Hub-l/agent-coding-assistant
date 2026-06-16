# Local-only feedback loops between adjacent stages

The pipeline is a serial chain (PM → Architect → Coder → Reviewer → Tester), but issues found downstream need fixing. We chose local feedback loops (Coder ↔ Reviewer, Coder ↔ Tester) capped at a max retry count, rather than global rollback that could cascade back to Architect or PM. Global rollback is exposed as a recommendation to the user, who decides whether to restart from an earlier stage. This keeps the orchestration logic predictable in the MVP while still handling the most common correction patterns.

**Considered Options**: Pure one-way pipeline (no retry); local loops only (chosen); full global rollback between any stages.

**Consequences**: If a fundamental architecture flaw is discovered during Review or Testing, the system cannot self-correct — it must surface the issue and let the user decide. This is acceptable for MVP but may feel limiting as agent capabilities improve.
