import pytest

# Tests written in M1 against the contracts in app/domain/rules.py. They are strict expected
# failures that only count as xfail while the rule raises NotImplementedError:
# - if the rule is implemented wrongly, the test FAILS (the assertion error is not masked);
# - once the rule is implemented correctly, the test XPASSes, which strict mode reports as a
#   failure, so the marker has to be removed in M2 and cannot be forgotten.
awaiting_m2 = pytest.mark.xfail(
    raises=NotImplementedError, strict=True, reason="rule is implemented in M2"
)
