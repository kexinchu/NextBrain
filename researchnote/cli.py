"""ResearchNote CLI: record, note, index, browser."""
import argparse
import sys


def cmd_record(args):
    """Record a paper: fetch metadata → Zotero → classify → generate note → Obsidian."""
    from researchnote.scholar.metadata import fetch_metadata
    from researchnote.scholar.classifier import classify_paper
    from researchnote.scholar.note_generator import generate_paper_note
    from researchnote.scholar.obsidian_writer import write_paper_note, get_note_stem, find_existing_note

    if args.browser:
        from researchnote import config
        config.set_use_browser_llm(True)

    url = args.url
    print(f"[record] Processing: {url}")

    # 1. Fetch metadata
    print("[record] Fetching metadata...")
    meta = fetch_metadata(url)
    if not meta.title:
        print("[record] ERROR: Could not retrieve paper metadata. Check the URL.", file=sys.stderr)
        sys.exit(1)
    print(f"[record] Title: {meta.title}")
    print(f"[record] Authors: {', '.join(meta.authors[:5])}")

    # 1.5. Duplicate check — skip if note already exists (unless --force)
    if not args.force:
        vault_path = args.vault if args.vault else None
        existing = find_existing_note(meta.source_url or url, vault_path=vault_path)
        if existing:
            print(f"[record] SKIP: Note already exists → {existing}")
            return

    # 2. Classify
    print("[record] Classifying paper...")
    meta.paper_type = classify_paper(meta)
    print(f"[record] Type: {meta.paper_type}")

    # 3. Zotero (optional, skip if not configured)
    zotero_key = ""
    if not args.no_zotero:
        try:
            from researchnote.scholar.zotero_client import check_duplicate, add_paper

            dup_key = check_duplicate(meta)
            if dup_key:
                print(f"[record] Paper already in Zotero (key: {dup_key}), skipping.")
                zotero_key = dup_key
            else:
                print("[record] Adding to Zotero...")
                collection_name = f"ResearchNote/{meta.paper_type}"
                zotero_key = add_paper(meta, collection_name=collection_name)
                print(f"[record] Zotero key: {zotero_key}")
        except RuntimeError as e:
            print(f"[record] Zotero skipped: {e}", file=sys.stderr)
        except ImportError:
            print("[record] Zotero skipped: pyzotero not installed. Run: pip install pyzotero", file=sys.stderr)

    # 4. Extract figures from PDF (before LLM call, so captions inform note generation)
    figure_info = []  # [{"id": "fig1", "page": 3, "caption": "..."}, ...]
    fig_paths = {}    # {"fig1": "assets/xxx/fig1_p3.png", ...}
    if not args.no_figures:
        try:
            from researchnote.scholar.figure_extractor import extract_and_save
            from researchnote.config import get_obsidian_vault_path
            vault = args.vault or get_obsidian_vault_path()
            # We need note_stem, but don't have system_name yet.
            # Use a temp stem from metadata; will be finalized after LLM call.
            figure_info, fig_paths = extract_and_save(
                source_url=meta.source_url or meta.pdf_url,
                note_stem="_tmp_figures",
                vault_path=vault,
                paper_type=meta.paper_type,
            )
        except Exception as e:
            print(f"[record] Figure extraction skipped: {e}", file=sys.stderr)

    # 5. Generate reading note (with figure captions for inline placement)
    print("[record] Generating reading note...")
    note = generate_paper_note(meta, figure_captions=figure_info if figure_info else None)
    note.zotero_key = zotero_key

    # 6. Rename figure assets to match final note stem
    if fig_paths:
        from researchnote.config import get_obsidian_vault_path
        from pathlib import Path
        vault = args.vault or get_obsidian_vault_path()
        final_stem = get_note_stem(note)
        paper_dir = Path(vault) / f"Papers-{note.paper_type}"
        old_dir = paper_dir / "assets" / "_tmp_figures"
        new_dir = paper_dir / "assets" / final_stem
        if old_dir.exists() and str(old_dir) != str(new_dir):
            new_dir.parent.mkdir(parents=True, exist_ok=True)
            if new_dir.exists():
                import shutil
                shutil.rmtree(new_dir)
            old_dir.rename(new_dir)
            # Update paths
            fig_paths = {fid: p.replace("_tmp_figures", final_stem) for fid, p in fig_paths.items()}

    # 7. Write to Obsidian
    fig_captions = {f["id"]: f["caption"] for f in figure_info} if figure_info else {}
    vault_path = args.vault if args.vault else None
    filepath = write_paper_note(note, vault_path=vault_path, fig_paths=fig_paths, fig_captions=fig_captions)
    print(f"[record] Note saved to: {filepath}")

    # 8. Index into RAG (best-effort)
    try:
        from researchnote.tools.rag import index_paper_note
        count = index_paper_note(filepath)
        if count:
            print(f"[record] Indexed {count} chunks into RAG")
    except Exception:
        pass

    print("\n========================================")
    print(f"  Title:     {meta.title}")
    print(f"  Type:      {meta.paper_type}")
    print(f"  Zotero:    {zotero_key or 'skipped'}")
    print(f"  Note:      {filepath}")
    print("========================================")


