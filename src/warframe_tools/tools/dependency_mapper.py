"""Dependency mapper for Warframe weapons."""

from collections import defaultdict


def map_dependencies(weapons_data):
    """
    Map weapon dependencies from manufacturing data.
    
    Args:
        weapons_data: List of weapon dictionaries, each containing:
            - weapon_name: str
            - weapon_url: str
            - resources: list of dicts with 'name', 'quantity', and optionally 'url'
    
    Returns:
        Tuple of (dependency_graph dict, all_dependencies set)
        - dependency_graph: dict mapping weapon_name -> [list of required weapon names]
        - all_dependencies: set of tuples (weapon_name, required_weapon_name)
    """
    # Build a mapping of weapon URLs to weapon names
    weapon_url_to_name = {}
    
    for weapon in weapons_data:
        weapon_name = weapon['weapon_name']
        weapon_url = weapon['weapon_url']
        weapon_url_to_name[weapon_url] = weapon_name
    
    # Build dependency graph
    # Graph structure: weapon_name -> [list of required weapon names]
    dependency_graph = defaultdict(list)
    all_dependencies = set()
    
    for weapon in weapons_data:
        weapon_name = weapon['weapon_name']
        resources = weapon.get('resources', [])
        
        for resource in resources:
            resource_url = resource.get('url', '')
            # Check if this resource is actually a weapon
            if resource_url in weapon_url_to_name:
                required_weapon = weapon_url_to_name[resource_url]
                # Skip self-dependencies (weapon depending on itself)
                if required_weapon != weapon_name:
                    dependency_graph[weapon_name].append(required_weapon)
                    all_dependencies.add((weapon_name, required_weapon))
    
    return dependency_graph, all_dependencies
