# Warframe Tools

A collection of Python tools for Warframe data analysis, scraping, and visualization.

> **Why it exists.** Crafting trees in modern games are dense graphs in disguise — what depends on what, what unlocks what. warframe_tools scrapes the wiki, builds the dependency graph in Python, and renders it. Same shape as N-D-3 (people-document graphs) and [Narode](https://www.narode.net) (information-spread graphs) — the substrate is different (game data), but the graph-rendering and dependency-tracing problem is shared. The productized successor to the looser [warframe_fodderpath](https://github.com/range-et/warframe_fodderpath) scripts.

## Installation

Install in editable mode:

```bash
pip install -e .
```

Or with development dependencies:

```bash
pip install -e ".[dev]"
```

## Structure

- `src/warframe_tools/scrapers/` - Data scraping modules
- `src/warframe_tools/tools/` - Data processing and analysis tools
- `src/warframe_tools/visualisation/` - Visualization modules
- `src/warframe_tools/workflows/` - Complete workflow orchestrators
- `data/` - Data files (JSON)
- `images/` - Image outputs and cached images
- `dist/` - Distribution outputs

## Usage

### Quick Start

After installing, you can run the dependency workflow:

```bash
# Using pipenv
pipenv install
pipenv run python -m warframe_tools dependency

# Or using the CLI (after pip install -e .)
warframe-tools dependency
```

This will:
1. Check for existing data (skips scraping if data exists)
2. Scrape weapon names if needed
3. Scrape weapon data if needed
4. Map dependencies to get the graph
5. Find dependency chains
6. Generate visualization → saves to `images/weapon_dependency_chains.png`

### Recommended: Use Workflows (Python API)

```python
from warframe_tools.workflows import run_dependency_workflow

# Run the complete dependency analysis workflow
result = run_dependency_workflow()

# The image will be saved to images/weapon_dependency_chains.png
print(f"Visualization saved to: {result['visualization_file']}")

# Force re-scraping even if data exists
result = run_dependency_workflow(force_scrape=True)

# Run in headless mode
result = run_dependency_workflow(headless=True)
```

### Individual Modules

You can also use individual modules if you need more control:

#### Scraping

```python
from warframe_tools.scrapers import scrape_weapon_names, scrape_weapon_data

# Scrape weapon names
scrape_weapon_names()

# Scrape weapon manufacturing data
scrape_weapon_data()
```

#### Dependency Mapping

```python
from warframe_tools.tools import map_dependencies
import json

# Load weapon data
with open('data/weapon_manufacturing_2025-11-20.json') as f:
    data = json.load(f)

# Map dependencies (returns graph, not files)
dependency_graph, all_dependencies = map_dependencies(data['weapons'])
```

#### Visualization

```python
from warframe_tools.visualisation import visualize_dependencies

# Create dependency visualization
visualize_dependencies()
```
