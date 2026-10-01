"""Vietnamese text normalization and n-gram extraction for search projection (T026)."""

import re
import unicodedata

# Maximum length for bounded n-gram expansion
DEFAULT_MIN_N = 1
DEFAULT_MAX_N = 3


def normalize_exact(text: str) -> str:
    """Normalize text using Unicode NFC, lowercase/casefold, and space collapsing.

    Preserves Vietnamese tone and vowel diacritics.
    Deterministic, side-effect free, and locale-stable.
    """
    if not text:
        return ""
    # NFC normalization ensures precomposed characters and consistent combining marks
    nfc = unicodedata.normalize("NFC", text.strip().casefold())
    return re.sub(r"\s+", " ", nfc)


def normalize_accent_fold(text: str) -> str:
    """Normalize text by folding Vietnamese diacritics and tones to base ASCII characters.

    Handles:
    - Precomposed and decomposed combining-mark vowels (a, ă, â, e, ê, i, o, ô, ơ, u, ư, y)
    - Tone marks (acute, grave, hook, tilde, dot below)
    - Vietnamese đ and Đ -> d
    - Case folding and space collapsing

    Deterministic, side-effect free, and locale-stable.
    """
    if not text:
        return ""
    # Casefold first
    folded = text.strip().casefold()
    # Explicitly map đ/Đ to d (in casefold, Đ becomes đ, so mapping đ is sufficient,
    # but mapping both guarantees safety against uncasefolded inputs)
    folded = folded.replace("\u0111", "d").replace("\u0110", "d")
    # Decompose into NFD to separate base characters from combining diacritics
    nfd = unicodedata.normalize("NFD", folded)
    # Strip non-spacing combining marks (category 'Mn')
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    # Return to NFC and collapse whitespace
    nfc = unicodedata.normalize("NFC", stripped)
    return re.sub(r"\s+", " ", nfc)


def generate_ngrams(text: str, min_n: int = DEFAULT_MIN_N, max_n: int = DEFAULT_MAX_N) -> set[str]:
    """Generate character n-grams from min_n to max_n for substring matching.

    Bounded generation avoids combinatorial expansion:
    For text of length L, total n-grams <= (max_n - min_n + 1) * L.
    """
    if not text or min_n < 1 or max_n < min_n:
        return set()
    length = len(text)
    ngrams: set[str] = set()
    upper_bound = min(max_n, length)
    for n in range(min_n, upper_bound + 1):
        for i in range(length - n + 1):
            ngrams.add(text[i : i + n])
    return ngrams


def escape_like_meta(text: str) -> str:
    r"""Escape SQL LIKE metacharacters (%, _, and \) for parameterized literal matching."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
