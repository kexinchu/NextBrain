"""ResearchNote CLI: record, note, index, browser."""
import argparse
import sys


def cmd_record(args):
    """Record a paper: fetch metadata → Zotero → classify → generate note → Obsidian."""
    from nextbrain.scholar.metadata import fetch_metadata
    from nextbrain.scholar.classifier import classify_paper
    from nextbrain.scholar.note_generator import generate_paper_note
    from nextbrain.scholar.obsidian_writer import write_paper_note, get_note_stem, find_existing_note

    if args.browser:
        from nextbrain import config
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
            from nextbrain.scholar.zotero_client import check_duplicate, add_paper

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
            from nextbrain.scholar.figure_extractor import extract_and_save
            from nextbrain.config import get_obsidian_vault_path
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
        from nextbrain.config import get_obsidian_vault_path
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
        from nextbrain.tools.rag import index_paper_note
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
    from nextbrain.scholar.note_generator import generate_paper_note, generate_idea_note
    from nextbrain.scholar.obsidian_writer import write_paper_note, write_idea_note
    from nextbrain.models import PaperMetadata

    if args.browser:
        from nextbrain import config
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
        from nextbrain.tools.rag import index_paper_note
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
    from nextbrain.config import CONFIG_TEMPLATE

    if args.glob:
        target = Path.home() / ".nextbrain" / "config.yaml"
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
    from nextbrain.tools.rag import index_obsidian_vault
    vault_path = args.vault if args.vault else None
    count = index_obsidian_vault(vault_path=vault_path)
    print(f"[index] Done. Indexed {count} document chunks.")


def cmd_workspace_init(args):
    """Scaffold a PhD-oriented Obsidian workspace."""
    from nextbrain.workspace import scaffold_phd_workspace

    vault, changed, skipped = scaffold_phd_workspace(
        vault_path=args.vault,
        force=args.force,
    )
    print(f"[workspace-init] Target vault: {vault}")
    print(f"[workspace-init] Created or updated {len(changed)} paths.")
    for path in changed:
        print(f"  + {path}")
    if skipped:
        print(f"[workspace-init] Skipped {len(skipped)} existing files (use --force to overwrite).")
        for path in skipped:
            print(f"  = {path}")


