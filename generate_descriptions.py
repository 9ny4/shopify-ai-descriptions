"""
shopify-ai-descriptions
=======================
CLI tool that reads a CSV of Shopify products and generates SEO-optimized
product descriptions using the OpenRouter API (openai/gpt-4o-mini).
"""

import csv
import os
import sys
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

load_dotenv()

console = Console()

REQUIRED_COLUMNS = {"name", "category", "tags", "specs"}
DRY_RUN_PLACEHOLDER = (
    "[DRY RUN] SEO-optimized description would be generated here. "
    "Remove --dry-run to call the AI API."
)


def build_client() -> OpenAI:
    """Create and return an OpenAI-compatible client pointed at OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[bold red]Error:[/] OPENROUTER_API_KEY is not set. "
                      "Copy .env.example → .env and add your key.")
        sys.exit(1)
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def build_prompt(name: str, category: str, tags: str, specs: str) -> str:
    """
    Construct the AI prompt for generating an SEO-optimized product description.

    Args:
        name: Product name.
        category: Product category.
        tags: Comma-separated product tags / keywords.
        specs: Key product specifications.

    Returns:
        A formatted prompt string ready to send to the model.
    """
    return f"""You are an expert Shopify copywriter specialising in SEO.

Write a compelling, SEO-optimised product description for the following item.
Requirements:
- 3–4 sentences, ~80–100 words
- Naturally weave in the tags as keywords
- Start with a benefit-led hook
- End with a subtle call-to-action
- Plain text only (no markdown, no bullet points)

Product details:
  Name:     {name}
  Category: {category}
  Tags:     {tags}
  Specs:    {specs}

Description:"""


def generate_description(
    client: OpenAI,
    name: str,
    category: str,
    tags: str,
    specs: str,
    model: str,
) -> str:
    """
    Call the OpenRouter API and return a product description.

    Args:
        client: Configured OpenAI client.
        name: Product name.
        category: Product category.
        tags: Comma-separated tags / keywords.
        specs: Product specifications.
        model: Model identifier to use (e.g. 'openai/gpt-4o-mini').

    Returns:
        Generated description as a string.

    Raises:
        SystemExit: If the API call fails.
    """
    prompt = build_prompt(name, category, tags, specs)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:  # noqa: BLE001
        console.print(f"[bold red]API error for '{name}':[/] {exc}")
        return "[ERROR] Description generation failed."


def validate_csv(reader: csv.DictReader) -> None:
    """
    Validate that the CSV contains all required columns.

    Args:
        reader: An initialised DictReader (fieldnames already populated).

    Raises:
        SystemExit: If any required column is missing.
    """
    if reader.fieldnames is None:
        console.print("[bold red]Error:[/] CSV file appears to be empty.")
        sys.exit(1)
    missing = REQUIRED_COLUMNS - {f.strip().lower() for f in reader.fieldnames}
    if missing:
        console.print(
            f"[bold red]Error:[/] CSV is missing required columns: {', '.join(sorted(missing))}\n"
            f"Expected: {', '.join(sorted(REQUIRED_COLUMNS))}"
        )
        sys.exit(1)


def print_preview_table(rows: list[dict]) -> None:
    """
    Print a Rich table previewing the first few generated descriptions.

    Args:
        rows: List of enriched product dicts (must include 'name' and 'description').
    """
    table = Table(title="Sample Output", show_lines=True, highlight=True)
    table.add_column("Product", style="bold cyan", min_width=20)
    table.add_column("Description", min_width=60)
    for row in rows[:5]:
        table.add_row(row["name"], row.get("description", ""))
    console.print(table)


@click.command()
@click.argument("input_csv", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_csv", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--model",
    default="openai/gpt-4o-mini",
    show_default=True,
    help="OpenRouter model identifier.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Skip API calls and insert placeholder descriptions.",
)
@click.option(
    "--preview",
    is_flag=True,
    default=False,
    help="Print a table of the first 5 results after processing.",
)
def main(
    input_csv: Path,
    output_csv: Path,
    model: str,
    dry_run: bool,
    preview: bool,
) -> None:
    """
    Generate SEO-optimised product descriptions for a Shopify CSV.

    \b
    INPUT_CSV   Path to the input CSV (columns: name, category, tags, specs)
    OUTPUT_CSV  Path to write the enriched CSV (adds a 'description' column)
    """
    console.print(
        f"[bold green]shopify-ai-descriptions[/]  "
        f"{'[yellow]DRY RUN[/]' if dry_run else f'model=[cyan]{model}[/]'}"
    )

    client: Optional[OpenAI] = None
    if not dry_run:
        client = build_client()

    rows: list[dict] = []

    with open(input_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        validate_csv(reader)
        all_rows = list(reader)

    if not all_rows:
        console.print("[yellow]Warning:[/] Input CSV has no data rows.")
        sys.exit(0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Generating descriptions…", total=len(all_rows))

        for row in all_rows:
            # Normalise keys to lowercase, strip whitespace
            row = {k.strip().lower(): v.strip() for k, v in row.items()}

            if dry_run:
                row["description"] = DRY_RUN_PLACEHOLDER
            else:
                row["description"] = generate_description(
                    client=client,  # type: ignore[arg-type]
                    name=row["name"],
                    category=row["category"],
                    tags=row["tags"],
                    specs=row["specs"],
                    model=model,
                )

            rows.append(row)
            progress.advance(task)

    # Write output CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(output_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    console.print(
        f"[bold green]✓[/] Wrote [cyan]{len(rows)}[/] rows → [cyan]{output_csv}[/]"
    )

    if preview:
        print_preview_table(rows)


if __name__ == "__main__":
    main()