def cmd_note(args):
    """Create a note from text input, classify as paper note or idea."""
    from researchnote.scholar.note_generator import generate_paper_note, generate_idea_note
    from researchnote.scholar.obsidian_writer import write_paper_note, write_idea_note
    from researchnote.models import PaperMetadata

    if args.browser:
        from researchnote import config
        config.set_use_browser_llm(True)

    # Read input
    if args.input:
        from pathlib import Path
        text = Path(args.input).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        print("Enter your note (Ctrl+D to finish):")
        lines = []
        try:
            while True:
                lines.append(input())
        except EOFError:
            pass
        text = "\n".join(lines)

    if not text.strip():
        print("[note] ERROR: No input provided.", file=sys.stderr)
        sys.exit(1)

    note_type = args.type
    vault_path = args.vault if args.vault else None

    if note_type == "idea" or (note_type == "auto" and _looks_like_idea(text)):
        print("[note] Generating idea note...")
        note = generate_idea_note(text)
        filepath = write_idea_note(note, vault_path=vault_path)
        print(f"[note] Idea note saved to: {filepath}")
    else:
        print("[note] Generating paper note...")
        meta = PaperMetadata(abstract=text)
        note = generate_paper_note(meta)
        filepath = write_paper_note(note, vault_path=vault_path)
        print(f"[note] Paper note saved to: {filepath}")

    # Index into RAG (best-effort)
    try:
        from researchnote.tools.rag import index_paper_note
        count = index_paper_note(filepath)
        if count:
            print(f"[note] Indexed {count} chunks into RAG")
    except Exception:
        pass


def _looks_like_idea(text: str) -> bool:
    """Heuristic: if text looks more like a research idea than a paper note."""
    idea_keywords = ["idea", "hypothesis", "what if", "we could", "I think",
                     "proposal", "approach", "想法", "假设", "方案"]
    text_lower = text.lower()
    score = sum(1 for kw in idea_keywords if kw in text_lower)
    return score >= 2


def cmd_init(args):
    """Generate config.yaml template."""
    from pathlib import Path
    from researchnote.config import CONFIG_TEMPLATE

    if args.glob:
        target = Path.home() / ".researchnote" / "config.yaml"
    else:
        target = Path.cwd() / "config.yaml"

    if target.exists() and not args.force:
        print(f"config.yaml already exists at {target}. Use --force to overwrite.")
        sys.exit(1)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(CONFIG_TEMPLATE, encoding="utf-8")
    print(f"Created {target}")
    print("Edit the file to fill in your API keys and paths, then start using ResearchNote.")


