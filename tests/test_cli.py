from branchsync.cli import (
    BranchSyncError,
    build_parser,
    find_missing_commits,
    load_target_subjects,
    matches_keyword,
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


def test_matches_keyword_accepts_contained_keyword() -> None:
    assert matches_keyword("discount: fix rounding", "rounding")
    assert matches_keyword("discount: fix rounding", "ROUNDING")
    assert matches_keyword('Revert "discount: fix rounding"', "rounding")
    assert matches_keyword("catalog: update price labels", "update price")


def test_matches_keyword_rejects_missing_keyword() -> None:
    assert not matches_keyword("catalog: update price labels", "rounding")
    assert not matches_keyword("catalog: update price labels", "")


def test_parser_prefix_is_optional() -> None:
    args = build_parser().parse_args([])
    assert args.prefix is None
    assert args.keyword is None


def test_parser_accepts_keyword_flag() -> None:
    args = build_parser().parse_args(["--keyword", "rounding"])
    assert args.keyword == "rounding"
    assert args.prefix is None

    args_short = build_parser().parse_args(["-k", "rounding"])
    assert args_short.keyword == "rounding"


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


def test_parse_source_commits_appends_keyword_grep(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return ""

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    parse_source_commits("develop", keyword="rounding")
    assert "--grep=rounding" in captured["command"]
    assert "-i" in captured["command"]


def test_parse_source_commits_without_prefix_or_keyword(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return ""

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    parse_source_commits("develop")
    assert not any(arg.startswith("--grep=") for arg in captured["command"])


def test_parse_source_commits_filters_by_keyword(monkeypatch) -> None:
    fake_output = (
        "sha1|1000|2026-07-01|feat: discount rounding\n"
        "sha2|2000|2026-07-02|feat: unrelated update\n"
    )
    monkeypatch.setattr("branchsync.cli.git_output", lambda command: fake_output)

    commits = parse_source_commits("develop", keyword="rounding")
    assert len(commits) == 1
    assert commits[0].sha == "sha1"
    assert commits[0].subject == "feat: discount rounding"


def test_parse_source_commits_with_both_prefix_and_keyword(monkeypatch) -> None:
    fake_output = (
        "sha1|1000|2026-07-01|discount: fix voucher rounding\n"
        "sha2|2000|2026-07-02|discount: clamp negative totals\n"
        "sha3|3000|2026-07-03|catalog: fix voucher rounding\n"
    )
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return fake_output

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    commits = parse_source_commits("develop", prefix="discount:", keyword="rounding")
    assert "--all-match" in captured["command"]
    assert "--grep=discount:" in captured["command"]
    assert "--grep=rounding" in captured["command"]
    assert len(commits) == 1
    assert commits[0].sha == "sha1"


def test_load_target_subjects_appends_keyword_grep(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}

    def fake_git_output(command: list[str]) -> str:
        captured["command"] = command
        return "feat: fix voucher rounding\n"

    monkeypatch.setattr("branchsync.cli.git_output", fake_git_output)
    subjects = load_target_subjects("testing", keyword="rounding")
    assert "--grep=rounding" in captured["command"]
    assert "feat: fix voucher rounding" in subjects


def test_find_missing_commits_forwards_keyword_filter(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def fake_parse(source_ref: str, prefix: str | None = None, since: str = "3 weeks ago", user: str | None = None, keyword: str | None = None) -> list:
        seen["source_kw"] = keyword
        return []

    def fake_load(target_ref: str, prefix: str | None = None, since: str = "3 weeks ago", user: str | None = None, keyword: str | None = None) -> set:
        seen["target_kw"] = keyword
        return set()

    monkeypatch.setattr("branchsync.cli.parse_source_commits", fake_parse)
    monkeypatch.setattr("branchsync.cli.load_target_subjects", fake_load)

    find_missing_commits("develop", "testing", keyword="rounding")
    assert seen == {"source_kw": "rounding", "target_kw": "rounding"}