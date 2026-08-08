import os
from pathlib import Path

from autoresearch.snapshot import IncrementalSnapshotter


def test_verification_hash_detects_same_stat_content_change(tmp_path: Path) -> None:
    story = tmp_path / "story.md"
    story.write_text("first", encoding="utf-8")
    snapshotter = IncrementalSnapshotter(tmp_path)
    before = snapshotter.snapshot(paths=("story.md",), force_hash=())
    stat = story.stat()

    story.write_text("other", encoding="utf-8")
    os.utime(story, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    cached = snapshotter.snapshot(paths=("story.md",), force_hash=())
    verified = snapshotter.snapshot(paths=("story.md",), force_hash=(), verify_content=True)
    assert cached == before
    assert verified != before


def test_excluded_directory_is_pruned_before_file_hashing(tmp_path: Path) -> None:
    included = tmp_path / "paper" / "STORY.md"
    excluded = tmp_path / "paper" / "venue-corpus" / "large.bin"
    included.parent.mkdir(parents=True)
    excluded.parent.mkdir(parents=True)
    included.write_text("story", encoding="utf-8")
    excluded.write_bytes(b"large-input")

    snapshot = IncrementalSnapshotter(tmp_path).snapshot(
        paths=("paper",), exclude=("paper/venue-corpus",), verify_content=True
    )

    assert set(snapshot) == {"paper/STORY.md"}
