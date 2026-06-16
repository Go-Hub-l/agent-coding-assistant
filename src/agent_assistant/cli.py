"""CLI entry point for the Agent Coding Assistant."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import SpinnerColumn, TextColumn, Progress
from rich.table import Table

from agent_assistant.agents.architect import ArchitectAgent
from agent_assistant.agents.coder import CoderAgent
from agent_assistant.agents.pm import PMAgent
from agent_assistant.agents.reviewer import ReviewerAgent
from agent_assistant.agents.tester import TesterAgent
from agent_assistant.config import load_config
from agent_assistant.llm.client import LLMClient
from agent_assistant.orchestrator.intent import correct_intent, parse_intent
from agent_assistant.pipeline.artifact import Artifact
from agent_assistant.pipeline.intervention import (
    InterventionAction,
    InterventionConfig,
    InterventionHandler,
)
from agent_assistant.pipeline.pipeline import Pipeline
from agent_assistant.pipeline.session import Session
from agent_assistant.project_context.scanner import ProjectScanner
from agent_assistant.project_context.summarizer import ProjectSummarizer

app = typer.Typer(
    name="agent-assist",
    help="Multi-agent CLI programming assistant that simulates a development team.",
    no_args_is_help=True,
)
console = Console()

# Stage display configuration: emoji, color
STAGE_STYLE = {
    "pm": ("📋", "cyan"),
    "architect": ("🏗️", "blue"),
    "coder": ("💻", "green"),
    "reviewer": ("🔍", "yellow"),
    "tester": ("🧪", "magenta"),
}


def _confirm_intent(intent) -> str | None:
    """Display intent and ask user to confirm or correct. Returns corrections or None."""
    console.print(Panel(intent.format_for_display(), title="Intent Document", border_style="blue"))
    console.print()
    console.print("[bold]Options:[/bold] [y]es confirm  |  [c]orrect  |  [a]bort")
    choice = typer.prompt("Your choice", default="y")

    if choice.lower() in ("y", "yes"):
        return None
    elif choice.lower() in ("c", "correct"):
        return typer.prompt("Enter corrections")
    else:
        raise typer.Abort()


def _create_stage_callback() -> callable:
    """Create a progress callback that displays stage completions with timing."""
    stage_times: dict[str, float] = {}

    def on_stage_start(stage: str) -> None:
        emoji, color = STAGE_STYLE.get(stage, ("⚙️", "white"))
        console.print(f"  {emoji} [{color}]Running {stage}...[/{color}]", end=" ")
        stage_times[stage] = time.time()

    def on_stage_complete(artifact: Artifact) -> None:
        elapsed = time.time() - stage_times.get(artifact.stage, time.time())
        console.print(f"[green]✓[/green] [{artifact.stage}] {artifact.summary} [dim]({elapsed:.1f}s)[/dim]")

    return on_stage_start, on_stage_complete


def _create_intervention_prompt(stage: str) -> callable:
    """Create an intervention prompt function for the given stage."""
    def prompt_fn(artifact: Artifact) -> InterventionAction:
        emoji, color = STAGE_STYLE.get(stage, ("⚙️", "white"))
        console.print()
        console.print(Panel(
            artifact.summary,
            title=f"{emoji} {artifact.stage.capitalize()} — Review Checkpoint",
            border_style=color,
        ))
        if artifact.structured_data:
            console.print(f"  [dim]Structured data: {list(artifact.structured_data.keys())}[/dim]")
        console.print()
        console.print("[bold]Options:[/bold] [a]pprove  |  [m]odify  |  [q]uit")
        choice = typer.prompt("Your choice", default="a")

        if choice.lower() in ("a", "approve"):
            console.print("[green]Approved — continuing pipeline.[/green]")
            return InterventionAction.APPROVE
        elif choice.lower() in ("m", "modify"):
            console.print("[yellow]Modify — artifact will be updated.[/yellow]")
            return InterventionAction.MODIFY
        else:
            console.print("[red]Aborting pipeline.[/red]")
            return InterventionAction.ABORT

    return prompt_fn


def _scan_project_context(project_dir: Path, llm: LLMClient) -> dict:
    """Scan an existing project and produce a context summary."""
    console.print(f"[dim]Scanning project: {project_dir}...[/dim]")
    scanner = ProjectScanner(project_dir)
    scan_result = scanner.scan()
    console.print(f"[dim]Found {len(scan_result.files)} files, {len(scan_result.dependencies)} dependencies[/dim]")

    summarizer = ProjectSummarizer(llm)
    summary = summarizer.summarize(scan_result)
    console.print(f"[green]Project context ready.[/green] {summary.project_type or 'Unknown project type'}")
    return {
        "summary": summary.architecture or "",
        "project_type": summary.project_type or "",
        "tech_stack": summary.tech_stack or [],
        "key_modules": [m.get("name", "") for m in (summary.key_modules or [])],
    }


@app.command()
def build(
    request: str = typer.Argument(..., help="Natural-language description of what to build"),
    project_dir: Optional[Path] = typer.Option(
        None,
        "--project-dir",
        "-p",
        help="Path to existing project directory (iteration mode). Omit for greenfield.",
    ),
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file",
        "-e",
        help="Path to .env file",
    ),
    intervene: bool = typer.Option(
        False,
        "--intervene",
        "-i",
        help="Pause at each stage boundary for review",
    ),
    intervene_at: Optional[str] = typer.Option(
        None,
        "--intervene-at",
        help="Comma-separated stages to pause at (e.g., 'pm,coder'). Overrides --intervene.",
    ),
) -> None:
    """Build a feature using the multi-agent development pipeline.

    The pipeline runs: PM → Architect → Coder → Reviewer → Tester.
    Each agent produces a structured artifact consumed by the next stage.

    Exit codes: 0 = success, 1 = user abort, 2 = error/escalation.
    """
    config = load_config(env_file)

    if not config.api_key:
        console.print("[red]Error:[/red] DEEPSEEK_API_KEY not set. Add it to your .env file.")
        raise typer.Exit(code=2)

    console.print(f"[bold blue]Agent Coding Assistant v0.1.0[/bold blue]")
    console.print(f"Request: [italic]{request}[/italic]")

    if project_dir:
        if not project_dir.exists():
            console.print(f"[red]Error:[/red] Project directory not found: {project_dir}")
            raise typer.Exit(code=2)
        console.print(f"Mode: [green]Iteration[/green] (project: {project_dir})")
    else:
        console.print("Mode: [green]Greenfield[/green] (new project)")

    if intervene_at:
        console.print(f"Intervention: [yellow]{intervene_at}[/yellow]")
    elif intervene:
        console.print("Intervention: [yellow]all stages[/yellow]")

    console.print()

    # --- Intent Specification ---
    orchestrator_llm = LLMClient(config, model=config.models.orchestrator)

    console.print("[dim]Parsing intent...[/dim]")
    try:
        intent = parse_intent(orchestrator_llm, request)
    except Exception as e:
        console.print(f"[red]Error parsing intent:[/red] {e}")
        raise typer.Exit(code=2)

    while True:
        corrections = _confirm_intent(intent)
        if corrections is None:
            console.print("[green]Intent confirmed.[/green]")
            break
        try:
            intent = correct_intent(orchestrator_llm, intent, corrections)
            console.print("[dim]Intent updated with corrections.[/dim]")
        except Exception as e:
            console.print(f"[red]Error applying corrections:[/red] {e}")

    console.print()

    # --- Project Context (iteration mode) ---
    project_context = None
    if project_dir:
        project_context = _scan_project_context(project_dir, orchestrator_llm)
        console.print()

    # --- Build agents with per-agent LLM clients ---
    agents = [
        PMAgent(),
        ArchitectAgent(),
        CoderAgent(),
        ReviewerAgent(),
        TesterAgent(),
    ]

    # Create per-agent LLM clients (used by the pipeline internally)
    # The pipeline currently uses a single LLM client; per-agent selection
    # is configured at the agent level via their execute methods.
    pipeline_llm = LLMClient(config, model=config.models.pm)

    # --- Intervention setup ---
    if intervene_at:
        stages = [s.strip() for s in intervene_at.split(",")]
        intervention_config = InterventionConfig(stages=stages)
    elif intervene:
        intervention_config = InterventionConfig(stages="all")
    else:
        intervention_config = InterventionConfig(stages="none")

    handler = InterventionHandler(
        config=intervention_config,
        prompt_fn=_create_intervention_prompt("current"),
    )

    # --- Progress display ---
    on_stage_start, on_stage_complete_display = _create_stage_callback()

    def combined_callback(artifact: Artifact) -> str | None:
        on_stage_complete_display(artifact)
        return handler.on_stage_complete(artifact)

    # --- Pipeline Execution ---
    session = Session()
    pipeline = Pipeline(
        agents=agents,
        config=config,
        llm_client=pipeline_llm,
        session=session,
        on_stage_complete=combined_callback,
        feedback_loops=[
            ("coder", "reviewer"),
            ("coder", "tester"),
        ],
    )

    console.print("[bold]Running pipeline...[/bold]")
    stages_display = " → ".join(f"{STAGE_STYLE.get(a.role.value, ('⚙️', 'white'))[0]} {a.name}" for a in agents)
    console.print(f"[dim]{stages_display}[/dim]")
    console.print()

    start_time = time.time()

    # Announce each stage before it runs
    for i, agent in enumerate(agents):
        on_stage_start(agent.role.value)

    try:
        session = pipeline.run(intent, project_context=project_context)
    except typer.Abort:
        console.print("\n[red]Pipeline aborted by user.[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"\n[red]Pipeline error:[/red] {e}")
        raise typer.Exit(code=2)

    elapsed = time.time() - start_time

    console.print()

    # --- Final status ---
    if session.status == "completed":
        console.print(f"[bold green]Pipeline completed.[/bold green] Stages: {', '.join(session.completed_stages)}")
        console.print(f"[dim]Total time: {elapsed:.1f}s[/dim]")
    elif session.status == "escalated":
        console.print(f"[bold yellow]Pipeline escalated.[/bold yellow] Max retries exhausted.")
        console.print(f"[dim]Stages completed: {', '.join(session.completed_stages)}[/dim]")
        console.print("[yellow]Review the artifacts and decide whether to continue manually.[/yellow]")
        raise typer.Exit(code=2)
    elif session.status == "fundamental_issue":
        console.print(f"[bold red]Fundamental issue detected.[/bold red]")
        console.print("[red]The reviewer identified an architecture-level problem.[/red]")
        console.print("[yellow]Consider revising the requirements or architecture before continuing.[/yellow]")
        raise typer.Exit(code=2)
    else:
        console.print(f"[bold]Pipeline finished with status:[/bold] {session.status}")


@app.command()
def version() -> None:
    """Show the current version."""
    from agent_assistant import __version__

    console.print(f"agent-assist v{__version__}")


if __name__ == "__main__":
    app()
