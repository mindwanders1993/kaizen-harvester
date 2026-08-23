import argparse
import os
import sys

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def load_recipe(recipe_path: str) -> dict:
    if not os.path.exists(recipe_path):
        console.print(f"[bold red]Error: Recipe file '{recipe_path}' not found.[/bold red]")
        sys.exit(1)
    with open(recipe_path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as exc:
            console.print(f"[bold red]Error parsing YAML:[/bold red] {exc}")
            sys.exit(1)


def display_harvest_plan(recipe: dict):
    title = recipe.get("name", "Unknown Vault")
    domain = recipe.get("domain", "Unknown")

    console.print(
        Panel(
            f"[bold blue]Initializing Sovereign Knowledge Harvester[/bold blue]\nTarget: [green]{title}[/green] ({domain})",
            expand=False,
        )
    )

    # Sources Table
    sources_table = Table(title="Harvest Sources", show_header=True, header_style="bold magenta")
    sources_table.add_column("Source Type", style="dim", width=20)
    sources_table.add_column("Target/Query", justify="left")

    sources = recipe.get("sources", {})
    for src_type, queries in sources.items():
        for query in queries:
            sources_table.add_row(src_type.replace("_", " ").title(), query)

    console.print(sources_table)

    # Schema Table
    schema_table = Table(title="Target Schema (Extraction Goal)", show_header=True, header_style="bold cyan")
    schema_table.add_column("Field", style="cyan", width=20)
    schema_table.add_column("Type/Enum", justify="left")

    schema = recipe.get("target_schema", {})
    for field, field_type in schema.items():
        schema_table.add_row(field, field_type)

    console.print(schema_table)


def main():
    parser = argparse.ArgumentParser(description="Kaizen Harvester CLI")
    parser.add_argument("action", choices=["run", "stats"], help="Action to perform (run, stats)")
    parser.add_argument("--recipe", type=str, help="Path to the YAML recipe file")

    args = parser.parse_args()

    if args.action == "run":
        if not args.recipe:
            console.print("[bold red]Error: --recipe is required for the 'run' action.[/bold red]")
            sys.exit(1)

        recipe = load_recipe(args.recipe)
        display_harvest_plan(recipe)

        console.print("\n[bold yellow]Step 1: Starting Ingress Mesh...[/bold yellow]")
        # TODO: Initialize GitHub/Obscura fetchers

        console.print("[bold yellow]Step 2: Spinning up Agent Swarm...[/bold yellow]")
        # TODO: Initialize Scout, Extractor, Curator

        console.print("[bold yellow]Step 3: Checking LanceDB Vault...[/bold yellow]")
        # TODO: Initialize LanceDB deduplication

        console.print("\n[bold green]✓ Dry-run complete. Engine is ready for core modules.[/bold green]")

    elif args.action == "stats":
        console.print(
            Panel("[bold green]Vault Statistics[/bold green]\nLanceDB: 0 vectors\nDuckDB: 0 records", expand=False)
        )


if __name__ == "__main__":
    main()
