#!/usr/bin/env python3
"""
Demo script to show ModelVault functionality in action.
This demonstrates the core features without requiring cloud credentials.
"""

import json
import tempfile
from pathlib import Path
from modelvault.git_utils import GitManager
from modelvault.metadata import MetadataManager
from modelvault.config import Config

def demo_metadata_operations():
    """Demonstrate metadata management."""
    print("=" * 60)
    print("DEMO: Metadata Management")
    print("=" * 60)
    
    # Create a temporary directory for demo
    with tempfile.TemporaryDirectory() as tmpdir:
        demo_path = Path(tmpdir)
        
        # Initialize metadata manager
        metadata = MetadataManager(project_root=demo_path)
        
        # Add some demo models
        print("\n1. Adding model artifacts to metadata...")
        metadata.add_model(
            commit_hash="abc123def456",
            model_name="my_model",
            storage_uri="my_model/abc123def456.pkl",
            file_size=1024 * 1024,  # 1MB
            file_extension="pkl"
        )
        
        metadata.add_model(
            commit_hash="xyz789ghi012",
            model_name="my_model",
            storage_uri="my_model/xyz789ghi012.pkl",
            file_size=2048 * 1024,  # 2MB
            file_extension="pkl"
        )
        
        metadata.add_model(
            commit_hash="def456abc123",
            model_name="another_model",
            storage_uri="another_model/def456abc123.h5",
            file_size=512 * 1024,  # 512KB
            file_extension="h5"
        )
        
        metadata.save()
        print("   ✓ Metadata saved to .model_meta.json")
        
        # Show the metadata file
        print("\n2. Contents of .model_meta.json:")
        print("-" * 60)
        with open(demo_path / ".model_meta.json") as f:
            print(json.dumps(json.load(f), indent=2))
        
        # Demonstrate lookups
        print("\n3. Looking up storage URIs:")
        print("-" * 60)
        uri1 = metadata.get_storage_uri("abc123def456", "my_model")
        print(f"   Commit 'abc123def456' for 'my_model': {uri1}")
        
        uri2 = metadata.get_storage_uri("latest", "my_model")
        print(f"   'latest' for 'my_model': {uri2}")
        
        # List all models
        print("\n4. Listing all stored models:")
        print("-" * 60)
        models = metadata.list_models()
        for model in models:
            latest_marker = " [LATEST]" if model["is_latest"] else ""
            print(f"   {model['model_name']} @ {model['commit_hash']}{latest_marker}")
            print(f"      URI: {model['storage_uri']}")
            print(f"      Size: {model['file_size'] / 1024:.1f} KB")
            print()


def demo_git_integration():
    """Demonstrate Git integration."""
    print("=" * 60)
    print("DEMO: Git Integration")
    print("=" * 60)
    
    try:
        git_manager = GitManager()
        
        print("\n1. Current Git Status:")
        print("-" * 60)
        commit_hash = git_manager.get_current_commit_hash()
        print(f"   Current commit hash: {commit_hash}")
        
        is_clean = git_manager.is_clean()
        print(f"   Repository is clean: {is_clean}")
        
        if not is_clean:
            uncommitted = git_manager.get_uncommitted_files()
            print(f"   Uncommitted files: {', '.join(uncommitted)}")
        else:
            print("   ✓ No uncommitted changes - ready to store model!")
            
    except Exception as e:
        print(f"   ⚠ Error: {e}")


def demo_cli_commands():
    """Show what CLI commands would do."""
    print("=" * 60)
    print("DEMO: CLI Commands Overview")
    print("=" * 60)
    
    commands = [
        {
            "command": "modelvault store ./models/my_model.pkl my_model",
            "description": "Stores a model file:\n  - Validates Git repo is clean\n  - Gets current commit hash\n  - Uploads to cloud storage\n  - Creates metadata entry"
        },
        {
            "command": "modelvault load abc123def456 ./models/restored.pkl",
            "description": "Loads a model by commit hash:\n  - Looks up storage URI in metadata\n  - Downloads from cloud storage\n  - Saves to specified path"
        },
        {
            "command": "modelvault load latest ./models/latest.pkl --model-name my_model",
            "description": "Loads the latest version of a model"
        },
        {
            "command": "modelvault list",
            "description": "Lists all stored models with metadata"
        },
        {
            "command": "modelvault rollback abc123def456 my_model",
            "description": "Sets a previous version as the latest"
        }
    ]
    
    for i, cmd_info in enumerate(commands, 1):
        print(f"\n{i}. {cmd_info['command']}")
        print(f"   {cmd_info['description']}")


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("MODELVAULT DEMONSTRATION")
    print("=" * 60)
    print("\nThis demo shows ModelVault's core functionality.")
    print("Note: Full functionality requires cloud credentials (AWS S3 or GCS).\n")
    
    # Run demos
    demo_metadata_operations()
    print("\n")
    demo_git_integration()
    print("\n")
    demo_cli_commands()
    
    print("\n" + "=" * 60)
    print("TO TEST FULL FUNCTIONALITY:")
    print("=" * 60)
    print("1. Create .modelvaultrc file with your cloud settings")
    print("2. Configure cloud credentials (AWS or GCP)")
    print("3. Create a sample model file")
    print("4. Run: modelvault store <model_file> <model_name>")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
