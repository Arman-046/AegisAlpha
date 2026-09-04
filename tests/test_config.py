import pytest
from pydantic import ValidationError
from config.settings import Settings

def test_valid_settings():
    # Should not raise any errors
    s = Settings(
        APCA_API_KEY_ID="test_key",
        APCA_API_SECRET_KEY="test_secret",
        GROQ_API_KEY="test_groq",
        PAPER=True,
        MAX_RISK_PERCENT=0.02,
        BASE_MIN_CONFIDENCE=0.65,
        MAX_OPEN_POSITIONS=5,
        MIN_DTE=14,
        MAX_DTE=35,
        MAX_SLIPPAGE_PERCENT=0.02
    )
    assert s.PAPER is True
    assert s.MAX_RISK_PERCENT == 0.02

def test_invalid_paper_trading():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APCA_API_KEY_ID="test",
            APCA_API_SECRET_KEY="test",
            GEMINI_API_KEY="test",
            PAPER=False  # Should fail
        )
    assert "PAPER must be True" in str(exc_info.value)

def test_negative_risk_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APCA_API_KEY_ID="test",
            APCA_API_SECRET_KEY="test",
            GEMINI_API_KEY="test",
            MAX_RISK_PERCENT=-0.01
        )
    assert "MAX_RISK_PERCENT must be > 0 and <= 0.05" in str(exc_info.value)

def test_excessive_risk_rejected():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APCA_API_KEY_ID="test",
            APCA_API_SECRET_KEY="test",
            GEMINI_API_KEY="test",
            MAX_RISK_PERCENT=0.06 # Over hard cap of 5%
        )
    assert "MAX_RISK_PERCENT must be > 0 and <= 0.05" in str(exc_info.value)

def test_out_of_bounds_confidence():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APCA_API_KEY_ID="test",
            APCA_API_SECRET_KEY="test",
            GEMINI_API_KEY="test",
            BASE_MIN_CONFIDENCE=1.5 # Invalid
        )
    assert "BASE_MIN_CONFIDENCE must be between 0 and 1" in str(exc_info.value)

def test_dte_validation():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            APCA_API_KEY_ID="test",
            APCA_API_SECRET_KEY="test",
            GEMINI_API_KEY="test",
            MIN_DTE=30,
            MAX_DTE=10 # Invalid, less than MIN_DTE
        )
    assert "MAX_DTE cannot be less than MIN_DTE" in str(exc_info.value)
