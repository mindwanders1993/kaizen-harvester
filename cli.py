import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from core.agents.curator import CuratorAgent
from core.agents.extractor import ExtractorAgent
from core.agents.scout import ScoutAgent
from core.ingress.github import GithubFetcher
from core.ingress.web import WebFetcher
from core.memory.duckdb_store import DuckDBStore
from core.memory.lancedb_store import LanceDBStore
from core.schemas import HarvestRecipe, HarvestRunStats, RawArtifact

console = Console()


def load_recipe(recipe_path: str) -> HarvestRecipe:
    """Loads and validates a HarvestRecipe from a YAML file."""
    if not os.path.exists(recipe_path):
        console.print(f"[bold red]Error: Recipe file '{recipe_path}' not found.[/bold red]")
        sys.exit(1)
    with open(recipe_path, "r", encoding="utf-8") as f:
        try:
            raw_dict = yaml.safe_load(f)
            return HarvestRecipe.model_validate(raw_dict)
        except yaml.YAMLError as exc:
            console.print(f"[bold red]Error parsing YAML:[/bold red] {exc}")
            sys.exit(1)
        except Exception as exc:
            console.print(f"[bold red]Error validating recipe schema:[/bold red] {exc}")
            sys.exit(1)


def display_harvest_plan(recipe: HarvestRecipe):
    """Renders the sovereign harvest plan in Rich formatted tables."""
    console.print(
        Panel(
            f"[bold blue]Initializing Sovereign Knowledge Harvester[/bold blue]\n"
            f"Target: [green]{recipe.name}[/green] (Domain: [cyan]{recipe.domain}[/cyan])",
            expand=False,
        )
    )

    # Sources Table
    sources_table = Table(title="Harvest Sources", show_header=True, header_style="bold magenta")
    sources_table.add_column("Source Type", style="dim", width=20)
    sources_table.add_column("Target/Query", justify="left")

    for src_type, queries in recipe.sources.items():
        for query in queries:
            sources_table.add_row(src_type.replace("_", " ").title(), query)

    console.print(sources_table)

    # Schema Table
    schema_table = Table(title="Target Schema (Extraction Goal)", show_header=True, header_style="bold cyan")
    schema_table.add_column("Field", style="cyan", width=20)
    schema_table.add_column("Type/Enum", justify="left")

    for field, field_type in recipe.target_schema.items():
        schema_table.add_row(field, field_type)

    console.print(schema_table)


def display_run_summary(stats: HarvestRunStats):
    """Renders the execution summary table for a completed harvest run."""
    duration_str = "N/A"
    if stats.completed_at and stats.started_at:
        duration_str = f"{(stats.completed_at - stats.started_at).total_seconds():.2f}s"

    table = Table(title="🏁 Harvest Run Summary", show_header=True, header_style="bold green")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold yellow")

    table.add_row("Run ID", stats.run_id)
    table.add_row("Recipe", stats.recipe_name)
    table.add_row("Status", f"[bold green]{stats.status.upper()}[/bold green]")
    table.add_row("Duration", duration_str)
    table.add_row("Files Scanned", str(stats.total_scanned))
    table.add_row("Records Extracted", str(stats.total_extracted))
    table.add_row("Duplicates Merged", str(stats.total_deduped))
    table.add_row("Unique Vault Records Saved", f"[bold green]{stats.total_saved}[/bold green]")

    console.print(table)


