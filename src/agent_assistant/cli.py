"""CLI entry point for the Agent Coding Assistant."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from agent_assistant.config import load_config

app = typer.Typer(
    name="agent-assist",
    help="Multi-agent CLI programming assistant that simulates a development team.",
    no_args_is_help=True,
)
console = Console()


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
    console.print("[dim]Pipeline: PM → Architect → Coder → Reviewer → Tester[/dim]")
    console.print("[dim]Pipeline not yet implemented — coming in Issue #2+[/dim]")


@app.command()
def version() -> None:
    """Show the current version."""
    from agent_assistant import __version__

    console.print(f"agent-assist v{__version__}")


if __name__ == "__main__":
    app()
