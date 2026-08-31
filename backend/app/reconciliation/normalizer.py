from datetime import datetime
from decimal import Decimal, InvalidOperation
import re


def normalize_amount(value) -> Decimal:
    """
    Normalize monetary values into a consistent Decimal representation.

    Examples:
        "₹1,234.50" -> Decimal("1234.50")
        "$1,234.50" -> Decimal("1234.50")
        "1234.50"   -> Decimal("1234.50")
    """

    if value is None:
        raise ValueError("Amount cannot be None")

    text = str(value).strip()

    if not text:
        raise ValueError("Amount cannot be empty")

    # Remove common currency symbols and thousands separators.
    text = re.sub(r"[₹$€£]", "", text)
    text = text.replace(",", "").strip()

    # Handle accounting-style negative values: (123.45)
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"

    try:
        return Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value}") from exc


def normalize_date(value) -> str:
    """
    Normalize supported date formats to YYYY-MM-DD.

    Examples:
        2026-08-24 -> 2026-08-24
        24/08/2026 -> 2026-08-24
        24-08-2026 -> 2026-08-24
        08/24/2026 -> 2026-08-24
    """

    if value is None:
        raise ValueError("Date cannot be None")

    text = str(value).strip()

    if not text:
        raise ValueError("Date cannot be empty")

    formats = (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
        "%Y.%m.%d",
    )

    for date_format in formats:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            continue

    raise ValueError(f"Unsupported date format: {value}")


def normalize_reference(value) -> str:
    """
    Normalize transaction references into a canonical token.

    Examples:
        SET-441       -> SET441
        SET_441       -> SET441
        RZP SET-441   -> SET441
        RZP/SET-441   -> SET441
    """

    if value is None:
        raise ValueError("Reference cannot be None")

    text = str(value).strip().upper()

    if not text:
        raise ValueError("Reference cannot be empty")

    # Remove known prefixes when they appear at the beginning.
    text = re.sub(r"^RZP[\s/_-]*", "", text)

    # Remove separators and whitespace.
    text = re.sub(r"[^A-Z0-9]", "", text)

    if not text:
        raise ValueError(f"Invalid reference: {value}")

    return text
