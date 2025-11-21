"""Visualization module for weapon dependency trees."""

import json
from pathlib import Path
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from urllib.parse import unquote, urlparse
import requests
from PIL import Image
from io import BytesIO
import os


def visualize_dependencies(
    dependency_chains_file=None,
    data_dir=None,
    images_dir=None,
    output_dir=None,
    size='64px'
):
    """
    Create visualization of weapon dependency trees.
    
    Args:
        dependency_chains_file: Path to dependency chains JSON file.
                               If None, looks for weapon_dependency_chains.json in data_dir.
        data_dir: Directory to read data from. Defaults to 'data' folder in project root.
        images_dir: Directory to cache weapon images. Defaults to 'data/weapon_images' in project root.
        output_dir: Directory to save output images. Defaults to 'images' and 'dist' folders in project root.
        size: Size of weapon images to download.
    
    Returns:
        Path to the saved PNG file.
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
    
    images_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Find dependency chains file if not provided
    if dependency_chains_file is None:
        dependency_chains_file = data_dir / "weapon_dependency_chains.json"
    else:
        dependency_chains_file = Path(dependency_chains_file)
    
    if not dependency_chains_file.exists():
        raise FileNotFoundError(f"Dependency chains file not found: {dependency_chains_file}")
    
    # Load dependency chains
    print(f"Loading dependency chains from {dependency_chains_file}...")
    with open(dependency_chains_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    final_trees = data['trees']
    all_dependencies = data['all_dependencies']
    
    print(f"Loaded {len(final_trees)} dependency trees")
    
    # Load manufacturing data to get weapon URLs for image fetching
    manufacturing_files = sorted(data_dir.glob("weapon_manufacturing_*.json"))
    weapon_url_to_name = {}
    weapon_name_to_url = {}
    
    if manufacturing_files:
        with open(manufacturing_files[-1], 'r', encoding='utf-8') as f:
            manufacturing_data = json.load(f)
        
        for weapon in manufacturing_data['weapons']:
            weapon_name = weapon['weapon_name']
            weapon_url = weapon['weapon_url']
            weapon_url_to_name[weapon_url] = weapon_name
            weapon_name_to_url[weapon_name] = weapon_url
    
    # Function to get weapon image URL - try multiple patterns
    def get_weapon_image_url(weapon_name, weapon_url=None, size='64px'):
        """Construct weapon image URL from weapon name - try multiple patterns"""
        # If we have the weapon URL, extract the page name from it
        if weapon_url:
            try:
                parsed = urlparse(weapon_url)
                path_parts = parsed.path.split('/')
                if len(path_parts) >= 2 and path_parts[-1]:
                    wiki_page_name = path_parts[-1]
                    # Use the exact page name from URL
                    patterns = [
                        f"https://wiki.warframe.com/images/thumb/{wiki_page_name}.png/{size}-{wiki_page_name}.png",
                        f"https://wiki.warframe.com/images/thumb/{unquote(wiki_page_name)}.png/{size}-{unquote(wiki_page_name)}.png",
                    ]
                    return patterns
            except:
                pass
        
        # Fallback: construct from weapon name
        clean_name1 = weapon_name.replace(' ', '_')
        clean_name2 = clean_name1
        try:
            clean_name2 = unquote(clean_name1)
            clean_name2 = clean_name2.replace(' ', '_')
        except:
            pass
        
        clean_name3 = clean_name2.replace('&', '%26').replace('%', '%25')
        
        patterns = [
            f"https://wiki.warframe.com/images/thumb/{clean_name1}.png/{size}-{clean_name1}.png",
            f"https://wiki.warframe.com/images/thumb/{clean_name2}.png/{size}-{clean_name2}.png",
            f"https://wiki.warframe.com/images/thumb/{clean_name3}.png/{size}-{clean_name3}.png",
            f"https://wiki.warframe.com/images/thumb/{clean_name1.lower()}.png/{size}-{clean_name1.lower()}.png",
        ]
        
        return patterns
    
    # Cache for downloaded images
    image_cache = {}
    
    def get_weapon_image(weapon_name, size='64px', weapon_url=None):
        """Download and cache weapon image"""
        if weapon_name in image_cache:
            return image_cache[weapon_name]
        
        # Check local cache first
        cache_file = images_dir / f"{weapon_name.replace(' ', '_')}_{size}.png"
        if cache_file.exists():
            try:
                img = Image.open(cache_file)
                image_cache[weapon_name] = img
                return img
            except:
                pass
        
        # Download image - try multiple URL patterns
        image_urls = get_weapon_image_url(weapon_name, weapon_url, size)
        for image_url in image_urls:
            try:
                response = requests.get(image_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200 and len(response.content) > 100:
                    img = Image.open(BytesIO(response.content))
                    img.verify()
                    img = Image.open(BytesIO(response.content))
                    img.save(cache_file)
                    image_cache[weapon_name] = img
                    return img
            except Exception as e:
                continue
        
        return None
    
    # Create visualization
    print("\nCreating visualization...")
    
    num_trees = len(final_trees)
    if num_trees == 0:
        print("No dependency trees found to visualize.")
        return None
    
    print("Creating column visualization...")
    
    # Calculate figure height based on tree heights
    def get_tree_height(node):
        """Calculate the height needed for a tree (in drawing units)"""
        if not node.get('children'):
            return 0.8
        num_children = len(node['children'])
        children_height = (num_children - 1) * 0.5
        max_child_tree_height = max([get_tree_height(child) for child in node['children']], default=0.8)
        return max(children_height + 0.8, max_child_tree_height) + 0.3
    
    tree_heights = []
    for tree in final_trees:
        tree_height = get_tree_height(tree)
        tree_heights.append(max(1.5, tree_height + 0.3))
    
    total_height = sum(tree_heights) + 1.0
    max_fig_height = 50
    fig_height = min(max(12, total_height), max_fig_height)
    fig_width = 14
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    fig.patch.set_facecolor('#f8f9fa')
    
    ax = fig.add_subplot(111)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, min(total_height + 0.5, max_fig_height * 2))
    ax.axis('off')
    
    # Title at the top
    fig.suptitle('Warframe Weapon Dependency Trees', 
                fontsize=24, fontweight='bold', y=0.98, color='#2c3e50')
    fig.text(0.5, 0.96, 'Required Weapons → Weapon That Needs Them', 
            ha='center', fontsize=12, color='#7f8c8d', style='italic')
    
    # Draw each tree as a row - start from top
    y_position = total_height - 0.3
    
    actual_bottom = float('inf')
    actual_top = float('-inf')
    
    def draw_tree_node(node, x_pos, y_pos, level=0, is_target=False):
        """Recursively draw a tree node and its children"""
        char_width = 0.08
        box_height = 0.35
        vertical_spacing = 0.5
        
        text_width = len(node['weapon']) * char_width
        box_width = max(0.6, min(1.2, text_width + 0.2))
        box_x = x_pos - box_width / 2
        box_y = y_pos - box_height / 2
        
        edge_color = '#e74c3c' if is_target else '#667eea'
        face_color = '#fff5f5' if is_target else 'white'
        
        weapon_box = FancyBboxPatch(
            (box_x, box_y), box_width, box_height,
            boxstyle="round,pad=0.05",
            linewidth=2,
            edgecolor=edge_color,
            facecolor=face_color,
            zorder=3
        )
        ax.add_patch(weapon_box)
        
        if len(node['weapon']) > 15:
            fontsize = 9
        elif len(node['weapon']) > 12:
            fontsize = 10
        else:
            fontsize = 11
        
        display_text = node['weapon']
        if len(node['weapon']) > 20:
            display_text = node['weapon'][:17] + '...'
        
        ax.text(x_pos, y_pos, display_text, 
               ha='center', va='center',
               fontsize=fontsize, fontweight='600', color='#2c3e50',
               zorder=4)
        
        return {'x': x_pos, 'y': y_pos, 'width': box_width, 'height': box_height}
    
    for idx, tree in enumerate(final_trees):
        tree_y = y_position
        ax.text(0.2, tree_y, f"Tree {idx + 1}", 
               fontsize=14, fontweight='bold', color='#667eea',
               verticalalignment='top')
        
        char_width = 0.08
        box_height = 0.35
        vertical_spacing = 0.4
        
        def draw_tree_recursive(node, x_pos, y_center, level=0):
            """Recursively draw tree with proper positioning - left to right"""
            children = node.get('children', [])
            
            if not children:
                box_info = draw_tree_node(node, x_pos, y_center, level, is_target=False)
                y_min = y_center - box_height / 2
                y_max = y_center + box_height / 2
                return box_info, (y_min, y_max)
            
            num_children = len(children)
            total_height = (num_children - 1) * vertical_spacing
            y_start = y_center - total_height / 2
            
            child_boxes = []
            min_child_y = float('inf')
            max_child_y = float('-inf')
            for i, child in enumerate(children):
                child_y = y_start + i * vertical_spacing
                child_box, (child_min_y, child_max_y) = draw_tree_recursive(child, x_pos - 1.8, child_y, level + 1)
                child_boxes.append(child_box)
                min_child_y = min(min_child_y, child_min_y)
                max_child_y = max(max_child_y, child_max_y)
            
            is_target = (level == 0)
            current_box = draw_tree_node(node, x_pos, y_center, level, is_target=is_target)
            
            for child_box in child_boxes:
                arrow_start_x = child_box['x'] + child_box['width'] / 2
                arrow_end_x = current_box['x'] - current_box['width'] / 2
                arrow_y = current_box['y']
                child_y = child_box['y']
                
                ax.annotate('', xy=(arrow_end_x, arrow_y), 
                           xytext=(arrow_start_x, child_y),
                           arrowprops=dict(arrowstyle='->', lw=2.5, 
                                          color='#667eea', alpha=0.8),
                           zorder=2)
            
            actual_min_y = min(y_center - box_height / 2, min_child_y)
            actual_max_y = max(y_center + box_height / 2, max_child_y)
            return current_box, (actual_min_y, actual_max_y)
        
        target_x = 8.0
        _, (tree_min_y, tree_max_y) = draw_tree_recursive(tree, target_x, tree_y - 0.2, level=0)
        
        actual_bottom = min(actual_bottom, tree_min_y)
        actual_top = max(actual_top, tree_y)
        
        y_position = tree_min_y - 0.3
        
        if y_position < 0:
            print(f"Warning: Tree {idx + 1} would be drawn below visible area. Adjusting ylim...")
            break
    
    if actual_bottom != float('inf') and actual_top != float('-inf'):
        ax.set_ylim(actual_bottom - 0.3, actual_top + 0.5)
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    output_file = output_dir / 'weapon_dependency_chains.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight', 
                facecolor='#f8f9fa', edgecolor='none', pad_inches=0.2)
    print(f"Saved column visualization to {output_file}")
    
    # Also save to dist folder
    dist_dir = Path(__file__).parent.parent.parent.parent / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    dist_output = dist_dir / 'weapon_dependency_chains.png'
    plt.savefig(dist_output, dpi=300, bbox_inches='tight', 
                facecolor='#f8f9fa', edgecolor='none', pad_inches=0.2)
    print(f"Saved column visualization to {dist_output}")
    
    plt.close()
    
    return output_file


if __name__ == "__main__":
    visualize_dependencies()

