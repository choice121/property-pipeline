"""Lock-in tests for the Phase 3 hard-reject rules in services/validator.py.

These tests exist specifically so a future refactor can't accidentally let
a row with no rent, no address, or a $50 list price slip back into the
pipeline. If you find yourself relaxing one of these, update the audit doc
and the phased plan first — this file is the contract.

Run from the backend/ directory:
    PYTHONPATH=. python -m pytest tests/test_validator.py -v
"""

from services.validator import HARD_MIN_RENT, validate_and_filter


def _good_row(**overrides):
    base = {
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "monthly_rent": 1500,
        "bedrooms": 2,
        "bathrooms": 1.5,
    }
    base.update(overrides)
    return base


def test_accepts_well_formed_row():
    cleaned, reason = validate_and_filter(_good_row())
    assert reason is None
    assert cleaned is not None
    assert cleaned["monthly_rent"] == 1500


def test_rejects_missing_rent():
    cleaned, reason = validate_and_filter(_good_row(monthly_rent=None))
    assert cleaned is None
    assert reason == "missing_rent"


def test_rejects_rent_below_floor():
    # validate() already nulls values below its own min (currently equal to
    # HARD_MIN_RENT), so the layered behavior is: validate nulls → our filter
    # catches the None as "missing_rent". Either reason is acceptable; the
    # contract is that the row is rejected. "rent_below_min" remains as a
    # backstop in case the two thresholds ever drift apart.
    cleaned, reason = validate_and_filter(_good_row(monthly_rent=HARD_MIN_RENT - 1))
    assert cleaned is None
    assert reason in {"missing_rent", "rent_below_min"}


def test_rejects_missing_address():
    cleaned, reason = validate_and_filter(_good_row(address=None))
    assert cleaned is None
    assert reason == "missing_address"


def test_rejects_blank_address():
    cleaned, reason = validate_and_filter(_good_row(address="   "))
    assert cleaned is None
    assert reason == "missing_address"


def test_address_check_runs_before_rent_check():
    # Both bad — address takes precedence so we surface the most useful reason.
    cleaned, reason = validate_and_filter(_good_row(address=None, monthly_rent=None))
    assert cleaned is None
    assert reason == "missing_address"


def test_validator_crash_returns_named_reason():
    # Pass a non-dict to provoke an exception inside validate(); the wrapper
    # should never let it propagate to the request handler.
    cleaned, reason = validate_and_filter(None)  # type: ignore[arg-type]
    assert cleaned is None
    assert reason == "validator_crash"


def test_rent_at_floor_is_accepted():
    cleaned, reason = validate_and_filter(_good_row(monthly_rent=HARD_MIN_RENT))
    assert reason is None
    assert cleaned is not None
