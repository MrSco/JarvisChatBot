# Assistant Manifest Generator

This script generates PWA (Progressive Web App) manifest files and placeholder icons for chatbot assistants. It creates:

1. A manifest.json file for each assistant
2. A set of standard icon images in different sizes (16x16, 32x32, 48x48, 192x192, 512x512)
3. A favicon.ico file

## Requirements

- Python 3.6+
- Pillow library (for image generation)

Install dependencies with:

```bash
pip install pillow
```

## Usage

Basic usage:

```bash
python generate_manifest.py
```

This will:
- Look for `assistants.json` in the current directory
- Create manifest files in the `static` directory
- Create icon images in the `static/images` directory
- Process all assistants found in the JSON file
- Skip generating images that already exist (unless `--force` is specified)

### Command-line Options

```
--assistants-json PATH  Path to assistants.json file (default: assistants.json)
--output-dir DIR        Output directory for manifest files (default: static)
--images-dir DIR        Output directory for icon images (default: static/images)
--assistant NAME        Generate only for a specific assistant (optional)
--force                 Force regeneration of existing files
```

### Examples

Generate for all assistants using a specific assistants.json file:
```bash
python generate_manifest.py --assistants-json my_assistants.json
```

Generate only for a specific assistant:
```bash
python generate_manifest.py --assistant Jarvis
```

Force regeneration of existing files:
```bash
python generate_manifest.py --force
```

Specify custom output directories:
```bash
python generate_manifest.py --output-dir website/static --images-dir website/static/img
```

## Assistant Configuration

The script uses the assistants.json file to get information about each assistant. The following fields are used:

- `name`: The assistant's display name (used as part of icon filenames)
- `page_title`: The full page title (used as the full name in the manifest)
- `acronym`: (optional) The acronym of the assistant
- `theme_color`: (optional) The theme color to use in the manifest and for icons

### Theme Color Selection

The script determines the theme color in the following order:
1. From the `theme_color` field in assistants.json (if present)
2. From an existing manifest file (if it exists and `--force` is not specified)
3. From the predefined DEFAULT_COLORS dictionary in the script
4. Fallback to a default blue color (#3498db)

Default theme colors are defined in the script for common assistants:
- Jarvis: Blue (#3498db)
- Friday: Pink (#e84393)
- Bluey: Light blue (#90D5F6)
- TARS: Dark gray (#2d3436)
- HAL: Red (#e50322)
- Joshua: Green (#27ae60)

You can add more default colors in the DEFAULT_COLORS dictionary in the script.

## Output Files

For each assistant named "AssistantName", the script generates:

- `static/assistantname-manifest.json`
- `static/images/assistantname-android-chrome-192x192.png`
- `static/images/assistantname-android-chrome-512x512.png`
- `static/images/assistantname-apple-touch-icon.png`
- `static/images/assistantname-favicon-16x16.png`
- `static/images/assistantname-favicon-32x32.png`
- `static/images/assistantname-favicon-48x48.png`
- `static/images/assistantname-favicon.ico`

All image files contain a simple circular icon with the assistant's initial in the center, using the assistant's theme color. 