def display_stats(db_path: str = "storage/vault.duckdb", vector_path: str = "storage/lancedb"):
    """Fetches and displays aggregate statistics from DuckDB and LanceDB."""
    duckdb_store = DuckDBStore(db_path=db_path)
    lancedb_store = LanceDBStore(db_path=vector_path)

    stats = duckdb_store.get_stats()
    vector_count = lancedb_store.count()
    duckdb_store.close()

    console.print(
        Panel(
            f"[bold green]Vault Overview[/bold green]\n"
            f"Relational Challenges (DuckDB): [bold yellow]{stats['total_challenges']}[/bold yellow]\n"
            f"Vector Embeddings (LanceDB): [bold yellow]{vector_count}[/bold yellow]",
            expand=False,
        )
    )

    if stats["total_challenges"] > 0:
        # Difficulty breakdown
        diff_table = Table(title="Challenges by Difficulty", show_header=True, header_style="bold magenta")
        diff_table.add_column("Difficulty", style="cyan")
        diff_table.add_column("Count", justify="right")
        for diff, count in stats.get("by_difficulty", {}).items():
            diff_table.add_row(diff, str(count))
        console.print(diff_table)

        # Dialect breakdown
        dialect_table = Table(title="Challenges by SQL Dialect", show_header=True, header_style="bold cyan")
        dialect_table.add_column("Dialect", style="cyan")
        dialect_table.add_column("Count", justify="right")
        for dialect, count in stats.get("by_dialect", {}).items():
            dialect_table.add_row(dialect, str(count))
        console.print(dialect_table)


