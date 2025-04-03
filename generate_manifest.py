#!/usr/bin/env python3
import os
import json
import argparse
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

# Image sizes needed for PWA manifest
IMAGE_SIZES = {
    "android-chrome-192x192.png": (192, 192),
    "android-chrome-512x512.png": (512, 512),
    "apple-touch-icon.png": (180, 180),
    "favicon-16x16.png": (16, 16),
    "favicon-32x32.png": (32, 32),
    "favicon-48x48.png": (48, 48),
}

# Default colors for each assistant if not specified
DEFAULT_COLORS = {
    "jarvis": "#3498db",  # Blue
    "friday": "#e84393",  # Pink
    "bluey": "#90D5F6",   # Light blue
    "tars": "#2d3436",    # Dark gray
    "hal": "#e50322",     # Red
    "joshua": "#27ae60",  # Green
    # Add more assistants with their theme colors as needed
}

def get_existing_theme_color(assistant_name, output_dir):
    """Try to get the theme color from an existing manifest file"""
    manifest_path = Path(output_dir) / f"{assistant_name.lower()}-manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
                if "theme_color" in manifest:
                    return manifest["theme_color"]
        except Exception as e:
            print(f"Error reading existing manifest: {e}")
    return None

def generate_manifest(assistant_name, page_title, acronym, theme_color, output_dir):
    """Generate a manifest.json file for the given assistant"""
    manifest = {
        "short_name": assistant_name,
        "name": page_title,
        "icons": [
            {
                "src": f"/static/images/{assistant_name.lower()}-android-chrome-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": f"/static/images/{assistant_name.lower()}-android-chrome-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ],
        "start_url": "..",
        "display": "standalone",
        "theme_color": theme_color,
        "background_color": "#ffffff"
    }
    
    # Create static directory if it doesn't exist
    manifest_dir = Path(output_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    
    # Write manifest to file
    manifest_path = manifest_dir / f"{assistant_name.lower()}-manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=4)
    
    print(f"Generated manifest file: {manifest_path}")
    return manifest

def get_text_dimensions(draw, text, font):
    """Get text dimensions using the appropriate method for the Pillow version"""
    try:
        # For newer Pillow versions
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        # For older Pillow versions
        return draw.textsize(text, font=font)

def generate_icon(assistant_name, color, size, output_path):
    """Generate a placeholder icon with the assistant's initial"""
    width, height = size
    img = Image.new('RGBA', (width, height), color=(255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw a circle with the theme color
    circle_diameter = min(width, height) - 4
    circle_radius = circle_diameter // 2
    circle_x = (width - circle_diameter) // 2
    circle_y = (height - circle_diameter) // 2
    draw.ellipse(
        [circle_x, circle_y, circle_x + circle_diameter, circle_y + circle_diameter],
        fill=color
    )
    
    # Add assistant's initial
    try:
        # Try to use a system font
        font_size = circle_diameter // 2
        try:
            # Try to find a suitable font
            font_path = None
            if os.path.exists("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            elif os.path.exists("C:/Windows/Fonts/Arial.ttf"):
                font_path = "C:/Windows/Fonts/Arial.ttf"
            
            if font_path:
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
                
        except Exception:
            # Fall back to default font
            font = ImageFont.load_default()
            
        # Get initial letter and center it
        initial = assistant_name[0].upper()
        text_width, text_height = get_text_dimensions(draw, initial, font)
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2
        
        # Draw the text
        draw.text((text_x, text_y), initial, fill="white", font=font)
    except Exception as e:
        print(f"Error adding text: {e}")
        # Continue without text if there's an error
    
    # Save the image
    img.save(output_path, "PNG")
    print(f"Generated icon: {output_path}")

def generate_favicon(assistant_name, color, output_path):
    """Generate a favicon.ico file from the 32x32 PNG"""
    # Create a 32x32 image
    png_path = str(output_path).replace(".ico", "-32x32.png")
    if not os.path.exists(png_path):
        generate_icon(assistant_name, color, (32, 32), png_path)
    
    # Convert to ICO
    img = Image.open(png_path)
    img.save(output_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    print(f"Generated favicon: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate PWA manifest and icons for assistants")
    parser.add_argument("--assistants-json", default="assistants.json", help="Path to assistants.json file")
    parser.add_argument("--output-dir", default="static", help="Output directory for manifest files")
    parser.add_argument("--images-dir", default="static/images", help="Output directory for icon images")
    parser.add_argument("--assistant", help="Generate only for a specific assistant (optional)")
    parser.add_argument("--force", action="store_true", help="Force regeneration of existing files")
    args = parser.parse_args()
    
    # Create output directories if they don't exist
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    Path(args.images_dir).mkdir(parents=True, exist_ok=True)
    
    # Load assistants data
    try:
        with open(args.assistants_json, 'r') as f:
            assistants = json.load(f)
    except FileNotFoundError:
        print(f"Error: {args.assistants_json} not found. Using example file.")
        try:
            with open(f"{args.assistants_json}.example", 'r') as f:
                assistants = json.load(f)
        except FileNotFoundError:
            print(f"Error: {args.assistants_json}.example not found. Exiting.")
            return
    
    # Process each assistant or just the specified one
    for key, data in assistants.items():
        if args.assistant and args.assistant.lower() != key.lower():
            continue
        
        assistant_name = data.get("name", key.capitalize())
        page_title = data.get("page_title", assistant_name)
        acronym = data.get("acronym", "")
        
        # Check for theme_color in data first, then existing manifest, then defaults
        theme_color = data.get("theme_color", None)
        if not theme_color and not args.force:
            theme_color = get_existing_theme_color(assistant_name, args.output_dir)
        if not theme_color:
            theme_color = DEFAULT_COLORS.get(key.lower(), "#3498db")  # Default to blue if not found
        
        print(f"\nProcessing assistant: {assistant_name} (theme color: {theme_color})")
        
        # Generate manifest file
        manifest = generate_manifest(
            assistant_name, 
            page_title, 
            acronym, 
            theme_color, 
            args.output_dir
        )
        
        # Generate icons
        for img_name, size in IMAGE_SIZES.items():
            img_path = Path(args.images_dir) / f"{assistant_name.lower()}-{img_name}"
            if not img_path.exists() or args.force:
                generate_icon(assistant_name, theme_color, size, img_path)
            else:
                print(f"Skipped existing icon: {img_path} (use --force to override)")
        
        # Generate favicon.ico
        favicon_path = Path(args.images_dir) / f"{assistant_name.lower()}-favicon.ico"
        if not favicon_path.exists() or args.force:
            generate_favicon(assistant_name, theme_color, favicon_path)
        else:
            print(f"Skipped existing favicon: {favicon_path} (use --force to override)")
    
    print("\nManifest and icon generation completed!")

if __name__ == "__main__":
    main() 