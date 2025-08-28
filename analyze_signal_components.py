#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script analyzes signal generation components to determine if any
can be consolidated or should be removed.
"""

import os
import sys
import importlib.util
from pathlib import Path
from datetime import datetime
import json

def get_file_info(filepath):
    """Get file size, modification time, and other details"""
    stats = os.stat(filepath)
    return {
        'path': filepath,
        'size': stats.st_size,
        'modified': datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'timestamp': stats.st_mtime
    }

def get_import_map(files):
    """Create a mapping of which files import which"""
    import_map = {}
    
    for file in files:
        import_map[file] = []
        try:
            with open(file, 'r') as f:
                content = f.read()
                # Look for imports
                lines = content.split('\n')
                for line in lines:
                    if 'import' in line:
                        for other_file in files:
                            # Extract the module name from the path
                            module_name = os.path.basename(other_file)[:-3]
                            if module_name in line:
                                import_map[file].append(other_file)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    return import_map

def analyze_signal_generators():
    """Analyze signal generator components"""
    project_root = "/workspaces/iq-720-trading-bot"
    
    # Find all signal generator related files
    signal_files = []
    
    # Main signal generator
    if os.path.exists(os.path.join(project_root, 'src', 'signal_generator.py')):
        signal_files.append(os.path.join(project_root, 'src', 'signal_generator.py'))
    
    # Improved signal generator
    if os.path.exists(os.path.join(project_root, 'src', 'improved_signal_generator.py')):
        signal_files.append(os.path.join(project_root, 'src', 'improved_signal_generator.py'))
    
    # Utils signal generators
    util_path = os.path.join(project_root, 'src', 'utils')
    
    if os.path.exists(util_path):
        for file in os.listdir(util_path):
            if 'signal' in file and file.endswith('.py'):
                signal_files.append(os.path.join(util_path, file))
    
    # Get file info
    file_info = [get_file_info(file) for file in signal_files]
    file_info.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Get import relationships
    import_map = get_import_map(signal_files)
    
    # Output analysis
    print("=== Signal Generator Components Analysis ===")
    print(f"Found {len(signal_files)} signal-related files")
    print("\nFiles sorted by most recent:")
    
    for info in file_info:
        print(f"{info['path']}: modified {info['modified']}, size: {info['size']} bytes")
    
    print("\nImport relationships:")
    for file, imports in import_map.items():
        print(f"{os.path.basename(file)} imports from:")
        if imports:
            for imported in imports:
                print(f"  - {os.path.basename(imported)}")
        else:
            print("  - No other signal files imported")
    
    # Analyze which main files use which signal generator
    main_files = [
        os.path.join(project_root, 'src', 'main.py'),
        os.path.join(project_root, 'src', 'main_updated.py'),
        os.path.join(project_root, 'src', 'main_enhanced.py'),
        os.path.join(project_root, 'src', 'main_enhanced_improved.py'),
        os.path.join(project_root, 'src', 'main_advanced.py')
    ]
    
    main_files = [f for f in main_files if os.path.exists(f)]
    main_info = [get_file_info(file) for file in main_files]
    main_info.sort(key=lambda x: x['timestamp'], reverse=True)
    
    print("\nMain controller files sorted by most recent:")
    for info in main_info:
        print(f"{os.path.basename(info['path'])}: modified {info['modified']}")
    
    print("\nSignal generator usage in main files:")
    for main_file in main_files:
        signal_imports = []
        try:
            with open(main_file, 'r') as f:
                content = f.read()
                for signal_file in signal_files:
                    module_name = os.path.basename(signal_file)[:-3]
                    if module_name in content:
                        signal_imports.append(module_name)
                        
            print(f"{os.path.basename(main_file)} uses: {', '.join(signal_imports) if signal_imports else 'No direct signal imports'}")
        except Exception as e:
            print(f"Error reading {main_file}: {e}")

    # Recommendations
    newest_main = main_info[0]['path'] if main_info else None
    print("\n=== Recommendations ===")
    
    if newest_main:
        print(f"1. The most recently updated main file is {os.path.basename(newest_main)}")
        print(f"   Use run_advanced_bot.sh to run this version")
    
    if len(signal_files) > 1:
        newest_signal = file_info[0]['path'] if file_info else None
        if newest_signal:
            print(f"\n2. Consider consolidating signal generation components:")
            print(f"   - Keep {os.path.basename(newest_signal)} as the primary signal generator")
            print(f"   - Review other signal files for unique functionality that should be preserved")

if __name__ == "__main__":
    analyze_signal_generators()
