"""Command-line interface for NexusML."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from .config import Config
from .storage import get_storage_backend
from .git_utils import GitManager
from .metadata import MetadataManager

app = typer.Typer(help="NexusML - End-to-end ML Versioning and Serving Platform")
console = Console()


@app.command()
def store(
    model_path: str = typer.Argument(..., help="Path to the model file to store"),
    model_name: str = typer.Argument(..., help="Name of the model"),
):
    """
    Store a model artifact in cloud storage and create metadata entry.
    
    This command:
    1. Validates that the repository is clean (no uncommitted changes)
    2. Gets the current commit hash
    3. Uploads the model to cloud storage
    4. Creates/updates the .model_meta.json file
    """
    try:
        # Initialize components
        config = Config()
        git_manager = GitManager()
        metadata_manager = MetadataManager()
        storage_backend = get_storage_backend(config)
        
        # Validate model file exists
        model_file = Path(model_path).resolve()
        if not model_file.exists():
            console.print(f"[red]Error: Model file not found: {model_path}[/red]")
            raise typer.Exit(1)
        
        if not model_file.is_file():
            console.print(f"[red]Error: Path is not a file: {model_path}[/red]")
            raise typer.Exit(1)
        
        # Ensure repository is clean
        try:
            git_manager.ensure_clean()
        except RuntimeError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        # Get current commit hash
        commit_hash = git_manager.get_current_commit_hash()
        console.print(f"[green]Current commit hash: {commit_hash}[/green]")
        
        # Get file extension
        file_extension = model_file.suffix.lstrip('.') or 'bin'
        
        # Construct storage URI: bucket/model_name/commit_hash.ext
        storage_uri = f"{model_name}/{commit_hash}.{file_extension}"
        
        # Upload to cloud storage
        console.print(f"[yellow]Uploading model to cloud storage...[/yellow]")
        try:
            storage_backend.upload(model_file, storage_uri)
        except RuntimeError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        # Get file size
        file_size = model_file.stat().st_size
        
        # Update metadata
        metadata_manager.add_model(
            commit_hash=commit_hash,
            model_name=model_name,
            storage_uri=storage_uri,
            file_size=file_size,
            file_extension=file_extension
        )
        metadata_manager.save()
        
        console.print(f"[green]✓ Model artifact stored successfully![/green]")
        console.print(f"[cyan]Storage URI: {storage_uri}[/cyan]")
        console.print(
            f"\n[yellow]Action required:[/yellow] "
            f"Please git commit and git push the updated {metadata_manager.metadata_file.name} file."
        )
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def load(
    commit_hash: str = typer.Argument(..., help="Git commit hash or 'latest' to load the latest model"),
    output_path: str = typer.Argument(..., help="Path where the model will be saved"),
    model_name: Optional[str] = typer.Option(
        None,
        "--model-name",
        "-n",
        help="Name of the model (required when using 'latest')"
    ),
):
    """
    Load a model artifact from cloud storage.
    
    This command:
    1. Looks up the model metadata for the given commit hash
    2. Downloads the model from cloud storage
    3. Saves it to the specified output path
    """
    try:
        # Initialize components
        config = Config()
        metadata_manager = MetadataManager()
        storage_backend = get_storage_backend(config)
        
        # Ensure metadata file exists
        try:
            metadata_manager.ensure_exists()
        except RuntimeError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        # If commit_hash is 'latest', model_name is required
        if commit_hash == "latest" and model_name is None:
            console.print(
                "[red]Error: Model name is required when using 'latest' commit hash. "
                "Use --model-name or -n option.[/red]"
            )
            raise typer.Exit(1)
        
        # Look up storage URI
        storage_uri = metadata_manager.get_storage_uri(commit_hash, model_name)
        if storage_uri is None:
            if commit_hash == "latest":
                console.print(
                    f"[red]Error: No latest model found for model name: {model_name}[/red]"
                )
            else:
                console.print(
                    f"[red]Error: Model artifact not found for commit hash: {commit_hash}[/red]"
                )
            raise typer.Exit(1)
        
        # Download from cloud storage
        output_file = Path(output_path).resolve()
        console.print(f"[yellow]Downloading model from cloud storage...[/yellow]")
        try:
            storage_backend.download(storage_uri, output_file)
        except RuntimeError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        console.print(
            f"[green]✓ Model artifact from commit {commit_hash} "
            f"successfully loaded to {output_path}[/green]"
        )
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def list():
    """
    List all stored model artifacts.
    
    Displays a table of all model artifacts with their commit hashes,
    storage URIs, file sizes, and timestamps.
    """
    try:
        metadata_manager = MetadataManager()
        
        # Ensure metadata file exists
        try:
            metadata_manager.ensure_exists()
        except RuntimeError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        # Get all models
        models_list = metadata_manager.list_models()
        
        if not models_list:
            console.print("[yellow]No model artifacts found.[/yellow]")
            return
        
        # Create and display table
        table = Table(title="Stored Model Artifacts")
        table.add_column("Model Name", style="cyan")
        table.add_column("Commit Hash", style="green")
        table.add_column("Storage URI", style="yellow")
        table.add_column("Size", style="magenta")
        table.add_column("Timestamp", style="blue")
        table.add_column("Latest", style="bold")
        
        for model in models_list:
            size_mb = model["file_size"] / (1024 * 1024)
            table.add_row(
                model["model_name"],
                model["commit_hash"],
                model["storage_uri"],
                f"{size_mb:.2f} MB",
                model["timestamp"][:19],  # Show date and time only
                "✓" if model["is_latest"] else ""
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command()
def rollback(
    commit_hash: str = typer.Argument(..., help="Git commit hash to rollback to"),
    model_name: str = typer.Argument(..., help="Name of the model"),
):
    """
    Rollback to a previous model version by setting it as the latest.
    
    This command updates the 'latest' pointer in the metadata file to
    point to the specified commit hash for the given model.
    """
    try:
        metadata_manager = MetadataManager()
        
        # Ensure metadata file exists
        try:
            metadata_manager.ensure_exists()
        except RuntimeError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        # Set as latest
        try:
            metadata_manager.set_latest(commit_hash, model_name)
            metadata_manager.save()
        except ValueError as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            raise typer.Exit(1)
        
        console.print(
            f"[green]✓ Rolled back model '{model_name}' to commit {commit_hash}[/green]"
        )
        console.print(
            f"\n[yellow]Action required:[/yellow] "
            f"Please git commit and git push the updated {metadata_manager.metadata_file.name} file."
        )
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
