"""Ratios, percentage changes, averages and the overdue aging bands."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.analytics import (
    AGING_BANDS,
    BLOCKING_DAYS,
    aging_band_index,
    average_1dp,
    average_paise,
    blocks_member,
    change_pct,
    ratio_pct,
)
from app.domain.enums import BlockReason, MemberStatus
from app.domain.rules import late_fee_days, member_block_reasons


@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [
        (0, 0, None),
        (5, 0, None),
        (0, 5, 0.0),
        (1, 1, 100.0),
        (3, 2, 150.0),
        (1, 3, 33.3),
        (2, 3, 66.7),
        (1, 6, 16.7),
        (5, 6, 83.3),
        (1, 8, 12.5),
        (1, 16, 6.3),  # 6.25 rounds half up
        (3, 16, 18.8),  # 18.75 rounds half up
        (1, 1000, 0.1),
        (1, 10000, 0.0),
    ],
)
def test_ratio_pct_has_one_decimal_rounded_half_up_and_none_without_a_denominator(
    numerator, denominator, expected
):
    assert ratio_pct(numerator, denominator) == expected


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (5, 0, None),
        (0, 0, None),
        (110, 100, 10.0),
        (90, 100, -10.0),
        (100, 100, 0.0),
        (0, 5, -100.0),
        (4, 3, 33.3),
        (2, 3, -33.3),
        (1, 3, -66.7),
        (17, 16, 6.3),  # +6.25 rounds away from zero
        (1, 16, -93.8),  # -93.75 rounds away from zero
        (300, 100, 200.0),
    ],
)
def test_change_pct_is_signed_and_none_when_there_was_nothing_before(current, previous, expected):
    assert change_pct(current, previous) == expected


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [(0, 0, None), (10, 4, 2.5), (1, 3, 0.3), (2, 3, 0.7), (7, 2, 3.5), (5, 8, 0.6), (9, 1, 9.0)],
)
def test_average_1dp(total, count, expected):
    assert average_1dp(total, count) == expected


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [(0, 0, None), (1000, 3, 333), (2000, 3, 667), (5, 2, 3), (7, 2, 4), (0, 4, 0), (1500, 2, 750)],
)
def test_average_paise_is_whole_paise_rounded_half_up(total, count, expected):
    result = average_paise(total, count)
    assert result == expected
    assert result is None or type(result) is int


# --- overdue aging -----------------------------------------------------------------------------


def test_the_bands_are_contiguous_start_at_one_day_and_the_last_is_open_ended():
    assert AGING_BANDS[0].min_days == 1
    for earlier, later in zip(AGING_BANDS, AGING_BANDS[1:], strict=False):
        assert earlier.max_days is not None
        assert later.min_days == earlier.max_days + 1
    assert AGING_BANDS[-1].max_days is None
    assert [band.label for band in AGING_BANDS] == ["1–3 days", "4–7 days", "8–14 days", "15+ days"]


@pytest.mark.parametrize(
    ("days", "band"),
    [
        (1, 0),
        (2, 0),
        (3, 0),
        (4, 1),
        (7, 1),
        (8, 2),
        (14, 2),
        (15, 3),
        (16, 3),
        (365, 3),
        (10_000, 3),
    ],
)
def test_a_loan_falls_in_the_band_for_its_rounded_up_days_overdue(days, band):
    assert aging_band_index(days) == band


@pytest.mark.parametrize("days", [0, -1])
def test_a_loan_that_is_not_overdue_has_no_band(days):
    with pytest.raises(ValueError):
        aging_band_index(days)


def test_the_last_band_starts_exactly_where_a_loan_starts_to_block_its_member():
    assert BLOCKING_DAYS == 14
    assert AGING_BANDS[-1].min_days == BLOCKING_DAYS + 1
    assert not blocks_member(BLOCKING_DAYS)
    assert blocks_member(BLOCKING_DAYS + 1)


def test_blocking_agrees_with_the_member_eligibility_rule_at_the_exact_boundary():
    due = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
    exactly_14_days = due + timedelta(days=14)
    one_second_more = exactly_14_days + timedelta(seconds=1)

    for moment, blocked in [(exactly_14_days, False), (one_second_more, True)]:
        reasons = member_block_reasons(
            status=MemberStatus.ACTIVE, balance_paise=0, longest_overdue=moment - due
        )
        assert (BlockReason.LONG_OVERDUE in reasons) is blocked
        assert blocks_member(late_fee_days(due, moment)) is blocked