def cmd_index(args):
    """Index Obsidian vault into RAG for context retrieval."""
    from researchnote.tools.rag import index_obsidian_vault
    vault_path = args.vault if args.vault else None
    count = index_obsidian_vault(vault_path=vault_path)
    print(f"[index] Done. Indexed {count} document chunks.")


def cmd_browser(args):
    """Manage the persistent browser daemon for ChatGPT."""
    from researchnote.tools.browser_daemon import (
        is_daemon_alive, ensure_daemon_running, stop_daemon, read_daemon_info,
        daemon_new_session,
    )

    action = args.action

    if action == "start":
        if is_daemon_alive():
            pid, port = read_daemon_info()
            print(f"[browser] Daemon already running (PID {pid}, port {port})")
        else:
            print("[browser] Starting browser daemon...")
            port = ensure_daemon_running()
            pid, _ = read_daemon_info()
            print(f"[browser] Daemon started (PID {pid}, port {port})")
            print("[browser] Browser will stay open until idle timeout or 'researchnote browser stop'")

    elif action == "stop":
        if stop_daemon():
            print("[browser] Daemon stopped.")
        else:
            print("[browser] No daemon running.")

    elif action == "new":
        if daemon_new_session():
            print("[browser] Session reset. Next command will open a new ChatGPT conversation.")
        else:
            print("[browser] No daemon running. Start one first: researchnote browser start")

    elif action == "status":
        if is_daemon_alive():
            pid, port = read_daemon_info()
            print(f"[browser] Daemon running (PID {pid}, port {port})")
        else:
            print("[browser] Daemon not running.")


def main():
    parser = argparse.ArgumentParser(
        prog="researchnote",
        description="ResearchNote: paper reading notes with LLM — fetch metadata, generate structured notes, manage in Obsidian",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── init ──
    init_p = subparsers.add_parser("init", help="Generate config.yaml template")
    init_p.add_argument("--global", dest="glob", action="store_true",
                        help="Create in ~/.researchnote/ instead of current directory")
    init_p.add_argument("--force", action="store_true", help="Overwrite existing config.yaml")

    # ── record ──
    record_p = subparsers.add_parser("record", help="Record a paper: metadata → Zotero → classify → note → Obsidian")
    record_p.add_argument("url", help="Paper URL (arXiv, Semantic Scholar, DOI, or direct PDF)")
    record_p.add_argument("--force", action="store_true", help="Regenerate note even if it already exists")
    record_p.add_argument("--no-zotero", action="store_true", help="Skip Zotero integration")
    record_p.add_argument("--no-figures", action="store_true", help="Skip figure extraction from PDF")
    record_p.add_argument("--vault", default=None, help="Obsidian vault path (override config)")
    record_p.add_argument("--browser", action="store_true", help="Use browser-based ChatGPT (no API key)")

    # ── note ──
    note_p = subparsers.add_parser("note", help="Create a structured note from text input")
    note_p.add_argument("--type", choices=["paper", "idea", "auto"], default="auto",
                        help="Note type (default: auto-detect)")
    note_p.add_argument("--input", default=None, help="Input file path (alternative to stdin)")
    note_p.add_argument("--vault", default=None, help="Obsidian vault path")
    note_p.add_argument("--browser", action="store_true", help="Use browser-based ChatGPT (no API key)")

    # ── index ──
    index_p = subparsers.add_parser("index", help="Index Obsidian vault into RAG for context retrieval")
    index_p.add_argument("--vault", default=None, help="Obsidian vault path")

    # ── browser ──
    browser_p = subparsers.add_parser("browser", help="Manage persistent browser daemon for ChatGPT")
    browser_p.add_argument("action", choices=["start", "stop", "new", "status"],
                           help="start: launch daemon, stop: kill daemon, new: fresh ChatGPT conversation, status: check if running")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "note":
        cmd_note(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "browser":
        cmd_browser(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
