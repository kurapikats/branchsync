from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass


class BranchSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class Commit:
    sha: str
    timestamp: int
    date: str
    subject: str


def run_git(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise BranchSyncError(
            f"Command failed: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def git_output(command: list[str], check: bool = True) -> str:
    return run_git(command, check=check).stdout.strip()


def ref_exists(ref_name: str) -> bool:
    return run_git(["git", "rev-parse", "--verify", "--quiet", ref_name], check=False).returncode == 0


def resolve_branch_ref(branch_name: str) -> str:
    remote_ref = f"origin/{branch_name}"
    if ref_exists(remote_ref):
        return remote_ref
    if ref_exists(branch_name):
        return branch_name
    raise BranchSyncError(f"Branch not found locally or on origin: {branch_name}")


def normalize_subject(subject: str) -> str:
    return subject.strip().lower().replace('"', "").replace("'", "")


def matches_prefix(subject: str, prefix: str) -> bool:
    normalized_subject = subject.strip().lower()
    normalized_prefix = prefix.strip().lower()
    return normalized_subject.startswith(normalized_prefix) or normalized_subject.startswith(
        f'revert "{normalized_prefix}'
    )


def matches_keyword(subject: str, keyword: str) -> bool:
    normalized_subject = subject.strip().lower()
    normalized_keyword = keyword.strip().lower()
    if not normalized_keyword:
        return False
    if normalized_keyword in normalized_subject:
        return True
    return normalize_subject(keyword) in normalize_subject(subject)


def parse_source_commits(
    source_ref: str,
    prefix: str | None = None,
    since: str = "3 weeks ago",
    user: str | None = None,
    keyword: str | None = None,
) -> list[Commit]:
    cmd = [
        "git",
        "log",
        source_ref,
    ]
    if prefix:
        cmd.extend([f"--grep={prefix}", "-i"])
    if keyword:
        cmd.extend([f"--grep={keyword}", "-i"])
    if prefix and keyword:
        cmd.append("--all-match")
    cmd.extend([
        f"--since={since}",
        "--format=%H|%ct|%ad|%s",
        "--date=short",
    ])
    if user:
        cmd.append(f"--author={user}")
    output = git_output(cmd)
    commits: list[Commit] = []
    if not output:
        return commits

    for line in output.splitlines():
        parts = line.split("|", 3)
        if len(parts) != 4:
            continue
        sha, unix_time, commit_date, subject = [item.strip() for item in parts]
        if prefix and not matches_prefix(subject, prefix):
            continue
        if keyword and not matches_keyword(subject, keyword):
            continue
        try:
            timestamp = int(unix_time)
        except ValueError as error:
            raise BranchSyncError(f"Failed to parse timestamp '{unix_time}': {error}") from error
        commits.append(
            Commit(
                sha=sha,
                timestamp=timestamp,
                date=commit_date,
                subject=subject,
            )
        )
    return commits


def load_target_subjects(
    target_ref: str,
    prefix: str | None = None,
    since: str = "3 weeks ago",
    user: str | None = None,
    keyword: str | None = None,
) -> set[str]:
    cmd = [
        "git",
        "log",
        target_ref,
    ]
    if prefix:
        cmd.extend([f"--grep={prefix}", "-i"])
    if keyword:
        cmd.extend([f"--grep={keyword}", "-i"])
    if prefix and keyword:
        cmd.append("--all-match")
    cmd.extend([
        f"--since={since}",
        "--format=%s",
    ])
    if user:
        cmd.append(f"--author={user}")
    output = git_output(cmd)
    if not output:
        return set()
    return {normalize_subject(line) for line in output.splitlines() if line.strip()}


def find_missing_commits(
    source_ref: str,
    target_ref: str,
    prefix: str | None = None,
    since: str = "3 weeks ago",
    user: str | None = None,
    keyword: str | None = None,
) -> list[Commit]:
    extra_kwargs = {}
    if keyword is not None:
        extra_kwargs["keyword"] = keyword
    source_commits = parse_source_commits(source_ref, prefix, since, user=user, **extra_kwargs)
    target_subjects = load_target_subjects(target_ref, prefix, since, user=user, **extra_kwargs)
    missing_commits = [commit for commit in source_commits if normalize_subject(commit.subject) not in target_subjects]
    return sorted(missing_commits, key=lambda commit: commit.timestamp)


def print_missing_commits(commits: list[Commit]) -> None:
    print(f"\nFound {len(commits)} unmerged commit(s):")
    print("-" * 90)
    for commit in commits:
        print(f"{commit.date} | {commit.sha[:12]} | {commit.subject}")
    print("-" * 90)


def prompt_yes_no(message: str) -> bool:
    answer = input(message).strip().lower()
    return answer in {"y", "yes"}


def current_branch() -> str:
    return git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def has_uncommitted_changes() -> bool:
    return bool(git_output(["git", "status", "--porcelain"]))


def stash_changes() -> bool:
    if not has_uncommitted_changes():
        return False
    print("Stashing uncommitted changes...")
    run_git(["git", "stash", "push", "-u", "-m", "branchsync-auto-stash"])
    return True


def restore_workspace(start_branch: str, stashed: bool) -> None:
    try:
        run_git(["git", "checkout", start_branch])
    except BranchSyncError as error:
        print(f"Warning: failed to restore branch: {error}", file=sys.stderr)
        return
    if stashed:
        print("Restoring stashed changes...")
        try:
            run_git(["git", "stash", "pop"])
        except BranchSyncError as error:
            print(f"Warning: failed to pop stash: {error}", file=sys.stderr)


def checkout_and_update_target(target_branch: str) -> None:
    print(f'Checking out target branch "{target_branch}"...')
    run_git(["git", "checkout", target_branch])
    if git_output(["git", "ls-remote", "--heads", "origin", target_branch]):
        print(f'Pulling latest changes for "{target_branch}"...')
        run_git(["git", "pull", "origin", target_branch])


def cherry_pick_commits(commits: list[Commit], conflict_strategy: str | None) -> None:
    print(f"Cherry-picking {len(commits)} commit(s)...")
    for commit in commits:
        print(f"  -> {commit.sha[:12]} {commit.subject}")
        command = ["git", "cherry-pick"]
        if conflict_strategy == "incoming":
            command.append("-Xtheirs")
        elif conflict_strategy == "current":
            command.append("-Xours")
        command.append(commit.sha)

        result = run_git(command, check=False)
        if result.returncode == 0:
            continue

        status = git_output(["git", "status"], check=False)
        if "all conflicts fixed" in status:
            print("  -> Empty cherry-pick detected, skipping.")
            run_git(["git", "cherry-pick", "--skip"], check=False)
            continue

        run_git(["git", "cherry-pick", "--abort"], check=False)
        raise BranchSyncError(
            f"Cherry-pick failed for {commit.sha[:12]}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="branchsync",
        description="List and optionally cherry-pick unmerged commits from a source branch to a target branch.",
    )
    parser.add_argument("-s", "--source", default="develop", help="Source branch")
    parser.add_argument("-t", "--target", default="testing", help="Target branch")
    parser.add_argument("-d", "--since", default="3 weeks ago", help="Timeframe for the Git log search")
    parser.add_argument("-p", "--prefix", help="Commit prefix filter, for example 'discount:'")
    parser.add_argument("-k", "--keyword", help="Commit keyword filter, for example 'discount'")
    parser.add_argument("-U", "--user", help="Filter commits by committer username")
    parser.add_argument("-c", "--cherry-pick", action="store_true", help="Cherry-pick missing commits to the target branch")
    parser.add_argument("-u", "--push", action="store_true", help="Push the target branch after cherry-picking")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")
    parser.add_argument(
        "-x",
        "--conflict",
        choices=["incoming", "current"],
        help="Conflict strategy: incoming prefers picked changes, current prefers target branch changes",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        print("Fetching origin...")
        run_git(["git", "fetch", "origin"])

        source_ref = resolve_branch_ref(args.source)
        target_ref = resolve_branch_ref(args.target)
        missing_commits = find_missing_commits(
            source_ref,
            target_ref,
            args.prefix,
            args.since,
            user=args.user,
            keyword=args.keyword,
        )

        if not missing_commits:
            filter_desc = "filters"
            if args.prefix and not args.keyword:
                filter_desc = "prefix"
            elif args.keyword and not args.prefix:
                filter_desc = "keyword"
            print(f"No unmerged commits found for the selected {filter_desc} and timeframe.")
            return 0

        print_missing_commits(missing_commits)

        if not args.cherry_pick:
            print("\nRun with --cherry-pick to apply these commits.")
            return 0

        if not args.yes and not prompt_yes_no(
            f'\nCherry-pick these {len(missing_commits)} commit(s) to "{args.target}"? [y/N]: '
        ):
            print("Aborted.")
            return 0

        start_branch = current_branch()
        stashed = False

        try:
            stashed = stash_changes()
            checkout_and_update_target(args.target)
            cherry_pick_commits(missing_commits, args.conflict)
            print("Cherry-pick completed successfully.")

            if args.push:
                if args.yes or prompt_yes_no(f'Push "{args.target}" to origin? [y/N]: '):
                    print(f'Pushing "{args.target}" to origin...')
                    run_git(["git", "push", "origin", args.target])
                    print("Push completed successfully.")
        finally:
            restore_workspace(start_branch, stashed)

        return 0
    except BranchSyncError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

