from issf_rules.textnorm import collapse_spaces, join_lines, strip_controls


def test_strip_controls_removes_bel_but_keeps_tab() -> None:
    assert strip_controls("\x07If an athlete\t") == "If an athlete\t"


def test_collapse_spaces_handles_tabs_and_nbsp() -> None:
    assert collapse_spaces("  6.16.6 \t Appeals\u00a0 ") == "6.16.6 Appeals"


def test_join_lines_uses_single_spaces() -> None:
    assert join_lines(["The athlete must ", " report to the", "range."]) == (
        "The athlete must report to the range."
    )


def test_join_lines_keeps_hyphen_at_line_break() -> None:
    # Dropping the hyphen would change the text ("antidoping"), so it is kept.
    assert join_lines(["constitute anti-", "doping rule violations"]) == (
        "constitute anti-doping rule violations"
    )


def test_join_lines_keeps_space_before_free_standing_dash() -> None:
    assert join_lines(["Rule 6.16 -", "6.16.5.1"]) == "Rule 6.16 - 6.16.5.1"


def test_join_lines_skips_blank_lines() -> None:
    assert join_lines(["", "  ", "text"]) == "text"


def test_join_lines_soft_hyphen_joins_without_space_and_is_kept() -> None:
    assert join_lines(["Written Protest or Ap­", "peal"]) == "Written Protest or Ap­peal"


def test_join_lines_slash_at_line_end_joins_without_space() -> None:
    assert join_lines(["5.5kg (Men/", "Women)"]) == "5.5kg (Men/Women)"
