"""CLI entry point for llmfuzz."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

app = typer.Typer(
    name="llmfuzz",
    help="LLM-driven fuzzing agent with coverage-guided input generation",
    no_args_is_help=True,
)
console = Console()


@app.command()
def fuzz(
    target_path: str = typer.Argument(help="Path to the Python file to fuzz"),
    function: Optional[str] = typer.Option(None, "-f", "--function", help="Specific function to fuzz"),
    max_iterations: int = typer.Option(20, "-n", "--max-iterations", help="Max agent loop iterations"),
    batch_size: int = typer.Option(10, "-b", "--batch-size", help="Inputs per iteration"),
    timeout: float = typer.Option(5.0, "--timeout", help="Per-input timeout in seconds"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="Claude model to use"),
    db_path: str = typer.Option("llmfuzz.db", "--db", help="SQLite database path"),
) -> None:
    """Fuzz a Python function with LLM-guided input generation."""
    asyncio.run(_fuzz(target_path, function, max_iterations, batch_size, timeout, model, db_path))


async def _fuzz(
    target_path: str,
    function: str | None,
    max_iterations: int,
    batch_size: int,
    timeout: float,
    model: str,
    db_path: str,
) -> None:
    import anthropic

    from llmfuzz.agent.loop import run_agent_loop
    from llmfuzz.analysis.source import build_target, discover_targets
    from llmfuzz.storage.db import get_connection
    from llmfuzz.storage.repository import Repository

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)

    path = Path(target_path).resolve()
    if not path.exists():
        console.print(f"[red]Error: {target_path} not found[/red]")
        raise typer.Exit(1)

    # Discover or build target
    if function:
        targets = [build_target(str(path), function)]
    else:
        targets = discover_targets(str(path))

    if not targets:
        console.print("[red]No fuzzable functions found[/red]")
        raise typer.Exit(1)

    client = anthropic.AsyncAnthropic(api_key=api_key)
    conn = await get_connection(db_path)
    repo = Repository(conn)

    for target in targets:
        console.print(f"\n[bold]Fuzzing: {target.qualified_name}[/bold]")
        console.print(f"  Source: {target.source_file}:{target.signature.start_line}-{target.signature.end_line}")

        async def on_iteration(session, iteration):
            snap = session.coverage_snapshots[-1] if session.coverage_snapshots else None
            if snap:
                crashes = len(session.crashes)
                console.print(
                    f"  [dim]Iteration {iteration + 1}:[/dim] "
                    f"lines {snap.line_coverage_pct}% | "
                    f"branches {snap.branch_coverage_pct}% | "
                    f"inputs {session.inputs_generated} | "
                    f"crashes {crashes}"
                )

        session = await run_agent_loop(
            target=target,
            client=client,
            max_iterations=max_iterations,
            batch_size=batch_size,
            timeout_per_input=timeout,
            model=model,
            on_iteration=on_iteration,
        )

        # Save results
        await repo.save_session(session, target)
        for snap in session.coverage_snapshots:
            await repo.save_coverage_snapshot(session.session_id, snap)
        for crash in session.crashes:
            await repo.save_crash(session.session_id, crash)

        # Print summary
        _print_session_summary(session)

    await conn.close()


def _print_session_summary(session) -> None:
    console.print(f"\n[bold green]Fuzzing complete: {session.session_id[:12]}[/bold green]")

    if session.coverage_snapshots:
        final = session.coverage_snapshots[-1]
        console.print(f"  Final line coverage:   {final.line_coverage_pct}%")
        console.print(f"  Final branch coverage: {final.branch_coverage_pct}%")

    console.print(f"  Total inputs:          {session.inputs_generated}")
    console.print(f"  Iterations:            {session.iteration}")
    console.print(f"  Crashes found:         {len(session.crashes)}")

    if session.plateau_detected:
        console.print("  [yellow]Coverage plateau detected — stopped early[/yellow]")

    if session.crashes:
        console.print("\n[bold red]Crashes:[/bold red]")
        seen_types: set[str] = set()
        for crash in session.crashes:
            key = f"{crash.exception_type}: {crash.exception_message[:80]}"
            if key not in seen_types:
                seen_types.add(key)
                console.print(f"  - {crash.exception_type}: {crash.exception_message[:100]}")
                console.print(f"    Input: {crash.input.as_call_repr()}")


@app.command()
def discover(
    target_path: str = typer.Argument(help="Path to Python file or package"),
    filter_pattern: Optional[str] = typer.Option(None, "--filter", help="Filter function names"),
) -> None:
    """List all fuzzable targets in a Python file."""
    from llmfuzz.analysis.source import discover_targets

    path = Path(target_path).resolve()
    if not path.exists():
        console.print(f"[red]Error: {target_path} not found[/red]")
        raise typer.Exit(1)

    # Handle single file or directory
    files = [path] if path.is_file() else sorted(path.rglob("*.py"))

    table = Table(title="Fuzzable Targets")
    table.add_column("Function", style="bold")
    table.add_column("File")
    table.add_column("Lines")
    table.add_column("Params")

    for file in files:
        targets = discover_targets(str(file), function_filter=filter_pattern)
        for t in targets:
            params = ", ".join(
                f"{p.name}: {p.annotation}" if p.annotation else p.name
                for p in t.signature.parameters
            )
            table.add_row(
                t.qualified_name,
                str(file.relative_to(Path.cwd())),
                f"{t.signature.start_line}-{t.signature.end_line}",
                params or "(none)",
            )

    console.print(table)


@app.command()
def benchmark(
    target_path: str = typer.Argument(help="Path to the Python file to fuzz"),
    function: str = typer.Option(..., "-f", "--function", help="Function to benchmark"),
    iterations: int = typer.Option(20, "-n", "--iterations", help="Max LLM iterations"),
    batch_size: int = typer.Option(10, "-b", "--batch-size", help="Inputs per iteration"),
    timeout: float = typer.Option(5.0, "--timeout", help="Per-input timeout in seconds"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="Claude model"),
    output_dir: str = typer.Option("./benchmark_results", "-o", "--output", help="Output directory"),
) -> None:
    """Run LLM-guided vs random fuzzing comparison."""
    asyncio.run(_benchmark(target_path, function, iterations, batch_size, timeout, model, output_dir))


async def _benchmark(
    target_path: str,
    function: str,
    iterations: int,
    batch_size: int,
    timeout: float,
    model: str,
    output_dir: str,
) -> None:
    import anthropic

    from llmfuzz.analysis.benchmark import run_benchmark
    from llmfuzz.analysis.source import build_target

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
        raise typer.Exit(1)

    path = Path(target_path).resolve()
    target = build_target(str(path), function)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    console.print(f"\n[bold]Benchmarking: {target.qualified_name}[/bold]")
    console.print(f"  LLM iterations: {iterations}, batch size: {batch_size}")
    console.print(f"  Random inputs: {iterations * batch_size}")
    console.print()

    result = await run_benchmark(
        target=target,
        client=client,
        llm_iterations=iterations,
        batch_size=batch_size,
        timeout_per_input=timeout,
        model=model,
        output_dir=output_dir,
    )

    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  LLM branch coverage:    {result.llm_final_branch_pct:.1f}%")
    console.print(f"  Random branch coverage: {result.random_final_branch_pct:.1f}%")
    console.print(f"  LLM crashes:            {len(result.llm_session.crashes)}")
    console.print(f"  Random crashes:         {len(result.random_session.crashes)}")

    if result.llm_wins:
        diff = result.llm_final_branch_pct - result.random_final_branch_pct
        console.print(f"\n  [bold green]LLM-guided wins by {diff:.1f} percentage points[/bold green]")
    else:
        console.print(f"\n  [yellow]Random fuzzing matched or exceeded LLM-guided[/yellow]")

    console.print(f"\n  Chart saved to: {output_dir}/{target.target_id}_comparison.png")


@app.command()
def sessions(
    db_path: str = typer.Option("llmfuzz.db", "--db", help="SQLite database path"),
) -> None:
    """List all fuzzing sessions."""
    asyncio.run(_sessions(db_path))


async def _sessions(db_path: str) -> None:
    from llmfuzz.storage.db import get_connection
    from llmfuzz.storage.repository import Repository

    conn = await get_connection(db_path)
    repo = Repository(conn)
    rows = await repo.list_sessions()
    await conn.close()

    if not rows:
        console.print("[dim]No sessions found[/dim]")
        return

    table = Table(title="Fuzzing Sessions")
    table.add_column("Session ID")
    table.add_column("Target")
    table.add_column("Line Cov")
    table.add_column("Branch Cov")
    table.add_column("Inputs")
    table.add_column("Iters")
    table.add_column("Started")

    for row in rows:
        table.add_row(
            row["session_id"][:12],
            row["target_id"][:12],
            f"{row['final_line_coverage']:.1f}%",
            f"{row['final_branch_coverage']:.1f}%",
            str(row["total_inputs"]),
            str(row["total_iterations"]),
            row["started_at"][:19],
        )

    console.print(table)


@app.command()
def crashes(
    session_id: str = typer.Argument(help="Session ID (or prefix)"),
    db_path: str = typer.Option("llmfuzz.db", "--db", help="SQLite database path"),
) -> None:
    """Show crashes from a fuzzing session."""
    asyncio.run(_crashes(session_id, db_path))


async def _crashes(session_id: str, db_path: str) -> None:
    from llmfuzz.storage.db import get_connection
    from llmfuzz.storage.repository import Repository

    conn = await get_connection(db_path)
    repo = Repository(conn)

    # Find matching session
    all_sessions = await repo.list_sessions()
    matching = [s for s in all_sessions if s["session_id"].startswith(session_id)]
    if not matching:
        console.print(f"[red]No session found matching '{session_id}'[/red]")
        await conn.close()
        return

    full_id = matching[0]["session_id"]
    crash_rows = await repo.get_crashes(full_id)
    await conn.close()

    if not crash_rows:
        console.print("[green]No crashes found in this session[/green]")
        return

    for crash in crash_rows:
        console.print(f"\n[bold red]{crash['exception_type']}[/bold red]: {crash['exception_message']}")
        console.print(f"  Iteration: {crash['iteration']}")
        console.print(f"  [dim]Reproducer:[/dim]")
        console.print(f"  {crash['reproducer_code']}")


@app.command()
def worker(
    redis_url: str = typer.Option("redis://localhost:6379", "--redis-url", help="Redis URL"),
    worker_id: Optional[str] = typer.Option(None, "--worker-id", help="Worker ID (auto-generated if omitted)"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="Claude model"),
) -> None:
    """Start a distributed fuzzing worker."""
    asyncio.run(_worker(redis_url, worker_id, model))


async def _worker(redis_url: str, worker_id: str | None, model: str) -> None:
    from llmfuzz.distributed.worker import FuzzWorker

    w = FuzzWorker(worker_id=worker_id, redis_url=redis_url, model=model)
    try:
        await w.run()
    except KeyboardInterrupt:
        w.stop()
        console.print(f"\n[dim]Worker {w.worker_id} stopped[/dim]")


@app.command()
def coordinator(
    target_path: str = typer.Argument(help="Path to Python file with targets to fuzz"),
    redis_url: str = typer.Option("redis://localhost:6379", "--redis-url", help="Redis URL"),
    max_iterations: int = typer.Option(20, "-n", "--max-iterations", help="Max iterations per target"),
    function: Optional[str] = typer.Option(None, "-f", "--function", help="Specific function (otherwise all)"),
) -> None:
    """Start the distributed fuzzing coordinator."""
    asyncio.run(_coordinator(target_path, redis_url, max_iterations, function))


async def _coordinator(
    target_path: str, redis_url: str, max_iterations: int, function: str | None
) -> None:
    from llmfuzz.analysis.source import build_target, discover_targets
    from llmfuzz.distributed.coordinator import FuzzCoordinator

    path = Path(target_path).resolve()
    if function:
        targets = [build_target(str(path), function)]
    else:
        targets = discover_targets(str(path))

    if not targets:
        console.print("[red]No fuzzable targets found[/red]")
        raise typer.Exit(1)

    coord = FuzzCoordinator(redis_url=redis_url, max_iterations=max_iterations)
    await coord.submit_targets(targets)

    console.print(f"\n[bold]Waiting for {len(coord.active_tasks)} tasks to complete...[/bold]")
    try:
        await coord.monitor_results()
    except KeyboardInterrupt:
        console.print("\n[dim]Coordinator stopped[/dim]")

    coord.print_summary()


if __name__ == "__main__":
    app()
