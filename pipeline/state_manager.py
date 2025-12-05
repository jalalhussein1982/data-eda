"""State Manager for pipeline with branching and rollback support."""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, List
import pandas as pd
import hashlib
import json
import atexit
import shutil


@dataclass
class StateRecord:
    """Metadata for a single pipeline state."""
    id: str
    parent: Optional[str]
    timestamp: str
    data_hash: str
    row_count: int
    col_count: int
    config_snapshot: dict
    delta_summary: str


@dataclass
class Branch:
    """A branch in the pipeline state tree."""
    created_at: str
    forked_from: Optional[dict]
    states: List[StateRecord]

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "forked_from": self.forked_from,
            "states": [asdict(s) for s in self.states]
        }


class StateNotFoundError(Exception):
    """Raised when a requested state cannot be found."""
    pass


class StateManager:
    """
    Manages pipeline states with branching and rollback support.

    Uses full DataFrame copies with LRU eviction for MVP.
    Evicted states persist to disk as Parquet files.
    """

    def __init__(
        self,
        cache_size: int = 5,
        temp_dir: Path = Path("/tmp/pipeline_states")
    ):
        self.cache_size = cache_size
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(exist_ok=True)

        self.branches: Dict[str, Branch] = {
            "main": Branch(
                created_at=pd.Timestamp.now().isoformat(),
                forked_from=None,
                states=[]
            )
        }
        self.active_branch: str = "main"
        self._memory_cache: Dict[str, pd.DataFrame] = {}
        self._access_order: List[str] = []

        # Register cleanup on session end
        atexit.register(self.cleanup)

    def commit_state(
        self,
        state_id: str,
        df: pd.DataFrame,
        config_snapshot: dict,
        delta_summary: str
    ) -> None:
        """
        Commit a new state to the active branch.

        Args:
            state_id: Identifier for this state (e.g., 'df_clean')
            df: The DataFrame at this checkpoint
            config_snapshot: Configuration used to reach this state
            delta_summary: Human-readable description of changes
        """
        state_key = f"{self.active_branch}::{state_id}"

        # Store in memory cache
        self._add_to_cache(state_key, df.copy())

        # Record metadata
        branch = self.branches[self.active_branch]
        parent = branch.states[-1].id if branch.states else None

        branch.states.append(StateRecord(
            id=state_id,
            parent=parent,
            timestamp=pd.Timestamp.now().isoformat(),
            data_hash=self._compute_hash(df),
            row_count=len(df),
            col_count=len(df.columns),
            config_snapshot=config_snapshot,
            delta_summary=delta_summary
        ))

    def load_state(self, branch: str, state_id: str) -> pd.DataFrame:
        """
        Load a state from cache or disk.

        Args:
            branch: Branch name
            state_id: State identifier

        Returns:
            DataFrame at the requested state

        Raises:
            StateNotFoundError: If state doesn't exist
        """
        state_key = f"{branch}::{state_id}"

        # Check memory cache
        if state_key in self._memory_cache:
            self._touch(state_key)
            return self._memory_cache[state_key].copy()

        # Load from disk
        disk_path = self.temp_dir / f"{state_key.replace('::', '__')}.parquet"
        if disk_path.exists():
            df = pd.read_parquet(disk_path)
            self._add_to_cache(state_key, df)
            return df.copy()

        raise StateNotFoundError(f"State {state_key} not found")

    def get_current_state(self) -> Optional[pd.DataFrame]:
        """Get the current (latest) state of the active branch."""
        branch = self.branches[self.active_branch]
        if not branch.states:
            return None
        terminal_state = branch.states[-1].id
        return self.load_state(self.active_branch, terminal_state)

    def get_current_state_id(self) -> Optional[str]:
        """Get the ID of the current state."""
        branch = self.branches[self.active_branch]
        if not branch.states:
            return None
        return branch.states[-1].id

    def create_branch(
        self,
        new_branch_name: str,
        fork_from_state: str
    ) -> None:
        """
        Create a new branch from a specific state.

        Args:
            new_branch_name: Name for the new branch
            fork_from_state: State ID to fork from
        """
        source_branch = self.active_branch
        source_df = self.load_state(source_branch, fork_from_state)
        source_config = self._get_config_at_state(source_branch, fork_from_state)

        # Create new branch
        self.branches[new_branch_name] = Branch(
            created_at=pd.Timestamp.now().isoformat(),
            forked_from={"branch": source_branch, "state_id": fork_from_state},
            states=[]
        )

        # Switch to new branch and commit fork point
        self.active_branch = new_branch_name
        self.commit_state(
            state_id=fork_from_state,
            df=source_df,
            config_snapshot=source_config,
            delta_summary=f"Forked from {source_branch}::{fork_from_state}"
        )

    def switch_branch(self, branch_name: str) -> pd.DataFrame:
        """
        Switch to a different branch.

        Args:
            branch_name: Branch to switch to

        Returns:
            DataFrame at the terminal state of that branch
        """
        if branch_name not in self.branches:
            raise ValueError(f"Branch '{branch_name}' does not exist")

        self.active_branch = branch_name
        terminal_state = self.branches[branch_name].states[-1].id
        return self.load_state(branch_name, terminal_state)

    def delete_branch(self, branch_name: str) -> None:
        """
        Delete a branch and its cached states.

        Args:
            branch_name: Branch to delete (cannot be 'main')
        """
        if branch_name == "main":
            raise ValueError("Cannot delete main branch")
        if branch_name == self.active_branch:
            raise ValueError("Cannot delete active branch")

        # Remove from cache
        keys_to_remove = [k for k in self._memory_cache if k.startswith(f"{branch_name}::")]
        for key in keys_to_remove:
            del self._memory_cache[key]
            if key in self._access_order:
                self._access_order.remove(key)

        # Remove disk files
        for file in self.temp_dir.glob(f"{branch_name}__*.parquet"):
            file.unlink()

        # Remove branch
        del self.branches[branch_name]

    def get_branch_summary(self, branch_name: str) -> dict:
        """Get summary statistics for a branch."""
        branch = self.branches[branch_name]
        if not branch.states:
            return {"states": 0, "terminal_state": None}

        terminal = branch.states[-1]
        return {
            "states": len(branch.states),
            "terminal_state": terminal.id,
            "row_count": terminal.row_count,
            "col_count": terminal.col_count,
            "last_modified": terminal.timestamp
        }

    def get_state_history(self, branch_name: Optional[str] = None) -> List[StateRecord]:
        """Get state history for a branch."""
        branch_name = branch_name or self.active_branch
        return self.branches[branch_name].states

    def compare_branches(
        self,
        branch_a: str,
        branch_b: str,
        state_id: str = "df_final"
    ) -> dict:
        """
        Compare terminal states of two branches.

        Returns:
            Dictionary with comparison metrics
        """
        df_a = self.load_state(branch_a, state_id)
        df_b = self.load_state(branch_b, state_id)

        cols_a = set(df_a.columns)
        cols_b = set(df_b.columns)

        return {
            "branch_a": {
                "rows": len(df_a),
                "cols": len(df_a.columns),
                "memory_mb": df_a.memory_usage(deep=True).sum() / 1e6
            },
            "branch_b": {
                "rows": len(df_b),
                "cols": len(df_b.columns),
                "memory_mb": df_b.memory_usage(deep=True).sum() / 1e6
            },
            "columns_only_in_a": list(cols_a - cols_b),
            "columns_only_in_b": list(cols_b - cols_a),
            "common_columns": list(cols_a & cols_b)
        }

    def export_pipeline(self, output_dir: Path) -> None:
        """
        Export complete pipeline for reproducibility.

        Creates:
            - df_raw.parquet: Original uploaded data
            - state_store.json: Complete branch/state metadata
            - pipeline_config.json: Terminal configuration
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export raw data
        try:
            raw_df = self.load_state("main", "df_raw")
            raw_df.to_parquet(output_dir / "df_raw.parquet")
        except StateNotFoundError:
            pass

        # Export state store
        store_export = {
            "branches": {
                name: branch.to_dict()
                for name, branch in self.branches.items()
            },
            "active_branch": self.active_branch
        }
        with open(output_dir / "state_store.json", "w") as f:
            json.dump(store_export, f, indent=2)

        # Export terminal config
        if self.branches[self.active_branch].states:
            terminal_state = self.branches[self.active_branch].states[-1]
            with open(output_dir / "pipeline_config.json", "w") as f:
                json.dump(terminal_state.config_snapshot, f, indent=2)

    def _add_to_cache(self, state_key: str, df: pd.DataFrame) -> None:
        """Add to cache with LRU eviction."""
        if state_key in self._memory_cache:
            self._touch(state_key)
            return

        # Evict if at capacity
        while len(self._memory_cache) >= self.cache_size:
            evict_key = self._access_order.pop(0)
            evicted_df = self._memory_cache.pop(evict_key)

            # Persist to disk
            safe_key = evict_key.replace("::", "__")
            disk_path = self.temp_dir / f"{safe_key}.parquet"
            evicted_df.to_parquet(disk_path)

        self._memory_cache[state_key] = df
        self._access_order.append(state_key)

    def _touch(self, state_key: str) -> None:
        """Mark state as recently accessed."""
        if state_key in self._access_order:
            self._access_order.remove(state_key)
        self._access_order.append(state_key)

    def _compute_hash(self, df: pd.DataFrame) -> str:
        """Compute hash for integrity verification."""
        return hashlib.md5(
            pd.util.hash_pandas_object(df).values.tobytes()
        ).hexdigest()

    def _get_config_at_state(self, branch: str, state_id: str) -> dict:
        """Retrieve config snapshot for a specific state."""
        for state in self.branches[branch].states:
            if state.id == state_id:
                return state.config_snapshot
        return {}

    def cleanup(self) -> None:
        """Purge all temp files - GDPR erasure compliance."""
        # Clear memory
        self._memory_cache.clear()
        self._access_order.clear()

        # Clear disk
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        # Log for compliance audit (no user data in log)
        print(f"[GDPR] Session data purged at {pd.Timestamp.now().isoformat()}")

    def reset(self) -> None:
        """Reset state manager to initial state."""
        self.cleanup()
        self.temp_dir.mkdir(exist_ok=True)
        self.branches = {
            "main": Branch(
                created_at=pd.Timestamp.now().isoformat(),
                forked_from=None,
                states=[]
            )
        }
        self.active_branch = "main"
        self._memory_cache = {}
        self._access_order = []
