"""
Daily automated backup — copies memory.db, knowledge_graph.db, and chroma_data/.
Keeps last 7 backups, deletes older ones. Optionally encrypts with EncryptionManager.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("mira.helpers.backup")


def create_backup(
    data_dir: Path,
    backup_dir: Path,
    encrypt: bool = False,
    encryption_key_path: Optional[Path] = None,
) -> dict:
    """Create a timestamped backup of critical data files.

    Args:
        data_dir: Path to agent/data/ containing memory.db, knowledge_graph.db, chroma_data/
        backup_dir: Parent directory where timestamped backup folders are created
        encrypt: Whether to encrypt the backup using EncryptionManager
        encryption_key_path: Path to encryption key file (required if encrypt=True)

    Returns:
        dict with keys: backup_path, size_bytes, files_copied, timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"backup_{timestamp}"
    target.mkdir(parents=True, exist_ok=True)

    files_copied = 0
    total_size = 0

    # Files to back up
    files_to_copy = [
        data_dir / "memory.db",
        data_dir / "knowledge_graph.db",
    ]

    for src in files_to_copy:
        if src.exists():
            dst = target / src.name
            shutil.copy2(str(src), str(dst))
            total_size += dst.stat().st_size
            files_copied += 1
            logger.info(f"Backed up {src.name}")
        else:
            logger.warning(f"Backup source not found: {src}")

    # Copy chroma_data directory
    chroma_src = data_dir / "chroma_data"
    if chroma_src.exists() and chroma_src.is_dir():
        chroma_dst = target / "chroma_data"
        shutil.copytree(str(chroma_src), str(chroma_dst))
        # Calculate size of copied directory
        for f in chroma_dst.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                files_copied += 1
        logger.info("Backed up chroma_data/")
    else:
        logger.warning("chroma_data/ not found, skipping")

    # Optionally encrypt the backup
    if encrypt and encryption_key_path:
        try:
            from helpers.encryption import EncryptionManager

            enc = EncryptionManager(key_path=encryption_key_path)
            enc.initialise()
            for f in target.rglob("*"):
                if f.is_file() and f.suffix in (".db",):
                    enc.encrypt_file(f)
                    logger.info(f"Encrypted {f.name}")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")

    # Prune old backups — keep last 7
    _prune_old_backups(backup_dir, keep=7)

    result = {
        "backup_path": str(target),
        "size_bytes": total_size,
        "files_copied": files_copied,
        "timestamp": timestamp,
    }
    logger.info(f"Backup complete: {files_copied} items, {total_size / 1024:.1f} KB")
    return result


def _prune_old_backups(backup_dir: Path, keep: int = 7):
    """Delete oldest backups, keeping only the most recent `keep` folders."""
    if not backup_dir.exists():
        return

    backups = sorted(
        [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith("backup_")],
        key=lambda d: d.name,
        reverse=True,
    )

    for old in backups[keep:]:
        try:
            shutil.rmtree(str(old))
            logger.info(f"Pruned old backup: {old.name}")
        except Exception as e:
            logger.error(f"Failed to prune backup {old.name}: {e}")
