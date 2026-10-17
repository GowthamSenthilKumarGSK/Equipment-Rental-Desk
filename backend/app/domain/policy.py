"""The numbers from Problem 1. All money is integer paise (1 rupee = 100 paise); never floats."""

from datetime import timedelta

RESERVATION_HOLD = timedelta(hours=48)
LOAN_PERIOD = timedelta(days=7)

LATE_FEE_PER_DAY_PAISE = 10 * 100  # ₹10 per started day
LATE_FEE_CAP_PAISE = 200 * 100  # ₹200 per loan

MAX_ACTIVE_LOANS = 3
# A balance strictly greater than this blocks the member (exactly ₹100 is still allowed).
BLOCKING_BALANCE_PAISE = 100 * 100
# A loan overdue by strictly more than this blocks the member (exactly 14 days is allowed).
BLOCKING_OVERDUE = timedelta(days=14)
