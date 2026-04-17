"""
shopify-ai-descriptions
=======================
CLI tool that reads a CSV of Shopify products and generates SEO-optimized
product descriptions using the OpenRouter API (openai/gpt-4o-mini).
Includes an optional push command to update products via Shopify Admin API.
"""

from __future__ import annotations

import csv
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import click
import httpx
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

load_dotenv()

console = Console()

REQUIRED_COLUMNS = {"name", "category", "tags", "specs"}
DRY_RUN_PLACEHOLDER = (
    "[DRY RUN] SEO-optimized description would be generated here. "
    "Remove --dry-run to call the AI API."
)
SHOPIFY_API_VERSION = "2024-01"
DEFAULT_BATCH_SLEEP_SECONDS = 1.0


@dataclass(frozen=True)
class ShopifyCredentials:
    """Container for Shopify API credentials."""

    store: str
    token: str
    mock_mode: bool


class ShopifyClient:
    """Client for Shopify Admin REST API."""

    def __init__(self, credentials: ShopifyCredentials) -> None:
        self._credentials = credentials
        self._base_url = f"https://{credentials.store}/admin/api/{SHOPIFY_API_VERSION}"
        self._headers = {
            "X-Shopify-Access-Token": credentials.token,
            "Content-Type": "application/json",
        }

    def get_description(self, product_id: str) -> str:
        """
        Fetch the current product description (body_html).

        Args:
            product_id: Shopify product ID.

        Returns:
            The current product description as HTML/text.
        """
        if self._credentials.mock_mode:
            return "[MOCK] Existing description (no live token)."

        url = f"{self._base_url}/products/{product_id}.json"
        response = httpx.get(url, headers=self._headers, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
        return payload.get("product", {}).get("body_html", "") or ""

    def update_description(self, product_id: str, description: str) -> httpx.Response:
        """
        Update the product description (body_html).

        Args:
            product_id: Shopify product ID.
            description: New description text/HTML.

        Returns:
            The HTTP response object.
        """
        if self._credentials.mock_mode:
            return httpx.Response(status_code=200, json={"mock": True})

        url = f"{self._base_url}/products/{product_id}.json"
        payload = {"product": {"id": int(product_id), "body_html": description}}
        response = httpx.put(url, headers=self._headers, json=payload, timeout=20.0)
        response.raise_for_status()
        return response


def build_client() -> OpenAI:
    """Create and return an OpenAI-compatible client pointed at OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        console.print(
            "[bold red]Error:[/] OPENROUTER_API_KEY is not set. "
            "Copy .env.example → .env and add your key."
        )
        sys.exit(1)
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def resolve_shopify_credentials(store: Optional[str], token: Optional[str]) -> ShopifyCredentials:
    """
    Resolve Shopify credentials, falling back to mock mode if token is missing.

    Args:
        store: Shopify store domain (myshop.myshopify.com).
        token: Shopify Admin API token.

    Returns:
        A ShopifyCredentials object.

    Raises:
        SystemExit: If store is missing.
    """
    resolved_store = store or os.environ.get("SHOPIFY_STORE")
    if not resolved_store:
        console.print(
            "[bold red]Error:[/] Shopify store is not set. "
            "Provide --store or set SHOPIFY_STORE in .env."
        )
        sys.exit(1)

    resolved_token = token or os.environ.get("SHOPIFY_TOKEN", "")
    mock_mode = not bool(resolved_token)

    if mock_mode:
        console.print(
            "[yellow]Notice:[/] SHOPIFY_TOKEN not set. Running in mock mode; "
            "no changes will be sent to Shopify."
        )

    return ShopifyCredentials(store=resolved_store, token=resolved_token, mock_mode=mock_mode)


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


def validate_csv(reader: csv.DictReader, required_columns: set[str]) -> None:
    """
    Validate that the CSV contains all required columns.

    Args:
        reader: An initialised DictReader (fieldnames already populated).
        required_columns: Set of required column names (lowercase).

    Raises:
        SystemExit: If any required column is missing.
    """
    if reader.fieldnames is None:
        console.print("[bold red]Error:[/] CSV file appears to be empty.")
        sys.exit(1)
    missing = required_columns - {f.strip().lower() for f in reader.fieldnames}
    if missing:
        console.print(
            f"[bold red]Error:[/] CSV is missing required columns: {', '.join(sorted(missing))}\n"
            f"Expected: {', '.join(sorted(required_columns))}"
        )
        sys.exit(1)


def normalise_row(row: dict[str, str]) -> dict[str, str]:
    """
    Normalise CSV row keys to lowercase and strip whitespace.

    Args:
        row: CSV row mapping.

    Returns:
        Normalised row.
    """
    return {k.strip().lower(): (v or "").strip() for k, v in row.items()}


def read_csv_rows(input_csv: Path, required_columns: set[str]) -> list[dict[str, str]]:
    """
    Read rows from CSV and normalise fieldnames.

    Args:
        input_csv: Path to input CSV.
        required_columns: Required column names.

    Returns:
        List of normalised rows.
    """
    with open(input_csv, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        validate_csv(reader, required_columns)
        return [normalise_row(row) for row in reader]


def print_preview_table(rows: list[dict[str, str]]) -> None:
    """
    Print a Rich table previewing the first few generated descriptions.

    Args:
        rows: List of enriched product dicts (must include 'name' and 'description').
    """
    table = Table(title="Sample Output", show_lines=True, highlight=True)
    table.add_column("Product", style="bold cyan", min_width=20)
    table.add_column("Description", min_width=60)
    for row in rows[:5]:
        table.add_row(row.get("name", ""), row.get("description", ""))
    console.print(table)


def render_diff(product_id: str, old: str, new: str) -> None:
    """
    Render a diff between old and new descriptions.

    Args:
        product_id: Shopify product ID.
        old: Existing description.
        new: New description.
    """
    old_lines = old.splitlines() or [""]
    new_lines = new.splitlines() or [""]
    diff = "\n".join(
        list(
            __import__("difflib").unified_diff(
                old_lines,
                new_lines,
                fromfile="current",
                tofile="new",
                lineterm="",
            )
        )
    )
    syntax = Syntax(diff or "(no changes)", "diff", theme="ansi_dark", line_numbers=False)
    console.print(Panel(syntax, title=f"Product {product_id} preview", expand=False))


def infer_id_column(rows: list[dict[str, str]], id_column: str) -> str:
    """
    Resolve the product ID column name.

    Args:
        rows: CSV rows.
        id_column: Requested ID column name.

    Returns:
        Column name containing product IDs.

    Raises:
        SystemExit: If no suitable column is found.
    """
    if not rows:
        console.print("[bold red]Error:[/] CSV contains no data rows.")
        sys.exit(1)

    headers = set(rows[0].keys())
    if id_column in headers:
        return id_column
    if "product_id" in headers:
        return "product_id"

    console.print(
        "[bold red]Error:[/] Could not find product ID column. "
        "Use --id-column or include 'id' or 'product_id' in the CSV."
    )
    sys.exit(1)


def generate_descriptions(
    input_csv: Path,
    output_csv: Path,
    model: str,
    dry_run: bool,
    preview: bool,
) -> None:
    """
    Generate SEO-optimised descriptions and write to output CSV.

    Args:
        input_csv: Path to input CSV.
        output_csv: Path to output CSV.
        model: OpenRouter model identifier.
        dry_run: Whether to skip API calls.
        preview: Whether to print preview table.
    """
    console.print(
        f"[bold green]shopify-ai-descriptions[/]  "
        f"{'[yellow]DRY RUN[/]' if dry_run else f'model=[cyan]{model}[/]'}"
    )

    client: Optional[OpenAI] = None
    if not dry_run:
        client = build_client()

    rows = read_csv_rows(input_csv, REQUIRED_COLUMNS)

    if not rows:
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
        task = progress.add_task("Generating descriptions…", total=len(rows))

        for row in rows:
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


def chunked(items: list[dict[str, str]], size: int) -> Iterable[list[dict[str, str]]]:
    """
    Yield items in fixed-size chunks.

    Args:
        items: List of items.
        size: Chunk size.

    Yields:
        Lists of items per chunk.
    """
    for index in range(0, len(items), size):
        yield items[index : index + size]


def push_descriptions(
    input_csv: Path,
    store: Optional[str],
    token: Optional[str],
    id_column: str,
    description_column: str,
    preview: bool,
    batch_size: int,
    batch_sleep: float,
) -> None:
    """
    Push descriptions from CSV to Shopify products.

    Args:
        input_csv: Path to CSV with product IDs and descriptions.
        store: Shopify store domain.
        token: Shopify Admin API token.
        id_column: Column name for product IDs.
        description_column: Column name for new descriptions.
        preview: Whether to render a diff before updating.
        batch_size: Number of products per batch.
        batch_sleep: Seconds to wait between batches.
    """
    rows = read_csv_rows(input_csv, {description_column})
    resolved_id_column = infer_id_column(rows, id_column)

    credentials = resolve_shopify_credentials(store, token)
    client = ShopifyClient(credentials)

    if not rows:
        console.print("[yellow]Warning:[/] Input CSV has no data rows.")
        sys.exit(0)

    total = len(rows)
    console.print(
        f"[bold green]shopify-ai-descriptions[/] push → "
        f"{credentials.store} ({'mock' if credentials.mock_mode else 'live'})"
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Pushing descriptions…", total=total)

        for batch in chunked(rows, batch_size):
            for row in batch:
                product_id = row.get(resolved_id_column, "").strip()
                if not product_id:
                    console.print("[yellow]Skipping row with missing product ID.[/]")
                    progress.advance(task)
                    continue

                new_description = row.get(description_column, "")
                old_description = client.get_description(product_id)

                if preview:
                    render_diff(product_id, old_description, new_description)

                if credentials.mock_mode:
                    console.print(
                        f"[yellow]MOCK:[/] Would update product {product_id} "
                        f"(description length {len(new_description)} chars)."
                    )
                else:
                    response = client.update_description(product_id, new_description)
                    usage = response.headers.get("X-Shopify-Shop-Api-Call-Limit")
                    if usage:
                        console.print(f"[dim]API usage: {usage}[/]")

                progress.advance(task)

            if not credentials.mock_mode:
                time.sleep(batch_sleep)

    console.print(f"[bold green]✓[/] Completed pushing {total} products.")


@click.group(invoke_without_command=True)
@click.pass_context
@click.argument("input_csv", required=False, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_csv", required=False, type=click.Path(dir_okay=False, path_type=Path))
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
def cli(
    context: click.Context,
    input_csv: Optional[Path],
    output_csv: Optional[Path],
    model: str,
    dry_run: bool,
    preview: bool,
) -> None:
    """
    Generate SEO-optimised product descriptions for a Shopify CSV.

    
    INPUT_CSV   Path to the input CSV (columns: name, category, tags, specs)
    OUTPUT_CSV  Path to write the enriched CSV (adds a 'description' column)
    """
    if context.invoked_subcommand is not None:
        return

    if input_csv is None or output_csv is None:
        console.print("[bold red]Error:[/] INPUT_CSV and OUTPUT_CSV are required.")
        raise click.UsageError("Missing INPUT_CSV or OUTPUT_CSV")

    generate_descriptions(
        input_csv=input_csv,
        output_csv=output_csv,
        model=model,
        dry_run=dry_run,
        preview=preview,
    )


@cli.command("push")
@click.argument("input_csv", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--store",
    envvar="SHOPIFY_STORE",
    help="Shopify store domain (e.g. myshop.myshopify.com).",
)
@click.option(
    "--token",
    envvar="SHOPIFY_TOKEN",
    help="Shopify Admin API access token.",
)
@click.option(
    "--id-column",
    default="id",
    show_default=True,
    help="Column name for Shopify product IDs.",
)
@click.option(
    "--description-column",
    default="description",
    show_default=True,
    help="Column name for new product descriptions.",
)
@click.option(
    "--preview",
    is_flag=True,
    default=False,
    help="Show a diff of current vs new descriptions before pushing.",
)
@click.option(
    "--batch-size",
    default=10,
    show_default=True,
    help="Number of products to update per batch.",
)
@click.option(
    "--batch-sleep",
    default=DEFAULT_BATCH_SLEEP_SECONDS,
    show_default=True,
    help="Seconds to sleep between batches (rate limiting).",
)
def push_command(
    input_csv: Path,
    store: Optional[str],
    token: Optional[str],
    id_column: str,
    description_column: str,
    preview: bool,
    batch_size: int,
    batch_sleep: float,
) -> None:
    """
    Push generated descriptions to Shopify products by ID.

    INPUT_CSV should include a product ID column (default: id) and description.
    """
    if batch_size < 1:
        raise click.BadParameter("batch-size must be at least 1")

    push_descriptions(
        input_csv=input_csv,
        store=store,
        token=token,
        id_column=id_column,
        description_column=description_column,
        preview=preview,
        batch_size=batch_size,
        batch_sleep=batch_sleep,
    )


if __name__ == "__main__":
    cli()
