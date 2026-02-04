"""Fix emoji encoding issues in Python files for Windows console compatibility"""
import os

# Emoji to ASCII mapping
emoji_map = {
    '🔨': '[BUILD]',
    '✅': '[OK]',
    '⏳': '[WAIT]',
    '🪟': '[WIN]',
    '🚀': '[FAST]',
    '🎉': '[DONE]',
    '❌': '[X]',
    '💪': '[STRONG]',
    '📊': '[DATA]',
    '📁': '[FILE]',
    '📂': '[FOLDER]',
    '⚠️': '[WARN]',
    '⚙️': '[GEAR]',
    '🔧': '[TOOL]',
    '✔': '[OK]',
    '✓': '[OK]',  # checkmark
    '✗': '[X]',   # X mark
    '➡': '->',
    '🔄': '[SYNC]',
    '📝': '[NOTE]',
    '🔍': '[SEARCH]',
    '💡': '[TIP]',
    '🎬': '[VIDEO]',
    '🖼': '[IMG]',
    '📷': '[CAM]',
    '🎨': '[COLOR]',
    '🏃': '[RUN]',
    '⬆': '[UP]',
    '⬇': '[DOWN]',
    '🔥': '[HOT]',
    '❓': '[?]',
    '❗': '[!]',
    '➕': '[+]',
    '➖': '[-]',
    '🖥': '[SCREEN]',
    '💻': '[PC]',
    '🌐': '[WEB]',
    '⏱': '[TIME]',
    '🏁': '[FLAG]',
}

def fix_file(filepath):
    """Replace emojis in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original = content
        for emoji, replacement in emoji_map.items():
            content = content.replace(emoji, replacement)
        
        if content != original:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return False

# Fix all Python files in client folder
base_dir = 'V:/_MY_APPS/ImgApp_1/client'
fixed_count = 0

for root, dirs, files in os.walk(base_dir):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            if fix_file(path):
                print(f"Fixed: {path}")
                fixed_count += 1

print(f"\\nDone! Fixed {fixed_count} files")
