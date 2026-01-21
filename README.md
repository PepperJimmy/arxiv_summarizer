# arXiv Search Tool

A simple command-line tool to search the arXiv API and save results as human-readable JSON files.

## Setup

1. **Create a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment**:
   ```bash
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install requests feedparser
   ```

## Quick Start

Run a search:
```bash
./venv/bin/python arxiv_search.py --search-query 'all:machine learning'
```

Results are automatically saved to a timestamped JSON file (e.g., `arxiv_search_2026-01-21_15-04-51.json`).

## Example: AI/LLM Distillation Research

Search for recent papers about AI model distillation, synthetic data, and reverse engineering:

```bash
./venv/bin/python arxiv_search.py \
  --search-query '(all:AI OR all:LLM OR all:"large language") AND (all:"reverse engineering" OR all:"reverse engineered" OR all:distillation OR all:distill OR all:distilled OR all:"Synthetic Data" OR all:cloning OR all:cloned)' \
  --sort-by submittedDate \
  --sort-order descending \
  --max-results 50
```

## Search Query Syntax

The arXiv API uses a specific query syntax:

| Prefix | Searches |
|--------|----------|
| `all:` | All fields (title, abstract, authors, etc.) |
| `ti:` | Title only |
| `au:` | Author name |
| `abs:` | Abstract only |
| `cat:` | Category (e.g., `cs.LG`, `cs.AI`, `physics.optics`) |

### Boolean Operators

- `AND` — both terms must match
- `OR` — either term matches
- `ANDNOT` — exclude terms
- Use parentheses `()` to group terms

### Examples

| Query | Description |
|-------|-------------|
| `all:transformer` | Papers mentioning "transformer" anywhere |
| `ti:attention` | Papers with "attention" in the title |
| `au:hinton` | Papers by author Hinton |
| `cat:cs.LG` | Machine Learning category papers |
| `all:"neural network"` | Exact phrase match |
| `all:GPT AND all:reasoning` | Papers about GPT and reasoning |
| `cat:cs.AI OR cat:cs.LG` | AI or ML category papers |

## Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--search-query` | (required) | arXiv search query string |
| `--id-list` | — | Fetch specific arXiv IDs (comma-separated) |
| `--max-results` | 50 | Total number of results to retrieve |
| `--sort-by` | — | Sort by: `relevance`, `lastUpdatedDate`, or `submittedDate` |
| `--sort-order` | — | Sort order: `ascending` or `descending` |
| `--output` | — | Custom output file path |
| `--output-dir` | `.` | Directory for auto-generated output files |
| `--stdout` | — | Print raw JSONL to terminal instead of saving |
| `--start` | 0 | Starting index for pagination |
| `--chunk-size` | 200 | Results per API request |
| `--delay-seconds` | 3.0 | Delay between paginated requests |

## Output Format

Results are saved as JSON with this structure:

```json
{
  "search_metadata": {
    "timestamp": "2026-01-21T15:04:51.281766",
    "search_query": "your search query",
    "total_results": 20
  },
  "results": [
    {
      "title": "Paper Title",
      "published": "2026-01-20T14:53:32Z",
      "url": "http://arxiv.org/abs/2601.14032v1",
      "abstract": [
        "First line of the abstract wrapped at 80 characters...",
        "Second line continues here...",
        "And so on for readability."
      ]
    }
  ]
}
```

## Tips

- **Be polite to the API**: The default 3-second delay between requests is recommended by arXiv
- **Date filtering**: arXiv API doesn't support date ranges in queries. Sort by `submittedDate` descending to get the newest papers first
- **Large searches**: Maximum 30,000 results total, 2,000 per request

## arXiv Categories

Common computer science categories:
- `cs.AI` — Artificial Intelligence
- `cs.LG` — Machine Learning
- `cs.CL` — Computation and Language (NLP)
- `cs.CV` — Computer Vision
- `cs.NE` — Neural and Evolutionary Computing

See the full list at: https://arxiv.org/category_taxonomy