async def run_pipeline(
    recipe: HarvestRecipe,
    limit: Optional[int] = None,
    concurrency: int = 10,
    db_path: str = "storage/vault.duckdb",
    vector_path: str = "storage/lancedb",
    scout_agent: Optional[ScoutAgent] = None,
    extractor_agent: Optional[ExtractorAgent] = None,
    curator_agent: Optional[CuratorAgent] = None,
    duckdb_store: Optional[DuckDBStore] = None,
    lancedb_store: Optional[LanceDBStore] = None,
) -> HarvestRunStats:
    """
    Executes the complete harvesting pipeline loop:
    Ingress -> Scout Triage -> Extractor -> Curator Sandbox -> LanceDB Dedup -> DuckDB Persist.
    """
    duckdb_store = duckdb_store or DuckDBStore(db_path=db_path)
    lancedb_store = lancedb_store or LanceDBStore(db_path=vector_path)

    extractor = extractor_agent or ExtractorAgent()
    scout = scout_agent or ScoutAgent()
    curator = curator_agent or CuratorAgent(extractor=extractor)

    github_fetcher = GithubFetcher()
    web_fetcher = WebFetcher()

    stats = HarvestRunStats(recipe_name=recipe.name, started_at=datetime.now(timezone.utc))

    # 1. Collect artifacts from all recipe sources
    console.print("\n[bold yellow]Step 1: Discovering and buffering ingress artifacts...[/bold yellow]")
    collected_artifacts: List[RawArtifact] = []

    # GitHub Queries
    gh_queries = recipe.sources.get("github_queries", [])
    if gh_queries:
        async for artifact in github_fetcher.fetch(gh_queries, filters=recipe.filters):
            collected_artifacts.append(artifact)
            if limit and len(collected_artifacts) >= limit:
                break

    # Direct Repos
    direct_repos = recipe.sources.get("direct_repos", [])
    if direct_repos and (not limit or len(collected_artifacts) < limit):
        async for artifact in github_fetcher.fetch(direct_repos, filters=recipe.filters):
            collected_artifacts.append(artifact)
            if limit and len(collected_artifacts) >= limit:
                break

    # Web URLs
    web_urls = recipe.sources.get("web_urls", [])
    if web_urls and (not limit or len(collected_artifacts) < limit):
        async for artifact in web_fetcher.fetch(web_urls, filters=recipe.filters):
            collected_artifacts.append(artifact)
            if limit and len(collected_artifacts) >= limit:
                break

    total_candidates = len(collected_artifacts)
    console.print(f"[green]✓ Ingress complete. Found [bold]{total_candidates}[/bold] candidate artifacts.[/green]\n")

    if total_candidates == 0:
        stats.completed_at = datetime.now(timezone.utc)
        stats.status = "completed"
        duckdb_store.record_harvest_run(stats)
        return stats

    # 2. Agent Swarm Execution Loop with Bounded Concurrency and Rich Progress Bar
    console.print("[bold yellow]Step 2: Activating Agent Swarm & Memory Vault...[/bold yellow]")
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed}/{task.total})"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        harvest_task = progress.add_task("[cyan]Processing artifacts...", total=total_candidates)

        async def process_artifact(artifact: RawArtifact):
            async with sem:
                # A. Scout Triage
                scout_res = scout.triage(artifact, domain=recipe.domain)
                async with lock:
                    stats.total_scanned += 1

                if not scout_res.is_candidate:
                    progress.advance(harvest_task)
                    return

                # B. Extractor
                try:
                    extracted = extractor.extract(artifact, target_schema=recipe.target_schema, domain=recipe.domain)
                except Exception:
                    progress.advance(harvest_task)
                    return

                if not extracted or not extracted.data:
                    progress.advance(harvest_task)
                    return

                async with lock:
                    stats.total_extracted += 1

                # C. Curator Sandbox Verification
                curated = curator.curate(extracted, domain=recipe.domain)
                if not curated:
                    progress.advance(harvest_task)
                    return

                # D. LanceDB Semantic Deduplication
                text_to_embed = f"{curated.title}\n{curated.problem_statement}\n{curated.solution_sql or ''}"
                vector = lancedb_store.embed_text(text_to_embed)
                is_dup, match_id, _ = lancedb_store.is_duplicate(vector)

                source_url = curated.source_urls[0] if curated.source_urls else artifact.source_url

                async with lock:
                    if is_dup and match_id:
                        stats.total_deduped += 1
                        duckdb_store.merge_source(match_id, source_url)
                    else:
                        curated.vector_embedding = vector
                        lancedb_store.add_record(curated.record_id, vector, source_url, text=text_to_embed)
                        duckdb_store.insert_challenge(curated)
                        stats.total_saved += 1

                progress.advance(harvest_task)

        # Launch bounded concurrent tasks
        await asyncio.gather(*(process_artifact(art) for art in collected_artifacts))

    # 3. Finalize Telemetry
    stats.completed_at = datetime.now(timezone.utc)
    stats.status = "completed"
    duckdb_store.record_harvest_run(stats)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Kaizen Harvester CLI — Sovereign Agentic Knowledge Factory")
    parser.add_argument(
        "action",
        choices=["run", "stats", "export"],
        help="Action to perform: run (harvest), stats (view catalog), export (dump to file)",
    )
    parser.add_argument("--recipe", type=str, help="Path to the YAML recipe specification file")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of artifacts to harvest")
    parser.add_argument("--concurrency", type=int, default=10, help="Maximum concurrent agent pipeline tasks")
    parser.add_argument("--db-path", type=str, default="storage/vault.duckdb", help="Path to DuckDB storage file")
    parser.add_argument("--vector-path", type=str, default="storage/lancedb", help="Path to LanceDB vector directory")
    parser.add_argument("--export-jsonl", type=str, help="Export vault challenges to JSONL file path")
    parser.add_argument("--export-parquet", type=str, help="Export vault challenges to Apache Parquet file path")

    args = parser.parse_args()

    if args.action == "run":
        if not args.recipe:
            console.print("[bold red]Error: --recipe is required for the 'run' action.[/bold red]")
            sys.exit(1)

        recipe = load_recipe(args.recipe)
        display_harvest_plan(recipe)

        stats = asyncio.run(
            run_pipeline(
                recipe=recipe,
                limit=args.limit,
                concurrency=args.concurrency,
                db_path=args.db_path,
                vector_path=args.vector_path,
            )
        )

        display_run_summary(stats)

    elif args.action == "stats":
        display_stats(db_path=args.db_path, vector_path=args.vector_path)

    elif args.action == "export":
        duckdb_store = DuckDBStore(db_path=args.db_path)
        if args.export_jsonl:
            duckdb_store.export_jsonl(args.export_jsonl)
            console.print(f"[bold green]✓ Exported challenges to JSONL:[/bold green] {args.export_jsonl}")
        if args.export_parquet:
            duckdb_store.export_parquet(args.export_parquet)
            console.print(f"[bold green]✓ Exported challenges to Parquet:[/bold green] {args.export_parquet}")
        duckdb_store.close()


if __name__ == "__main__":
    main()
