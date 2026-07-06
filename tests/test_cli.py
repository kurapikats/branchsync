from branchsync.cli import matches_prefix, normalize_subject


def test_normalize_subject_removes_case_and_quotes() -> None:
    assert normalize_subject('  Revert "Discount: Fix Total"  ') == "revert discount: fix total"


def test_matches_prefix_accepts_direct_prefix() -> None:
    assert matches_prefix("discount: fix rounding", "discount:")


def test_matches_prefix_accepts_revert_prefix() -> None:
    assert matches_prefix('Revert "discount: fix rounding"', "discount:")


def test_matches_prefix_rejects_other_subjects() -> None:
    assert not matches_prefix("catalog: update price labels", "discount:")