def cmd_browser(args):
    """Manage the persistent browser daemon for ChatGPT."""
    from nextbrain.tools.browser_daemon import (
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
            print("[browser] Browser will stay open until idle timeout or 'nextbrain browser stop'")

    elif action == "stop":
        if stop_daemon():
            print("[browser] Daemon stopped.")
        else:
            print("[browser] No daemon running.")

    elif action == "new":
        if daemon_new_session():
            print("[browser] Session reset. Next command will open a new ChatGPT conversation.")
        else:
            print("[browser] No daemon running. Start one first: nextbrain browser start")

    elif action == "status":
        if is_daemon_alive():
            pid, port = read_daemon_info()
            print(f"[browser] Daemon running (PID {pid}, port {port})")
        else:
            print("[browser] Daemon not running.")


def cmd_ingest_mail(args):
    """Fetch unprocessed digest emails and apply the second-stage filter."""
    from nextbrain.ingest import mail_client
    from nextbrain.ingest.digest_parser import parse_digest_html
    from nextbrain.ingest.filter import (
        filter_papers, digest_paper_to_note, KEEP, INBOX,
    )
    from nextbrain.scholar.obsidian_writer import write_paper_note

    vault_path = args.vault if args.vault else None
    since = args.since_days

    if args.eml:
        # Local debug path: parse a .eml file directly, no Gmail roundtrip.
        from nextbrain.ingest.digest_parser import parse_eml_file
        digest = parse_eml_file(args.eml)
        digests = [(None, digest)]
    else:
        msg_ids = mail_client.list_digest_messages(since_days=since)
        if not msg_ids:
            print("[ingest-mail] No unprocessed digest messages.")
            return
        print(f"[ingest-mail] Found {len(msg_ids)} digest(s) to process.")
        digests = []
        for mid in msg_ids:
            fetched = mail_client.fetch_message(mid)
            digest = parse_digest_html(fetched.raw_html, subject=fetched.subject,
                                        message_id=mid)
            digests.append((mid, digest))

    n_keep = n_inbox = n_skip = 0
    for mid, digest in digests:
        print(f"\n[ingest-mail] === {digest.subject or digest.digest_date} ===")
        print(f"[ingest-mail] {len(digest.papers)} papers in digest. {digest.stats_text}")
        decisions = filter_papers(digest.papers, vault_path=vault_path,
                                   force_recompute_topics=args.recompute_topics)
        for d in decisions:
            tag = d.action.upper()
            print(f"  [{tag:5}] ({d.reason}) {d.paper.title[:80]}")
            if d.action == KEEP:
                n_keep += 1
            elif d.action == INBOX:
                n_inbox += 1
            else:
                n_skip += 1

            if args.dry_run:
                continue

            if d.action in (KEEP, INBOX):
                note = digest_paper_to_note(d.paper, d.paper_type)
                subfolder = "Inbox" if d.action == INBOX else None
                path = write_paper_note(note, vault_path=vault_path,
                                         subfolder=subfolder)
                print(f"           → {path}")
                # Index pass-through papers into RAG (skip Inbox to avoid noise)
                if d.action == KEEP:
                    try:
                        from nextbrain.tools.rag import index_paper_note
                        index_paper_note(path)
                    except Exception:
                        pass

        if mid and not args.dry_run and not args.keep_unread:
            mail_client.trash_message(mid)
            print(f"  [trash] Email moved to Gmail Trash")

    print(f"\n[ingest-mail] Summary: keep={n_keep} inbox={n_inbox} skip={n_skip}"
          f"{' (dry-run)' if args.dry_run else ''}")


def cmd_topics(args):
    """Show or recompute the auto-inferred active topic set."""
    from nextbrain.topics.active_topics import get_active_topics, compute_active_topics

    vault_path = args.vault if args.vault else None
    if args.recompute:
        at = compute_active_topics(vault_path=vault_path)
        from nextbrain.topics.active_topics import save_cached
        save_cached(at)
    else:
        at = get_active_topics(vault_path=vault_path)

    if not at.weights:
        print("[topics] No active topics inferred — vault appears empty.")
        return
    print(f"[topics] Active topics (top {len(at.weights)}):")
    for label, w in at.weights.items():
        raw = at.raw_counts.get(label, 0.0)
        print(f"  {w:6.3f}  {label}  (raw={raw:.2f})")


def cmd_prune(args):
    """Prune unread/unreferenced/off-topic papers; default dry-run."""
    from nextbrain import prune

    vault_path = args.vault if args.vault else None

    if not args.skip_refresh:
        print("[prune] Refreshing wikilink reference counts and last_opened...")
        stats = prune.refresh_lifecycle(vault_path=vault_path)
        print(f"[prune] {stats['paper_notes']} paper notes scanned; "
              f"refs updated on {stats['updated_refs']}, "
              f"last_opened backfilled on {stats['updated_opened']}.")

    candidates = prune.select_candidates(
        vault_path=vault_path,
        unread_since_days=args.unread_since,
        topic=args.topic,
        inbox_older_than_days=args.inbox_older_than,
        unreferenced_only=args.unreferenced,
    )

    if not candidates:
        print("[prune] No prune candidates.")
        return

    print(f"[prune] {len(candidates)} candidate(s):")
    for c in candidates:
        print(f"  - [{c.reason}] age={c.age_days}d refs={c.times_referenced} "
              f"read={c.read_status or '-':8} {c.path.relative_to(c.path.parents[1])}")

    if not args.apply:
        print("\n[prune] Dry-run only. Re-run with --apply to archive.")
        return

    moved = prune.archive_paths(candidates, vault_path=vault_path)
    print(f"\n[prune] Archived {len(moved)} note(s) to "
          f"<vault>/{__import__('nextbrain.config', fromlist=['x']).get_archive_dir_name()}/")


def cmd_digest(args):
    """Generate a weekly synthesis from recent vault activity."""
    from nextbrain import digest as digest_mod

    if args.browser:
        from nextbrain import config
        config.set_use_browser_llm(True)

    vault_path = args.vault if args.vault else None
    try:
        path = digest_mod.generate_digest(vault_path=vault_path, days=args.days)
    except RuntimeError as e:
        print(f"[digest] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[digest] Synthesis written to: {path}")

    # Index the synthesis itself so it shows up in future RAG retrievals
    try:
        from nextbrain.tools.rag import index_paper_note
        index_paper_note(path)
    except Exception:
        pass


def cmd_stats(args):
    """Print a vault health dashboard."""
    from nextbrain import stats as stats_mod
    s = stats_mod.compute(vault_path=args.vault, refresh_lifecycle=not args.skip_refresh)
    print(stats_mod.render(s, vault_path=args.vault))


def cmd_daily_report(args):
    """Ingest today's emails → if new papers → LLM daily report → send email."""
    from nextbrain import config
    from nextbrain.ingest import mail_client
    from nextbrain.ingest.digest_parser import parse_digest_html
    from nextbrain.ingest.filter import filter_papers, digest_paper_to_note, KEEP, INBOX
    from nextbrain.scholar.obsidian_writer import write_paper_note
    from nextbrain.report import generate_daily_report

    vault_path = args.vault if args.vault else None

    # 1. Ingest today's emails (last 1 day)
    msg_ids = mail_client.list_digest_messages(since_days=1)
    if not msg_ids:
        print("[daily-report] No new digest emails today — skipping.")
        return

    print(f"[daily-report] {len(msg_ids)} email(s) found. Ingesting...")
    for mid in msg_ids:
        fetched = mail_client.fetch_message(mid)
        digest = parse_digest_html(fetched.raw_html, subject=fetched.subject, message_id=mid)
        decisions = filter_papers(digest.papers, vault_path=vault_path)
        for d in decisions:
            if d.action in (KEEP, INBOX):
                note = digest_paper_to_note(d.paper, d.paper_type)
                subfolder = "Inbox" if d.action == INBOX else None
                path = write_paper_note(note, vault_path=vault_path, subfolder=subfolder)
                if d.action == KEEP:
                    try:
                        from nextbrain.tools.rag import index_paper_note
                        index_paper_note(path)
                    except Exception:
                        pass
        if not args.dry_run:
            mail_client.trash_message(mid)
            print(f"  [trash] {mid}")

    # 2. Generate daily report (returns None if no email-ingested papers today)
    report = generate_daily_report(vault_path=vault_path)
    if report is None:
        print("[daily-report] No email-ingested papers found for today — no report sent.")
        return

    # 3. Send report email
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"📚 每日论文日报 — {today}"
    to_addr = config.get_mail_user()

    if args.dry_run:
        print(f"[daily-report] DRY-RUN: would send to {to_addr}")
        print(report[:500] + ("…" if len(report) > 500 else ""))
        return

    mail_client.send_email(to_addr, subject, report)
    print(f"[daily-report] Report sent to {to_addr}")


def cmd_weekly_report(args):
    """Generate weekly synthesis report and send email (always runs)."""
    from nextbrain import config
    from nextbrain.ingest import mail_client
    from nextbrain.report import generate_weekly_report
    from datetime import datetime

    vault_path = args.vault if args.vault else None
    report = generate_weekly_report(vault_path=vault_path)

    today = datetime.now()
    iso_year, iso_week, _ = today.isocalendar()
    subject = f"📊 每周研究周报 — {iso_year} 第{iso_week}周"
    to_addr = config.get_mail_user()

    if args.dry_run:
        print(f"[weekly-report] DRY-RUN: would send to {to_addr}")
        print(report[:500] + ("…" if len(report) > 500 else ""))
        return

    mail_client.send_email(to_addr, subject, report)
    print(f"[weekly-report] Report sent to {to_addr}")


def main():
    parser = argparse.ArgumentParser(
        prog="nextbrain",
        description="ResearchNote: paper reading notes with LLM — fetch metadata, generate structured notes, manage in Obsidian",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── init ──
    init_p = subparsers.add_parser("init", help="Generate config.yaml template")
    init_p.add_argument("--global", dest="glob", action="store_true",
                        help="Create in ~/.nextbrain/ instead of current directory")
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

    # ── workspace-init ──
    workspace_p = subparsers.add_parser(
        "workspace-init",
        help="Scaffold an Obsidian workspace for PhD knowledge management",
    )
    workspace_p.add_argument("--vault", default=None, help="Obsidian vault path")
    workspace_p.add_argument("--force", action="store_true", help="Overwrite existing template files")

    # ── browser ──
    browser_p = subparsers.add_parser("browser", help="Manage persistent browser daemon for ChatGPT")
    browser_p.add_argument("action", choices=["start", "stop", "new", "status"],
                           help="start: launch daemon, stop: kill daemon, new: fresh ChatGPT conversation, status: check if running")

    # ── ingest-mail ──
    ingest_p = subparsers.add_parser(
        "ingest-mail",
        help="Fetch AI Digest emails (Gmail API) and apply the second-stage filter",
    )
    ingest_p.add_argument("--vault", default=None, help="Obsidian vault path")
    ingest_p.add_argument("--since-days", type=int, default=None,
                          help="Only consider emails newer than N days")
    ingest_p.add_argument("--dry-run", action="store_true",
                          help="Print decisions without writing to vault or marking emails processed")
    ingest_p.add_argument("--eml", default=None,
                          help="Parse a local .eml file instead of querying Gmail (debug)")
    ingest_p.add_argument("--recompute-topics", action="store_true",
                          help="Force-recompute active topics before filtering")
    ingest_p.add_argument("--keep-unread", action="store_true",
                          help="Don't mark emails as processed (useful for re-runs)")

    # ── topics ──
    topics_p = subparsers.add_parser(
        "topics",
        help="Show or recompute the auto-inferred active topic set",
    )
    topics_p.add_argument("--vault", default=None, help="Obsidian vault path")
    topics_p.add_argument("--recompute", action="store_true",
                          help="Force recompute (ignore cache)")

    # ── prune ──
    prune_p = subparsers.add_parser(
        "prune",
        help="Archive unread/unreferenced/off-topic notes (dry-run by default)",
    )
    prune_p.add_argument("--vault", default=None, help="Obsidian vault path")
    prune_p.add_argument("--unread-since", type=int, default=None,
                         help="Treat papers untouched for N days as candidates (default from config)")
    prune_p.add_argument("--unreferenced", action="store_true",
                         help="Only flag papers with zero incoming wikilinks")
    prune_p.add_argument("--topic", default=None,
                         help="Prune all papers in Papers-<topic>/ (e.g. Diffusion-Language-Model)")
    prune_p.add_argument("--inbox-older-than", type=int, default=None,
                         help="Also flag Inbox/ items older than N days (default from config)")
    prune_p.add_argument("--apply", action="store_true",
                         help="Actually archive the candidates (default is dry-run)")
    prune_p.add_argument("--skip-refresh", action="store_true",
                         help="Skip recomputing wikilink reference counts before selection")

    # ── digest ──
    digest_p = subparsers.add_parser(
        "digest",
        help="Generate a weekly synthesis from recent papers + ideas (LLM)",
    )
    digest_p.add_argument("--vault", default=None, help="Obsidian vault path")
    digest_p.add_argument("--days", type=int, default=7,
                          help="Window size in days (default 7)")
    digest_p.add_argument("--browser", action="store_true",
                          help="Use browser-based ChatGPT (no API key)")

    # ── stats ──
    stats_p = subparsers.add_parser(
        "stats",
        help="Print a vault health dashboard (no LLM)",
    )
    stats_p.add_argument("--vault", default=None, help="Obsidian vault path")
    stats_p.add_argument("--skip-refresh", action="store_true",
                         help="Skip recomputing wikilink counts before reporting")

    # ── daily-report ──
    daily_p = subparsers.add_parser(
        "daily-report",
        help="Ingest today's emails → LLM daily report → send email (Mon–Sat)",
    )
    daily_p.add_argument("--vault", default=None, help="Obsidian vault path")
    daily_p.add_argument("--dry-run", action="store_true",
                         help="Print report without sending email or trashing messages")

    # ── weekly-report ──
    weekly_p = subparsers.add_parser(
        "weekly-report",
        help="Generate weekly synthesis report and send email (Sunday)",
    )
    weekly_p.add_argument("--vault", default=None, help="Obsidian vault path")
    weekly_p.add_argument("--dry-run", action="store_true",
                          help="Print report without sending email")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "note":
        cmd_note(args)
    elif args.command == "index":
        cmd_index(args)
    elif args.command == "workspace-init":
        cmd_workspace_init(args)
    elif args.command == "browser":
        cmd_browser(args)
    elif args.command == "ingest-mail":
        cmd_ingest_mail(args)
    elif args.command == "topics":
        cmd_topics(args)
    elif args.command == "prune":
        cmd_prune(args)
    elif args.command == "digest":
        cmd_digest(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "daily-report":
        cmd_daily_report(args)
    elif args.command == "weekly-report":
        cmd_weekly_report(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
