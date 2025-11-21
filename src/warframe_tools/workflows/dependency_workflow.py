"""Workflow for scraping, mapping, and visualizing weapon dependencies."""

import json
from pathlib import Path
from datetime import datetime

from ..scrapers import scrape_weapon_names, scrape_weapon_data
from ..tools.dependency_mapper import map_dependencies
from ..visualisation import visualize_dependencies


def find_dependency_chains(dependency_graph):
    """
    Find all dependency chains (trees) from a dependency graph.
    
    Args:
        dependency_graph: dict mapping weapon_name -> [list of required weapon names]
    
    Returns:
        List of tree dictionaries, each with 'weapon' and 'children' keys
    """
    def build_tree(weapon, graph, visited=None):
        """Recursively build a dependency tree for a weapon"""
        if visited is None:
            visited = set()
        
        # Avoid cycles
        if weapon in visited:
            return None
        
        visited.add(weapon)
        
        tree = {
            'weapon': weapon,
            'children': []
        }
        
        # If this weapon has dependencies, add them as children
        if weapon in graph and graph[weapon]:
            for dep in graph[weapon]:
                if dep != weapon:  # Skip self-dependencies
                    child_tree = build_tree(dep, graph, visited.copy())
                    if child_tree:
                        tree['children'].append(child_tree)
        
        return tree
    
    def find_dependency_trees(graph):
        """Find all dependency trees - weapons with their required components (recursive)"""
        trees = []
        processed = set()
        
        # For each weapon that requires other weapons, build its full tree
        for weapon, deps in graph.items():
            if deps and weapon not in processed:  # Has dependencies and not processed
                tree = build_tree(weapon, graph)
                if tree:
                    trees.append(tree)
                    processed.add(weapon)
        
        return trees
    
    # Find all dependency trees
    all_trees = find_dependency_trees(dependency_graph)
    
    # Filter to get unique trees (remove duplicates and sub-trees)
    final_trees = []
    seen_trees = set()
    
    def get_tree_signature(tree):
        """Get a unique signature for a tree"""
        def get_all_weapons(node):
            """Recursively get all weapons in the tree"""
            weapons = [node['weapon']]
            for child in node.get('children', []):
                weapons.extend(get_all_weapons(child))
            return sorted(set(weapons))
        
        return tuple(get_all_weapons(tree))
    
    for tree in all_trees:
        tree_sig = get_tree_signature(tree)
        if tree_sig not in seen_trees:
            final_trees.append(tree)
            seen_trees.add(tree_sig)
    
    return final_trees


def save_dependency_chains(trees, all_dependencies, output_file):
    """
    Save dependency chains to JSON file.
    
    Args:
        trees: List of tree dictionaries
        all_dependencies: Set of tuples (weapon_name, required_weapon_name)
        output_file: Path to save the JSON file
    """
    def tree_to_dict(node):
        """Convert tree structure to dictionary for JSON"""
        result = {
            "weapon": node['weapon'],
            "children": []
        }
        for child in node.get('children', []):
            result['children'].append(tree_to_dict(child))
        return result
    
    output_data = {
        "total_trees": len(trees),
        "total_dependencies": len(all_dependencies),
        "trees": [tree_to_dict(tree) for tree in trees],
        "all_dependencies": [{"from": f, "to": t} for f, t in sorted(all_dependencies)]
    }
    
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    return output_file


