import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict

from google import genai
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s", stream=sys.stderr)
logger = logging.getLogger(__name__)

# Force UTF-8 on stdout so Hebrew characters print correctly on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BATCH_SIZE = 50


def _build_prompt(product_names: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {name}" for i, name in enumerate(product_names))
    return f"""You are a product name normalizer.

Below is a list of product names. For each name, return a canonical (standardized) English name.
Products that refer to the same real-world item — even if written in different languages,
with different spelling, casing, or formatting — MUST map to the EXACT SAME canonical name.

Product names:
{numbered}

Rules:
- Return ONLY valid JSON — a list of objects, one per product, in the SAME ORDER as the input.
- Each object must have exactly two keys:
    "original"  — the product name exactly as given above
    "canonical" — a clean, English, properly capitalized product name
- If two or more products are the same item, give them the exact same canonical name.
- No explanation, markdown, code fences, or any text outside the JSON array.

Example output format:
[
  {{"original": "Samsung S23", "canonical": "Samsung Galaxy S23"}},
  {{"original": "סמסונג גלקסי 23", "canonical": "Samsung Galaxy S23"}}
]

Your response:"""


def _parse_response(raw_text: str, product_names: list[str]) -> list[str]:
    text = raw_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            logger.warning("AI returned no JSON array; using original names.")
            return list(product_names)
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as exc:
            logger.warning("Could not parse AI JSON (%s); using original names.", exc)
            return list(product_names)

    if not isinstance(data, list) or len(data) != len(product_names):
        logger.warning("Unexpected AI response shape; using original names.")
        return list(product_names)

    canonical_names = []
    for i, item in enumerate(data):
        if isinstance(item, dict) and "canonical" in item:
            canonical_names.append(str(item["canonical"]))
        else:
            logger.warning("Malformed entry at index %d; using original name.", i)
            canonical_names.append(product_names[i])

    return canonical_names


class GeminiMapper:
    MODEL = "gemini-2.5-flash"

    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=api_key)

    def get_canonical_names(self, product_names: list[str]) -> list[str]:
        try:
            response = self._client.models.generate_content(
                model=self.MODEL,
                contents=_build_prompt(product_names),
            )
        except Exception as exc:
            logger.warning("Gemini API call failed: %s; using original names.", exc)
            return list(product_names)
        return _parse_response(response.text, product_names)


def deduplicate(products: list[dict], mapper: GeminiMapper) -> list[dict]:
    names = [str(p.get("name", "")) for p in products]

    canonical_names: list[str] = []
    for batch_start in range(0, len(names), BATCH_SIZE):
        canonical_names.extend(mapper.get_canonical_names(names[batch_start : batch_start + BATCH_SIZE]))

    groups: dict[str, list[int]] = defaultdict(list)
    for idx, canonical in enumerate(canonical_names):
        groups[canonical].append(idx)

    return [
        products[min(indices, key=lambda i: _parse_price(products[i].get("price", 0)))]
        for indices in groups.values()
    ]


def _parse_price(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        cleaned = re.sub(r"[^\d.]", "", str(value))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="products.json")
    args = parser.parse_args()

    try:
        with open(args.input, encoding="utf-8") as f:
            products = json.load(f)
    except FileNotFoundError:
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {args.input}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(products, list):
        print("Error: input JSON must be a list.", file=sys.stderr)
        sys.exit(1)

    try:
        mapper = GeminiMapper()
    except EnvironmentError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(deduplicate(products, mapper), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
