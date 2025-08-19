# Script to find where to add documentation about PATH behavior
import os
import glob

def find_documentation_files():
    """Find relevant documentation files to update"""
    
    # Look for documentation files
    doc_files = []
    
    # Check common documentation locations
    for pattern in ['docs/**/*.rst', 'docs/**/*.md', 'docs/*.rst', 'docs/*.md']:
        doc_files.extend(glob.glob(pattern, recursive=True))
    
    print("Found documentation files:")
    for doc_file in sorted(doc_files):
        print(f"  {doc_file}")
    
    print("\nLooking for files that might contain PATH or environment documentation...")
    
    relevant_files = []
    for doc_file in doc_files:
        if any(keyword in doc_file.lower() for keyword in ['env', 'path', 'tutorial', 'guide']):
            relevant_files.append(doc_file)
            print(f"  📄 {doc_file}")
    
    # Check content of relevant files for PATH mentions
    print("\nChecking for existing PATH documentation...")
    for doc_file in relevant_files:
        try:
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'PATH' in content or 'EnvPath' in content:
                print(f"  📝 {doc_file} - Contains PATH/EnvPath references")
                
        except Exception as e:
            print(f"  ❌ Could not read {doc_file}: {e}")

if __name__ == "__main__":
    find_documentation_files()
