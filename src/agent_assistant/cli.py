"""CLI entry point for the Agent Coding Assistant."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from agent_assistant.config import load_config
from agent_assistant.llm.client import LLMClient
from agent_assistant.orchestrator.intent import correct_intent, parse_intent

app = typer.Typer(
    name="agent-assist",
    help="Multi-agent CLI programming assistant that simulates a development team.",
    no_args_is_help=True,
)
console = Console()


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
) -> None:
    """Build a feature using the multi-agent development pipeline.

    The pipeline runs: PM → Architect → Coder → Reviewer → Tester.
    Each agent produces a structured artifact consumed by the next stage.
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

    if intervene:
        console.print("Intervention: [yellow]enabled[/yellow] (will pause at each stage)")

    console.print()

    # --- Intent Specification ---
    llm = LLMClient(config, model=config.models.orchestrator)

    console.print("[dim]Parsing intent...[/dim]")
    try:
        intent = parse_intent(llm, request)
    except Exception as e:
        console.print(f"[red]Error parsing intent:[/red] {e}")
        raise typer.Exit(code=2)

    # Allow user to confirm or correct
    while True:
        corrections = _confirm_intent(intent)
        if corrections is None:
            console.print("[green]Intent confirmed.[/green]")
            break
        try:
            intent = correct_intent(llm, intent, corrections)
            console.print("[dim]Intent updated with corrections.[/dim]")
        except Exception as e:
            console.print(f"[red]Error applying corrections:[/red] {e}")

    console.print()
    console.print("[dim]Pipeline: PM → Architect → Coder → Reviewer → Tester[/dim]")
    console.print("[dim]Pipeline execution not yet implemented — coming in Issue #3[/dim]")


@app.command()
def version() -> None:
    """Show the current version."""
    from agent_assistant import __version__

    console.print(f"agent-assist v{__version__}")


if __name__ == "__main__":
    app()
