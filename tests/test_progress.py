from tropic_checker.storage import ProgressTracker


def test_merge_reload_infers_checked(tmp_path):
    progress = ProgressTracker(tmp_path)
    remaining = [("a@x.com", "pass1"), ("b@x.com", "pass2")]
    full = [
        ("old@x.com", "gone"),
        ("a@x.com", "pass1"),
        ("b@x.com", "pass2"),
    ]

    merged, skipped, message = progress.merge_reload(full, remaining)
    assert skipped == 1
    assert "Resumed" in message
    assert merged == remaining
    assert progress.checked_count() == 1


def test_filter_unchecked(tmp_path):
    progress = ProgressTracker(tmp_path)
    progress.mark_checked("done@x.com", "pw", success=False)

    combos = [("done@x.com", "pw"), ("new@x.com", "pw2")]
    filtered, skipped = progress.filter_unchecked(combos)
    assert skipped == 1
    assert filtered == [("new@x.com", "pw2")]
