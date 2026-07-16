"""CLI tests for generate_descriptions.py using click's CliRunner."""

import csv
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

import generate_descriptions as gd

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_CSV = REPO_ROOT / "products_sample.csv"


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any test tries to make a real HTTP request."""

    def _blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("Unexpected HTTP request during tests")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "put", _blocked)


def read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_cli_help_exits_zero(runner: CliRunner) -> None:
    result = runner.invoke(gd.cli, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
    assert "push" in result.output


def test_generate_help_exits_zero(runner: CliRunner) -> None:
    result = runner.invoke(gd.cli, ["generate", "--help"])
    assert result.exit_code == 0
    assert "INPUT_CSV" in result.output
    assert "--dry-run" in result.output


def test_push_help_exits_zero(runner: CliRunner) -> None:
    """Regression: 'push --help' used to fail because the old group's
    positional argument swallowed the 'push' token."""
    result = runner.invoke(gd.cli, ["push", "--help"])
    assert result.exit_code == 0
    assert "--store" in result.output
    assert "--batch-size" in result.output


def test_generate_dry_run_end_to_end(runner: CliRunner, tmp_path: Path) -> None:
    output_csv = tmp_path / "output.csv"

    result = runner.invoke(
        gd.cli,
        ["generate", str(SAMPLE_CSV), str(output_csv), "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    rows = read_rows(output_csv)
    assert len(rows) == 10
    assert "description" in rows[0]
    assert all(row["description"] == gd.DRY_RUN_PLACEHOLDER for row in rows)


def test_generate_dry_run_preview_table(runner: CliRunner, tmp_path: Path) -> None:
    output_csv = tmp_path / "output.csv"

    result = runner.invoke(
        gd.cli,
        ["generate", str(SAMPLE_CSV), str(output_csv), "--dry-run", "--preview"],
    )

    assert result.exit_code == 0, result.output
    assert "Sample Output" in result.output


def test_generate_rejects_missing_columns(runner: CliRunner, tmp_path: Path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("name,category\nWidget,Tools\n", encoding="utf-8")
    output_csv = tmp_path / "output.csv"

    result = runner.invoke(
        gd.cli,
        ["generate", str(bad_csv), str(output_csv), "--dry-run"],
    )

    assert result.exit_code != 0
    assert "missing required columns" in result.output
    assert not output_csv.exists()


def test_generate_failure_exits_nonzero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run where every row fails must exit non-zero with a failure summary."""
    output_csv = tmp_path / "output.csv"

    monkeypatch.setattr(gd, "build_client", lambda: object())

    def _always_fails(*args: object, **kwargs: object) -> str:
        raise gd.DescriptionGenerationError("simulated API failure")

    monkeypatch.setattr(gd, "generate_description", _always_fails)

    result = runner.invoke(gd.cli, ["generate", str(SAMPLE_CSV), str(output_csv)])

    assert result.exit_code == 1, result.output
    assert "10 of 10" in result.output
    rows = read_rows(output_csv)
    assert len(rows) == 10
    assert all(row["description"] == gd.GENERATION_FAILED_PLACEHOLDER for row in rows)


def test_generate_partial_failure_exits_nonzero(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output_csv = tmp_path / "output.csv"

    monkeypatch.setattr(gd, "build_client", lambda: object())

    def _fails_for_yoga_mat(*, name: str, **kwargs: object) -> str:
        if name == "UltraGrip Yoga Mat":
            raise gd.DescriptionGenerationError("simulated API failure")
        return f"Generated copy for {name}."

    monkeypatch.setattr(
        gd,
        "generate_description",
        lambda client, name, category, tags, specs, model: _fails_for_yoga_mat(
            name=name
        ),
    )

    result = runner.invoke(gd.cli, ["generate", str(SAMPLE_CSV), str(output_csv)])

    assert result.exit_code == 1, result.output
    assert "1 of 10" in result.output
    rows = read_rows(output_csv)
    failed = [row for row in rows if row["description"] == gd.GENERATION_FAILED_PLACEHOLDER]
    assert len(failed) == 1
    assert failed[0]["name"] == "UltraGrip Yoga Mat"


def test_push_mock_mode_end_to_end(runner: CliRunner, tmp_path: Path) -> None:
    """generate --dry-run then push with SHOPIFY_TOKEN unset (mock mode).

    The autouse no_network fixture also guards the regression where push
    performed a live GET per product even without --preview.
    """
    input_csv = tmp_path / "products_with_ids.csv"
    with open(SAMPLE_CSV, newline="", encoding="utf-8") as fh:
        sample_rows = list(csv.DictReader(fh))
    with open(input_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "name", "category", "tags", "specs"])
        writer.writeheader()
        for index, row in enumerate(sample_rows, start=1001):
            writer.writerow({"id": str(index), **row})

    enriched_csv = tmp_path / "enriched.csv"
    generate_result = runner.invoke(
        gd.cli,
        ["generate", str(input_csv), str(enriched_csv), "--dry-run"],
    )
    assert generate_result.exit_code == 0, generate_result.output

    push_result = runner.invoke(
        gd.cli,
        ["push", str(enriched_csv), "--store", "test-store.myshopify.com"],
        env={"SHOPIFY_TOKEN": None, "SHOPIFY_STORE": None},
    )

    assert push_result.exit_code == 0, push_result.output
    assert "mock" in push_result.output.lower()
    assert push_result.output.count("Would update product") == 10
    assert "Completed pushing 10 products" in push_result.output


def test_push_mock_mode_with_preview_uses_mock_get(
    runner: CliRunner, tmp_path: Path
) -> None:
    input_csv = tmp_path / "push_input.csv"
    input_csv.write_text(
        "id,description\n2001,New description for preview.\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        gd.cli,
        ["push", str(input_csv), "--store", "test-store.myshopify.com", "--preview"],
        env={"SHOPIFY_TOKEN": None, "SHOPIFY_STORE": None},
    )

    assert result.exit_code == 0, result.output
    assert "2001" in result.output
