from branchsync.cli import (
    BranchSyncError,
    build_parser,
    find_missing_commits,
    load_target_subjects,
    matches_prefix,
    normalize_subject,
    parse_source_commits,
    restore_workspace,
)


def test_normalize_subject_removes_case_and_quotes() -> None:
    assert normalize_subject('  Revert "Discount: Fix Total"  ') == "revert discount: fix total"


def test_matches_prefix_accepts_direct_prefix() -> None:
    assert matches_prefix("discount: fix rounding", "discount:")


def test_matches_prefix_accepts_revert_prefix() -> None:
    assert matches_prefix('Revert "discount: fix rounding"', "discount:")


def test_matches_prefix_rejects_other_subjects() -> None:
    assert not matches_prefix("catalog: update price labels", "discount:")


def test_parser_accepts_user_flag() -> None:
    args = build_parser().parse_args(["-p", "discount:", "--user", "alice"])
    assert args.user == "alice"


def test_parse_source_commits_appends_author_flag_when_user_provided(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return ""

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    parse_source_commits("develop", "discount:", "3 weeks ago", user="alice")
    assert "--author=alice" in captured["command"]


def test_parse_source_commits_omits_author_flag_without_user(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return ""

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    parse_source_commits("develop", "discount:", "3 weeks ago")
    assert not any(arg.startswith("--author=") for arg in captured["command"])


def test_load_target_subjects_appends_author_flag_when_user_provided(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return ""

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    load_target_subjects("testing", "discount:", "3 weeks ago", user="alice")
    assert "--author=alice" in captured["command"]


def test_find_missing_commits_forwards_user_filter(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def fake_parse(source_ref: str, prefix: str, since: str, user: str | None = None) -> list:
        seen["source"] = user
        return []

    def fake_load(target_ref: str, prefix: str, since: str, user: str | None = None) -> set:
        seen["target"] = user
        return set()

    monkeypatch.setattr("branchsync.cli.parse_source_commits", fake_parse)
    monkeypatch.setattr("branchsync.cli.load_target_subjects", fake_load)

    find_missing_commits("develop", "testing", "discount:", "3 weeks ago", user="alice")
    assert seen == {"source": "alice", "target": "alice"}


def test_restore_workspace_pops_stash_when_stashed(monkeypatch) -> None:
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "branchsync.cli.run_git",
        lambda command, check=True: commands.append(command),
    )

    restore_workspace("develop", stashed=True)

    assert commands == [
        ["git", "checkout", "develop"],
        ["git", "stash", "pop"],
    ]


def test_restore_workspace_warns_on_checkout_failure(monkeypatch, capsys) -> None:
    def fake_run_git(command: list[str], check: bool = True) -> None:
        raise BranchSyncError("boom")

    monkeypatch.setattr("branchsync.cli.run_git", fake_run_git)

    restore_workspace("develop", stashed=True)

    captured = capsys.readouterr()
    assert "Warning: failed to restore branch:" in captured.err
    assert "Restoring stashed changes..." not in captured.out


def test_restore_workspace_warns_on_stash_pop_failure(monkeypatch, capsys) -> None:
    def fake_run_git(command: list[str], check: bool = True) -> None:
        if command[-1] == "pop":
            raise BranchSyncError("boom")

    monkeypatch.setattr("branchsync.cli.run_git", fake_run_git)

    restore_workspace("develop", stashed=True)

    captured = capsys.readouterr()
    assert "Restoring stashed changes..." in captured.out
    assert "Warning: failed to pop stash:" in captured.err