"""Git integration utilities."""

from pathlib import Path
from typing import Optional
import git
from git.exc import InvalidGitRepositoryError, GitCommandError


class GitManager:
    """Manages Git operations for ModelVault."""
    
    def __init__(self, repo_path: Optional[Path] = None):
        """
        Initialize Git manager.
        
        Args:
            repo_path: Path to the Git repository. If None, uses current directory.
        """
        if repo_path is None:
            repo_path = Path.cwd()
        self.repo_path = Path(repo_path).resolve()
        
        try:
            self.repo = git.Repo(self.repo_path)
        except InvalidGitRepositoryError:
            raise RuntimeError(
                f"Not a Git repository: {self.repo_path}.\n"
                f"Action: Please initialize a Git repository or run ModelVault from within a Git repository."
            )
    
    def get_current_commit_hash(self) -> str:
        """
        Get the current commit hash.
        
        Returns:
            Current commit hash (short format).
        """
        try:
            return self.repo.head.commit.hexsha[:12]  # Use first 12 characters
        except GitCommandError as e:
            raise RuntimeError(f"Failed to get commit hash: {str(e)}")
    
    def is_clean(self) -> bool:
        """
        Check if the repository is clean (no uncommitted changes).
        
        Returns:
            True if repository is clean, False otherwise.
        """
        return not self.repo.is_dirty()
    
    def get_uncommitted_files(self) -> list:
        """
        Get list of uncommitted files.
        
        Returns:
            List of uncommitted file paths.
        """
        return [item.a_path for item in self.repo.index.diff(None)]
    
    def ensure_clean(self) -> None:
        """
        Ensure the repository is clean, raising an error if not.
        
        Raises:
            RuntimeError: If repository has uncommitted changes.
        """
        if not self.is_clean():
            uncommitted = self.get_uncommitted_files()
            raise RuntimeError(
                f"Repository has uncommitted changes.\n"
                f"Uncommitted files: {', '.join(uncommitted)}\n"
                f"Action: Please commit or stash your changes before storing a model artifact."
            )
