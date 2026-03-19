"""
Convert PNG logo to ICO format for Windows taskbar icon.
Run once to create the .ico file.
"""

from pathlib import Path
from PIL import Image

# Paths
ROOT = Path(__file__).parent.parent
PNG_PATH = ROOT / "assets" / "icons" / "opaium_logo_nobg.png"
ICO_PATH = ROOT / "assets" / "icons" / "opaium_logo_nobg.ico"

def convert_png_to_ico():
    """Convert PNG to ICO with multiple sizes."""
    if not PNG_PATH.exists():
        print(f"Error: {PNG_PATH} not found")
        return False
    
    try:
        # Open the PNG
        img = Image.open(PNG_PATH)
        
        # Convert to RGBA if needed
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Create multiple sizes for Windows (16x16, 32x32, 48x48, 256x256)
        sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
        
        # Save as ICO with multiple sizes
        img.save(
            ICO_PATH,
            format='ICO',
            sizes=sizes
        )
        
        print(f"[OK] Created {ICO_PATH}")
        print(f"   Sizes: {', '.join(f'{w}x{h}' for w, h in sizes)}")
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


if __name__ == "__main__":
    print("Converting PNG logo to ICO format...")
    print(f"Source: {PNG_PATH}")
    print(f"Output: {ICO_PATH}")
    print()
    
    if convert_png_to_ico():
        print("\n[SUCCESS] Done! The taskbar icon will now show properly.")
    else:
        print("\n[FAILED] Failed to convert icon.")
