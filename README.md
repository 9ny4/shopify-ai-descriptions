# shopify-ai-descriptions

> AI-powered bulk product description generator for Shopify stores.

Feed it a CSV of products, get back SEO-optimised descriptions — ready to paste straight into your Shopify catalogue.

Uses [OpenRouter](https://openrouter.ai/) with `openai/gpt-4o-mini` under the hood: fast, cheap, and surprisingly good at writing copy.

---

## Features

- 📄 **CSV in → CSV out** — drop in your product list, get back an enriched file with a `description` column
- 🔍 **SEO-focused prompts** — descriptions are written to naturally include your product tags as keywords
- 🏃 **`--dry-run` mode** — test the pipeline end-to-end without spending any API credits
- 📊 **Live progress bar** — Rich-powered UI shows you exactly what's happening
- 🔌 **Pluggable model** — swap the model via `--model` flag if you want GPT-4o, Claude, etc.

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/9ny4/shopify-ai-descriptions.git
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

### Basic

```bash
python generate_descriptions.py products_sample.csv output.csv
```

### Dry run (no API calls)

```bash
python generate_descriptions.py products_sample.csv output.csv --dry-run
```

### With preview table

```bash
python generate_descriptions.py products_sample.csv output.csv --dry-run --preview
```

### Custom model

```bash
python generate_descriptions.py products.csv output.csv --model anthropic/claude-3-haiku
```

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

| Variable             | Required | Description                      |
|----------------------|----------|----------------------------------|
| `OPENROUTER_API_KEY` | Yes      | Your API key from openrouter.ai  |

---

## Project structure

```
shopify-ai-descriptions/
├── generate_descriptions.py   # Main CLI entrypoint
├── products_sample.csv        # Sample input (10 products)
├── requirements.txt
├── .env.example               # Environment variable template
├── .gitignore
└── README.md
```

---

## Cost estimate

Using `openai/gpt-4o-mini` at ~$0.15 / 1M input tokens:

- A 100-product CSV costs roughly **$0.02–0.05** to process.
- You can check current pricing at [openrouter.ai/models](https://openrouter.ai/models).

---

## License

MIT — free to use, modify, and distribute.
