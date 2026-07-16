# shopify-ai-descriptions

[![CI](https://github.com/sekkedev/shopify-ai-descriptions/actions/workflows/ci.yml/badge.svg)](https://github.com/sekkedev/shopify-ai-descriptions/actions/workflows/ci.yml)

> AI-powered bulk product description generator for Shopify stores.

Feed it a CSV of products, get back SEO-optimised descriptions — ready to paste straight into your Shopify catalogue.

Uses [OpenRouter](https://openrouter.ai/) with `openai/gpt-4o-mini` under the hood: fast, cheap, and surprisingly good at writing copy.

## Example Output

| Raw input | Generated description |
|---|---|
| `UltraGrip Yoga Mat`<br>`yoga mat, non-slip, eco-friendly, exercise, fitness` | `Elevate every practice with the UltraGrip Yoga Mat — a non-slip, eco-friendly surface built for comfort, stability, and daily training. Crafted from natural rubber with a supportive 6mm profile, it balances cushion with ground feel for home workouts, studio sessions, and on-the-go fitness routines.` |
| `Wireless Noise-Cancelling Headphones`<br>`headphones, wireless, noise-cancelling, bluetooth, audio` | `Immersive sound meets all-day comfort with Wireless Noise-Cancelling Headphones featuring Bluetooth 5.2, 40mm drivers, and up to 30 hours of battery life. Designed to cut distractions with powerful ANC, they're ideal for travel, work, and focused listening.` |

## Demo

A real dry-run against the bundled sample CSV (no API key needed):

```text
$ python generate_descriptions.py generate products_sample.csv output.csv --dry-run --preview
shopify-ai-descriptions  DRY RUN

✓ Wrote 10 rows → output.csv
                                             Sample Output
┌──────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
│ Product                              │ Description                                                  │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ UltraGrip Yoga Mat                   │ [DRY RUN] SEO-optimized description would be generated here. │
│                                      │ Remove --dry-run to call the AI API.                         │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Wireless Noise-Cancelling Headphones │ [DRY RUN] SEO-optimized description would be generated here. │
│                                      │ Remove --dry-run to call the AI API.                         │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Bamboo Cutting Board Set             │ [DRY RUN] SEO-optimized description would be generated here. │
│                                      │ Remove --dry-run to call the AI API.                         │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ Portable Espresso Maker              │ [DRY RUN] SEO-optimized description would be generated here. │
│                                      │ Remove --dry-run to call the AI API.                         │
├──────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ LED Desk Lamp with USB Charging      │ [DRY RUN] SEO-optimized description would be generated here. │
│                                      │ Remove --dry-run to call the AI API.                         │
└──────────────────────────────────────┴──────────────────────────────────────────────────────────────┘
```

And a real push in mock mode (`SHOPIFY_TOKEN` unset, so nothing is sent), using a copy of `output.csv` with an added `id` column:

```text
$ python generate_descriptions.py push output_with_ids.csv --store demo-store.myshopify.com --batch-size 5
Notice: SHOPIFY_TOKEN not set. Running in mock mode; no changes will be sent to Shopify.
shopify-ai-descriptions push → demo-store.myshopify.com (mock)
MOCK: Would update product 1001 (description length 97 chars).
MOCK: Would update product 1002 (description length 97 chars).
MOCK: Would update product 1003 (description length 97 chars).
MOCK: Would update product 1004 (description length 97 chars).
MOCK: Would update product 1005 (description length 97 chars).
MOCK: Would update product 1006 (description length 97 chars).
MOCK: Would update product 1007 (description length 97 chars).
MOCK: Would update product 1008 (description length 97 chars).
MOCK: Would update product 1009 (description length 97 chars).
MOCK: Would update product 1010 (description length 97 chars).

✓ Completed pushing 10 products.
```

The tool has been verified end-to-end in dry-run and mock modes; it has not yet been exercised against a live Shopify store.

---

## Features

- 📄 **CSV in → CSV out** — drop in your product list, get back an enriched file with a `description` column
- 🔍 **SEO-focused prompts** — descriptions are written to naturally include your product tags as keywords
- 🏃 **`--dry-run` mode** — test the pipeline end-to-end without spending any API credits
- 📊 **Live progress bar** — Rich-powered UI shows you exactly what's happening
- 🔌 **Pluggable model** — swap the model via `--model` flag if you want GPT-4o, Claude, etc.
- 🛒 **Shopify push** — update product descriptions directly via Admin REST API
- 🧾 **Preview diff** — inspect changes before pushing with `--preview`
- 📦 **Batch controls** — manage rate limits with `--batch-size` and `--batch-sleep`

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/sekkedev/shopify-ai-descriptions.git
cd shopify-ai-descriptions

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# Edit .env and add your OpenRouter key
```

---

## Usage

The CLI has two subcommands: `generate` and `push`.

### Generate descriptions

```bash
python generate_descriptions.py generate products_sample.csv output.csv
```

### Dry run (no API calls)

```bash
python generate_descriptions.py generate products_sample.csv output.csv --dry-run
```

### With preview table

```bash
python generate_descriptions.py generate products_sample.csv output.csv --dry-run --preview
```

### Custom model

```bash
python generate_descriptions.py generate products.csv output.csv --model anthropic/claude-3-haiku
```

### Push descriptions to Shopify

```bash
python generate_descriptions.py push output.csv --store your-store.myshopify.com --preview --batch-size 10
```

> If `SHOPIFY_TOKEN` isn't set, the push command runs in mock mode and makes no changes.

If any row fails to generate, the run prints a failure summary, writes an explicit
`[ERROR]` placeholder for the affected rows, and exits with a non-zero status code.

---

## Input CSV format

| Column     | Description                              | Example                              |
|------------|------------------------------------------|--------------------------------------|
| `name`     | Product name                             | `UltraGrip Yoga Mat`                 |
| `category` | Product category                         | `Fitness`                            |
| `tags`     | Comma-separated SEO keywords             | `yoga mat, non-slip, eco-friendly`   |
| `specs`    | Key specs (free-form text)               | `Material: natural rubber; 6mm thick`|

See [`products_sample.csv`](products_sample.csv) for a ready-to-use example with 10 products across 3 categories.

---

## Sample output

| Product | Description |
|---------|-------------|
| UltraGrip Yoga Mat | Elevate every practice with the UltraGrip Yoga Mat — a non-slip, eco-friendly surface engineered for yogis who demand performance and sustainability in equal measure. Crafted from natural rubber at a supportive 6mm thickness, it cushions joints without sacrificing ground feel. Lightweight at just 1.5 kg, it rolls up cleanly for home studio or gym bag alike. Add it to your fitness routine today and feel the difference from day one. |
| Wireless Noise-Cancelling Headphones | Immerse yourself in pure sound with these Wireless Noise-Cancelling Headphones, delivering up to 30 hours of Bluetooth audio with best-in-class -35 dB ANC. Bluetooth 5.2 ensures a rock-solid connection whether you're commuting or deep in a work session. At just 250 g, they're light enough to wear all day without fatigue. Upgrade your audio experience — order yours and block the world out. |

---

## Environment variables

| Variable             | Required | Description                              |
|----------------------|----------|------------------------------------------|
| `OPENROUTER_API_KEY` | Yes      | Your API key from openrouter.ai          |
| `SHOPIFY_STORE`      | Yes (push) | Shopify store domain (myshop.myshopify.com) |
| `SHOPIFY_TOKEN`      | Yes (push) | Shopify Admin API token (if unset → mock) |

---

## Project structure

```
shopify-ai-descriptions/
├── generate_descriptions.py   # Main CLI entrypoint (generate + push subcommands)
├── products_sample.csv        # Sample input (10 products)
├── tests/
│   ├── conftest.py
│   └── test_cli.py            # CLI test suite (pytest + click CliRunner)
├── .github/workflows/ci.yml   # CI: pytest on Ubuntu + Windows, Python 3.11/3.12
├── requirements.txt
├── requirements-dev.txt       # Test dependencies
├── .env.example               # Environment variable template
├── .gitignore
├── LICENSE
└── README.md
```

---

## Shopify push command

The `push` command updates `body_html` via Shopify Admin REST API (`PUT /admin/api/2024-01/products/{id}.json`).

### Required CSV columns

- `id` (or `product_id`) — Shopify product ID
- `description` — the new product description

### Example

```bash
python generate_descriptions.py push output.csv --store your-store.myshopify.com --preview --batch-size 5 --batch-sleep 1.5
```

### Preview mode

Add `--preview` to view a rich diff of the existing vs new description before each update.
The current description is only fetched from Shopify when `--preview` is set.

### Batch size control

Use `--batch-size` (default 10) to control how many products are updated per batch.
The CLI waits `--batch-sleep` seconds between batches to help respect API rate limits.

---

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite covers the `generate` and `push` subcommands end-to-end in dry-run and
mock modes, CSV validation, and the failure exit-code path. No network access or
API keys are required. CI runs the suite on Ubuntu and Windows (Python 3.11 and 3.12).

---

## Cost estimate

Using `openai/gpt-4o-mini` at ~$0.15 / 1M input tokens:

- A 100-product CSV costs roughly **$0.02–0.05** to process.
- You can check current pricing at [openrouter.ai/models](https://openrouter.ai/models).

---

## License

MIT — see [LICENSE](LICENSE).
