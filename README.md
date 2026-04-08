# Product Deduplicator

A Python script that deduplicates a product list using Gemini AI to assign a canonical name to each product. Products that refer to the same item — even when written in different languages or with inconsistent formatting — are merged, keeping only the lowest-priced entry.

The solution is based on sending a list of products to an AI model, which returns a standardized name for each product. This allows different variations of the same product such as "Samsung S23" and "סמסונג גלקסי 23" to be grouped together, even if they are written in different languages or formats.

The advantage of this approach is that the AI handles the complex task of identifying duplicates, while the code remains simple and clean, focusing on grouping the data and keeping the lowest price for each group.

## How it works

1. Products are loaded from `products.json` (each entry needs a `name` and `price` field).
2. All product names are sent to Gemini in batches of 50. The AI returns a canonical English name for each one, so duplicates like `"Samsung S23"` and `"סמסונג גלקסי S23"` both map to `"Samsung Galaxy S23"`.
3. Products are grouped by canonical name.
4. Within each group, the entry with the **lowest price** is kept.
5. The deduplicated list is printed as clean JSON to stdout.

If the AI returns invalid JSON, a warning is logged to stderr and the original names are used as-is for that batch.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Gemini API key:

```
GEMINI_API_KEY=your_api_key_here
```

Get a free API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

## Running

```bash
# Default input (products.json)
python deduplicate.py

# Custom input file
python deduplicate.py --input my_products.json

# Pipe output to a file (warnings stay on stderr)
python deduplicate.py > deduplicated.json
```

## Project structure

```
.
├── deduplicate.py   # main script
├── products.json    # sample product list with English + Hebrew names
├── requirements.txt
└── .gitignore
```