def run_dependency_workflow(
    data_dir=None,
    images_dir=None,
    output_dir=None,
    force_scrape=False,
    headless=False
):
    """
    Complete workflow for weapon dependency analysis:
    1. Scrape weapon names if needed
    2. Scrape weapon data if needed
    3. Map dependencies to get graph
    4. Find dependency chains
    5. Visualize dependencies
    
    Args:
        data_dir: Directory for data files. Defaults to 'data' folder in project root.
        images_dir: Directory for cached images. Defaults to 'data/weapon_images' in project root.
        output_dir: Directory for output files. Defaults to 'images' and 'dist' folders in project root.
        force_scrape: If True, scrape even if data already exists.
        headless: Whether to run browser in headless mode when scraping.
    
    Returns:
        Dictionary with paths to generated files and summary statistics.
    """
    # Determine directories
    if data_dir is None:
        project_root = Path(__file__).parent.parent.parent.parent
        data_dir = project_root / "data"
    else:
        data_dir = Path(data_dir)
    
    if images_dir is None:
        project_root = Path(__file__).parent.parent.parent.parent
        images_dir = project_root / "data" / "weapon_images"
    else:
        images_dir = Path(images_dir)
    
    if output_dir is None:
        project_root = Path(__file__).parent.parent.parent.parent
        output_dir = project_root / "images"
    else:
        output_dir = Path(output_dir)
    
    data_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    result = {
        "weapon_links_file": None,
        "manufacturing_file": None,
        "dependency_chains_file": None,
        "visualization_file": None,
        "summary": {}
    }
    
    # Step 1: Scrape weapon names if needed
    print("=" * 60)
    print("Step 1: Checking for weapon links...")
    print("=" * 60)
    
    weapon_links_files = sorted(data_dir.glob("weapon_links_*.json"))
    if not weapon_links_files or force_scrape:
        print("Weapon links not found or force_scrape=True. Scraping weapon names...")
        weapon_links_file = scrape_weapon_names(data_dir=data_dir, headless=headless)
        result["weapon_links_file"] = str(weapon_links_file)
    else:
        weapon_links_file = weapon_links_files[-1]
        print(f"Using existing weapon links file: {weapon_links_file}")
        result["weapon_links_file"] = str(weapon_links_file)
    
    # Step 2: Scrape weapon data if needed
    print("\n" + "=" * 60)
    print("Step 2: Checking for weapon manufacturing data...")
    print("=" * 60)
    
    manufacturing_files = sorted(data_dir.glob("weapon_manufacturing_*.json"))
    if not manufacturing_files or force_scrape:
        print("Manufacturing data not found or force_scrape=True. Scraping weapon data...")
        manufacturing_file = scrape_weapon_data(
            weapon_links_file=weapon_links_file,
            data_dir=data_dir,
            headless=headless
        )
        result["manufacturing_file"] = str(manufacturing_file)
    else:
        manufacturing_file = manufacturing_files[-1]
        print(f"Using existing manufacturing file: {manufacturing_file}")
        result["manufacturing_file"] = str(manufacturing_file)
    
    # Step 3: Load weapon data and map dependencies
    print("\n" + "=" * 60)
    print("Step 3: Mapping dependencies...")
    print("=" * 60)
    
    with open(manufacturing_file, 'r', encoding='utf-8') as f:
        manufacturing_data = json.load(f)
    
    weapons = manufacturing_data['weapons']
    print(f"Loaded {len(weapons)} weapons")
    
    dependency_graph, all_dependencies = map_dependencies(weapons)
    
    print(f"Found {len(all_dependencies)} weapon-to-weapon dependencies")
    print(f"Found {len(dependency_graph)} weapons that require other weapons")
    
    # Step 4: Find dependency chains
    print("\n" + "=" * 60)
    print("Step 4: Finding dependency chains...")
    print("=" * 60)
    
    trees = find_dependency_chains(dependency_graph)
    print(f"Found {len(trees)} unique dependency trees")
    
    # Save dependency chains
    dependency_chains_file = data_dir / "weapon_dependency_chains.json"
    save_dependency_chains(trees, all_dependencies, dependency_chains_file)
    result["dependency_chains_file"] = str(dependency_chains_file)
    print(f"Saved dependency chains to {dependency_chains_file}")
    
    # Step 5: Visualize dependencies
    print("\n" + "=" * 60)
    print("Step 5: Creating visualization...")
    print("=" * 60)
    
    visualization_file = visualize_dependencies(
        dependency_chains_file=dependency_chains_file,
        data_dir=data_dir,
        images_dir=images_dir,
        output_dir=output_dir
    )
    result["visualization_file"] = str(visualization_file)
    
    # Summary statistics
    def count_tree_nodes(node):
        """Count total nodes in a tree"""
        count = 1
        for child in node.get('children', []):
            count += count_tree_nodes(child)
        return count
    
    def get_max_depth(node):
        """Get maximum depth of a tree"""
        if not node.get('children'):
            return 1
        return 1 + max([get_max_depth(child) for child in node['children']], default=0)
    
    result["summary"] = {
        "total_weapons": len(weapons),
        "total_dependencies": len(all_dependencies),
        "total_trees": len(trees),
        "weapons_with_dependencies": len(dependency_graph)
    }
    
    if trees:
        max_nodes = max([count_tree_nodes(t) for t in trees])
        max_depth = max([get_max_depth(t) for t in trees])
        result["summary"]["largest_tree_nodes"] = max_nodes
        result["summary"]["max_tree_depth"] = max_depth
    
    print("\n" + "=" * 60)
    print("Workflow Complete!")
    print("=" * 60)
    print(f"Summary:")
    print(f"  - Total weapons: {result['summary']['total_weapons']}")
    print(f"  - Total dependencies: {result['summary']['total_dependencies']}")
    print(f"  - Total dependency trees: {result['summary']['total_trees']}")
    if trees:
        print(f"  - Largest tree: {result['summary']['largest_tree_nodes']} weapons, depth: {result['summary']['max_tree_depth']} levels")
    print(f"\nGenerated files:")
    print(f"  - Dependency chains: {result['dependency_chains_file']}")
    print(f"  - Visualization: {result['visualization_file']}")
    
    return result


if __name__ == "__main__":
    run_dependency_workflow()

