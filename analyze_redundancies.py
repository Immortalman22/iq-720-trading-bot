#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to identify conflicts and redundancies in the codebase
"""

import os
import glob
import difflib
import hashlib
import re

def summarize_file(filepath):
    """Generate summary of file content"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Count lines
    lines = content.count('\n') + 1
    
    # Get import statements
    imports = re.findall(r'^import\s+.*$|^from\s+.*\s+import\s+.*$', 
                         content, re.MULTILINE)
    
    # Find class definitions
    classes = re.findall(r'^class\s+(\w+).*:$', content, re.MULTILINE)
    
    # Find function definitions
    functions = re.findall(r'^def\s+(\w+).*:$', content, re.MULTILINE)
    
    # Calculate hash of file
    file_hash = hashlib.md5(content.encode()).hexdigest()
    
    return {
        'filepath': filepath,
        'lines': lines,
        'imports': imports,
        'classes': classes,
        'functions': functions,
        'hash': file_hash
    }

def print_file_summary(summary):
    """Print file summary in readable format"""
    print(f"File: {summary['filepath']}")
    print(f"Lines: {summary['lines']}")
    print(f"Hash: {summary['hash']}")
    print("Classes:")
    for cls in summary['classes']:
        print(f"  - {cls}")
    print("Functions:")
    for func in summary['functions']:
        print(f"  - {func}")
    print("Imports:")
    for imp in summary['imports'][:5]:  # Limit to 5 imports for brevity
        print(f"  - {imp}")
    if len(summary['imports']) > 5:
        print(f"  - ... ({len(summary['imports']) - 5} more)")
    print("-" * 80)

def main():
    """Main function to analyze code redundancies"""
    print("Code Redundancy Analysis")
    print("=" * 80)
    
    # Find main files
    main_files = glob.glob('src/main_*.py')
    
    # Summarize each file
    summaries = [summarize_file(f) for f in main_files]
    
    # Print summaries
    print("\nFile Summaries:")
    for summary in summaries:
        print_file_summary(summary)
    
    # Check for duplicate hashes
    hashes = {}
    for summary in summaries:
        hashes.setdefault(summary['hash'], []).append(summary['filepath'])
    
    print("\nDuplicate Files:")
    for hash_val, files in hashes.items():
        if len(files) > 1:
            print(f"Hash: {hash_val}")
            for f in files:
                print(f"  - {f}")
    
    # Check for similar class names
    all_classes = {}
    for summary in summaries:
        for cls in summary['classes']:
            all_classes.setdefault(cls, []).append(summary['filepath'])
    
    print("\nShared Classes:")
    for cls, files in all_classes.items():
        if len(files) > 1:
            print(f"Class: {cls}")
            for f in files:
                print(f"  - {f}")

if __name__ == "__main__":
    main()
