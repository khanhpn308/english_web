"""Lossless Markdown parser for academic vocabulary daily logs (T020).

Pure parser boundary: no filesystem access, no SQLite, no network, no AI, no global mutable state.
"""

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

# Pinned constants
MAX_SOURCE_SIZE_BYTES = 8 * 1024 * 1024  # 8 MiB (8,388,608 bytes)
TIMEZONE = "Asia/Bangkok"

# Deterministic POS mapping table
VALID_POS_MAP: dict[str, str] = {
    "noun": "NOUN",
    "n": "NOUN",
    "n.": "NOUN",
    "verb": "VERB",
    "v": "VERB",
    "v.": "VERB",
    "adjective": "ADJECTIVE",
    "adj": "ADJECTIVE",
    "adj.": "ADJECTIVE",
    "adverb": "ADVERB",
    "adv": "ADVERB",
    "adv.": "ADVERB",
    "pronoun": "PRONOUN",
    "pron": "PRONOUN",
    "pron.": "PRONOUN",
    "preposition": "PREPOSITION",
    "prep": "PREPOSITION",
    "prep.": "PREPOSITION",
    "conjunction": "CONJUNCTION",
    "conj": "CONJUNCTION",
    "conj.": "CONJUNCTION",
    "interjection": "INTERJECTION",
    "interj": "INTERJECTION",
    "interj.": "INTERJECTION",
    "determiner": "DETERMINER",
    "det": "DETERMINER",
    "det.": "DETERMINER",
}


def normalize_lemma(lemma: str) -> str:
    """Normalize lemma using Unicode NFC, strip whitespace, lowercase, and collapse spaces."""
    normalized = unicodedata.normalize("NFC", lemma.strip().lower())
    return re.sub(r"\s+", " ", normalized)


def parse_markdown_link(text: str) -> tuple[str, str | None]:
    """Extract display text and optional URL from markdown link like [text](url)."""
    text = text.strip()
    if not (text.startswith("[") and ")" in text):
        return text, None
    close_bracket = text.find("](")
    if close_bracket == -1:
        return text, None
    if text.endswith(")"):
        display = text[1:close_bracket].strip()
        url = text[close_bracket + 2 : -1].strip()
        return display, url
    match = re.search(r"\[([^\]]+)\]\((.*)\)", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return text, None


def parse_table_row(line: str) -> list[str]:
    """Parse a Markdown table row into cells, splitting by unescaped pipe."""
    trimmed = line.strip()
    if trimmed.startswith("|"):
        trimmed = trimmed[1:]
    if trimmed.endswith("|"):
        trimmed = trimmed[:-1]
    parts = re.split(r"(?<!\\)\|", trimmed)
    return [p.strip().replace(r"\|", "|") for p in parts]


def is_table_separator(line: str) -> bool:
    """Check if a line is a Markdown table separator line like |---|---|."""
    trimmed = line.strip()
    if not trimmed or "|" not in trimmed:
        return False
    cells = parse_table_row(trimmed)
    if not cells:
        return False
    return all(re.match(r"^:?-+:?$", c.strip()) is not None for c in cells if c.strip())


@dataclass(frozen=True)
class ParseDiagnostic:
    code: str
    message: str
    line: int | None = None
    column: int | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "field": self.field,
        }


@dataclass(frozen=True)
class QuickLookupItem:
    raw_term: str
    target_lemma: str
    ipa_us: str
    short_meaning: str
    short_example: str
    short_translation: str
    raw_row: str


@dataclass(frozen=True)
class RelatedFormItem:
    lemma: str
    normalized_lemma: str
    parts_of_speech: list[str]
    raw_pos: str
    ipa_us: str | None
    cambridge_url: str | None
    meaning_vi: str
    example_en: str
    example_vi: str
    raw_row: str


@dataclass(frozen=True)
class SemanticForm:
    lemma: str
    normalized_lemma: str
    part_of_speech: str
    is_primary: bool
    family_root: str
    ipa_us: str | None = None
    cambridge_url: str | None = None
    stress: str | None = None
    meanings_vi: list[str] = field(default_factory=list)
    meanings_en: list[str] = field(default_factory=list)
    examples: list[tuple[str, str]] = field(default_factory=list)
    source_date: str = ""
    source_date_legacy: str = ""


@dataclass
class DetailedEntry:
    heading: str
    lemma: str
    normalized_lemma: str
    parts_of_speech: list[str]
    raw_pos: str
    ipa_us: str | None
    stress: str | None
    cambridge_url: str | None
    meanings_text: str = ""
    context_text: str = ""
    example_en: str = ""
    example_vi: str = ""
    related_forms: list[RelatedFormItem] = field(default_factory=list)
    opaque_rows: list[str] = field(default_factory=list)
    opaque_sections: list[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ParsedDocument:
    note_date: str
    note_date_legacy: str
    raw_content: str
    quick_lookups: list[QuickLookupItem] = field(default_factory=list)
    entries: list[DetailedEntry] = field(default_factory=list)
    semantic_forms: list[SemanticForm] = field(default_factory=list)
    opaque_blocks: list[str] = field(default_factory=list)
    diagnostics: list[ParseDiagnostic] = field(default_factory=list)


@dataclass
class ParseResult:
    is_valid: bool
    status: Literal["VALID", "INVALID"]
    document: ParsedDocument | None
    diagnostics: list[ParseDiagnostic]


def _validate_calendar_date(
    day_str: str, month_str: str, year_str: str
) -> tuple[date | None, str | None]:
    """Validate calendar date and return (date_obj, error_message)."""
    try:
        d = int(day_str)
        m = int(month_str)
        y = int(year_str)
        return date(y, m, d), None
    except ValueError as e:
        return None, str(e)


def parse_markdown(content: str, filename: str | None = None) -> ParseResult:
    """Parse Markdown text into a structured, lossless document representation.

    Enforces frozen source constraints:
    - Max size 8 MiB (8,388,608 bytes)
    - Valid DD-MM-YYYY filename and H1 matching
    - Valid calendar date in Asia/Bangkok
    - Deterministic POS mapping and validation
    - Required table structures
    - Preservation of opaque rows, sections, and exact formatting
    """
    raw_bytes = content.encode("utf-8")
    if len(raw_bytes) > MAX_SOURCE_SIZE_BYTES:
        diag = ParseDiagnostic(
            code="PAYLOAD_TOO_LARGE",
            message=(
                f"Source size {len(raw_bytes)} bytes exceeds maximum allowed limit of "
                f"{MAX_SOURCE_SIZE_BYTES} bytes (8 MiB)."
            ),
        )
        return ParseResult(
            is_valid=False,
            status="INVALID",
            document=None,
            diagnostics=[diag],
        )

    diagnostics: list[ParseDiagnostic] = []
    fn_date: date | None = None
    fn_legacy: str | None = None

    if filename is not None:
        basename = os.path.basename(filename)
        fn_match = re.match(r"^(\d{2})-(\d{2})-(\d{4})\.md$", basename)
        if not fn_match:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_FILENAME",
                    message=(
                        f"Filename '{basename}' does not match required format 'DD-MM-YYYY.md'."
                    ),
                    field="filename",
                )
            )
        else:
            fn_day, fn_month, fn_year = fn_match.groups()
            fn_date, err = _validate_calendar_date(fn_day, fn_month, fn_year)
            if fn_date is None:
                diagnostics.append(
                    ParseDiagnostic(
                        code="INVALID_CALENDAR_DATE",
                        message=(
                            f"Filename date '{fn_day}-{fn_month}-{fn_year}' is not a valid "
                            f"calendar date: {err}."
                        ),
                        field="filename",
                    )
                )
            else:
                fn_legacy = f"{fn_day}-{fn_month}-{fn_year}"

    # Parse lines preserving newline terminators
    lines = content.splitlines(keepends=True)

    # Find H1 headings
    h1_indices: list[int] = []
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            h1_indices.append(idx)

    h1_date: date | None = None
    h1_legacy: str = ""
    h1_iso: str = ""

    if not h1_indices:
        diagnostics.append(
            ParseDiagnostic(
                code="MISSING_H1",
                message="Document is missing required top-level heading '# DD-MM-YYYY'.",
            )
        )
    else:
        if len(h1_indices) > 1:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_H1",
                    message="Document has multiple top-level H1 headings.",
                    line=h1_indices[1] + 1,
                )
            )

        h1_line_idx = h1_indices[0]
        h1_line = lines[h1_line_idx].strip()
        h1_match = re.match(r"^#\s+(\d{2})-(\d{2})-(\d{4})$", h1_line)
        if not h1_match:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_H1",
                    message=(
                        f"Top-level heading '{h1_line}' does not match required format "
                        "'# DD-MM-YYYY'."
                    ),
                    line=h1_line_idx + 1,
                )
            )
        else:
            h1_d, h1_m, h1_y = h1_match.groups()
            h1_date, err = _validate_calendar_date(h1_d, h1_m, h1_y)
            if h1_date is None:
                diagnostics.append(
                    ParseDiagnostic(
                        code="INVALID_CALENDAR_DATE",
                        message=(
                            f"H1 date '{h1_d}-{h1_m}-{h1_y}' is not a valid calendar date: {err}."
                        ),
                        line=h1_line_idx + 1,
                    )
                )
            else:
                h1_legacy = f"{h1_d}-{h1_m}-{h1_y}"
                h1_iso = h1_date.isoformat()

                if fn_date is not None and fn_legacy is not None and fn_legacy != h1_legacy:
                    diagnostics.append(
                        ParseDiagnostic(
                            code="DATE_MISMATCH",
                            message=(
                                f"Filename date '{fn_legacy}' does not match H1 date '{h1_legacy}'."
                            ),
                            line=h1_line_idx + 1,
                        )
                    )

    # Find all H2 headings: line index and title
    h2_sections: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        if line.startswith("## "):
            title = line[3:].strip()
            h2_sections.append((idx, title))

    quick_lookups: list[QuickLookupItem] = []
    entries: list[DetailedEntry] = []
    opaque_blocks: list[str] = []

    # Map sections by index range
    section_ranges: list[tuple[int, str, int, int]] = []
    for s_idx, (start_line, title) in enumerate(h2_sections):
        end_line = h2_sections[s_idx + 1][0] if s_idx + 1 < len(h2_sections) else len(lines)
        section_ranges.append((start_line, title, start_line, end_line))

    # Check for Tra cứu nhanh
    ql_range: tuple[int, str, int, int] | None = None
    entry_ranges: list[tuple[int, str, int, int]] = []

    for item in section_ranges:
        _, title, _, _ = item
        if title.lower() == "tra cứu nhanh":
            ql_range = item
        else:
            entry_ranges.append(item)

    if ql_range is None:
        diagnostics.append(
            ParseDiagnostic(
                code="MALFORMED_TABLE",
                message="Document is missing required '## Tra cứu nhanh' section.",
            )
        )
    else:
        # Parse Tra cứu nhanh table
        ql_start, _, _, ql_end = ql_range
        ql_lines = lines[ql_start:ql_end]
        table_lines: list[tuple[int, str]] = []
        for offset, line_str in enumerate(ql_lines):
            abs_idx = ql_start + offset
            if "|" in line_str:
                table_lines.append((abs_idx, line_str))

        if len(table_lines) < 2:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_TABLE",
                    message="Section '## Tra cứu nhanh' is missing required lookup table.",
                    line=ql_start + 1,
                )
            )
        else:
            hdr_idx, hdr_line = table_lines[0]
            _sep_idx, sep_line = table_lines[1]
            hdr_cells = parse_table_row(hdr_line)
            expected_headers = ["Từ/cụm từ", "IPA (US)", "Nghĩa ngắn", "Ví dụ ngắn", "Dịch ví dụ"]

            if len(hdr_cells) != 5 or not is_table_separator(sep_line):
                diagnostics.append(
                    ParseDiagnostic(
                        code="MALFORMED_TABLE",
                        message=(
                            f"Table in '## Tra cứu nhanh' has invalid structure or columns. "
                            f"Expected 5 columns: {expected_headers}, got {len(hdr_cells)}."
                        ),
                        line=hdr_idx + 1,
                    )
                )
            else:
                for row_idx, row_line in table_lines[2:]:
                    cells = parse_table_row(row_line)
                    if len(cells) != 5:
                        diagnostics.append(
                            ParseDiagnostic(
                                code="MALFORMED_TABLE",
                                message=(
                                    f"Row in '## Tra cứu nhanh' has {len(cells)} cells, expected 5."
                                ),
                                line=row_idx + 1,
                            )
                        )
                    else:
                        target_lemma, _ = parse_markdown_link(cells[0])
                        quick_lookups.append(
                            QuickLookupItem(
                                raw_term=cells[0],
                                target_lemma=target_lemma,
                                ipa_us=cells[1],
                                short_meaning=cells[2],
                                short_example=cells[3],
                                short_translation=cells[4],
                                raw_row=row_line,
                            )
                        )

    # Parse detailed entries or opaque H2 blocks
    for _start_idx, title, r_start, r_end in entry_ranges:
        entry_lines = lines[r_start:r_end]
        raw_section_text = "".join(entry_lines)

        # Find H3 subsections inside this entry
        h3_indices: list[tuple[int, str]] = []
        for offset, line_str in enumerate(entry_lines):
            if line_str.startswith("### "):
                h3_title = line_str[4:].strip()
                h3_indices.append((offset, h3_title))

        pre_h3_lines: list[tuple[int, str]]
        if h3_indices:
            first_h3_offset = h3_indices[0][0]
            pre_h3_lines = [(r_start + o, entry_lines[o]) for o in range(first_h3_offset)]
        else:
            pre_h3_lines = [(r_start + o, entry_lines[o]) for o in range(len(entry_lines))]

        # Search for principal table in pre_h3_lines
        principal_table_lines: list[tuple[int, str]] = [
            (idx, line_str) for idx, line_str in pre_h3_lines if "|" in line_str
        ]

        if not principal_table_lines:
            # No principal table: treat as opaque block (e.g. ## Ghi chú tài liệu)
            opaque_blocks.append(raw_section_text)
            continue

        if len(principal_table_lines) < 2:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_TABLE",
                    message=f"Principal table in entry '## {title}' is truncated.",
                    line=principal_table_lines[0][0] + 1,
                )
            )
            continue

        p_hdr_idx, p_hdr_line = principal_table_lines[0]
        p_sep_idx, p_sep_line = principal_table_lines[1]
        p_hdr_cells = parse_table_row(p_hdr_line)
        expected_p_headers = ["Từ/cụm từ", "Từ loại", "IPA (US)", "Trọng âm", "Nguồn"]

        if len(p_hdr_cells) != 5 or not is_table_separator(p_sep_line):
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_TABLE",
                    message=(
                        f"Principal table in entry '## {title}' has invalid structure or columns. "
                        f"Expected 5 columns: {expected_p_headers}, got {len(p_hdr_cells)}."
                    ),
                    line=p_hdr_idx + 1,
                )
            )
            continue

        if len(principal_table_lines) < 3:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_TABLE",
                    message=f"Principal table in entry '## {title}' has no rows.",
                    line=p_sep_idx + 1,
                )
            )
            continue

        p_row_idx, p_row_line = principal_table_lines[2]
        p_cells = parse_table_row(p_row_line)
        if len(p_cells) != 5:
            diagnostics.append(
                ParseDiagnostic(
                    code="MALFORMED_TABLE",
                    message=(
                        f"Principal table row in entry '## {title}' has {len(p_cells)} cells, "
                        "expected 5."
                    ),
                    line=p_row_idx + 1,
                )
            )
            continue

        lemma_cell = p_cells[0].strip()
        raw_pos = p_cells[1].strip()
        ipa_cell = p_cells[2].strip() or None
        stress_cell = p_cells[3].strip() or None
        source_cell = p_cells[4].strip()
        _, cambridge_url = parse_markdown_link(source_cell)

        # Parse and validate POS tokens for primary entry
        if not raw_pos:
            diagnostics.append(
                ParseDiagnostic(
                    code="AMBIGUOUS_POS",
                    message=f"Entry '{lemma_cell}' has empty 'Từ loại'.",
                    line=p_row_idx + 1,
                    field="Từ loại",
                )
            )
            entry_pos_list: list[str] = []
        else:
            raw_tokens = [t.strip() for t in raw_pos.split(",") if t.strip()]
            entry_pos_list = []
            if not raw_tokens:
                diagnostics.append(
                    ParseDiagnostic(
                        code="AMBIGUOUS_POS",
                        message=f"Entry '{lemma_cell}' has empty or invalid 'Từ loại'.",
                        line=p_row_idx + 1,
                        field="Từ loại",
                    )
                )
            for token in raw_tokens:
                canonical = VALID_POS_MAP.get(token.lower())
                if canonical is None:
                    diagnostics.append(
                        ParseDiagnostic(
                            code="AMBIGUOUS_POS",
                            message=(
                                f"Entry '{lemma_cell}' has ambiguous or unrecognized part of "
                                f"speech '{token}'."
                            ),
                            line=p_row_idx + 1,
                            field="Từ loại",
                        )
                    )
                else:
                    if canonical not in entry_pos_list:
                        entry_pos_list.append(canonical)

        # Subsections parsing (Ý nghĩa, Trong ngữ cảnh, Ví dụ, Các dạng liên quan, Opaque)
        meanings_text = ""
        context_text = ""
        example_en = ""
        example_vi = ""
        related_forms: list[RelatedFormItem] = []
        opaque_rows: list[str] = []
        opaque_subsections: list[str] = []

        for h3_idx, (h3_offset, h3_name) in enumerate(h3_indices):
            h3_end_offset = (
                h3_indices[h3_idx + 1][0] if h3_idx + 1 < len(h3_indices) else len(entry_lines)
            )
            sub_lines = entry_lines[h3_offset + 1 : h3_end_offset]
            sub_text = "".join(sub_lines).strip()
            norm_h3_name = h3_name.lower().strip()

            if norm_h3_name == "ý nghĩa":
                meanings_text = sub_text
            elif norm_h3_name == "trong ngữ cảnh":
                context_text = sub_text
            elif norm_h3_name == "ví dụ":
                # Extract English example and Vietnamese translation
                sub_str_lines = [line_str.strip() for line_str in sub_lines if line_str.strip()]
                en_parts: list[str] = []
                for sl in sub_str_lines:
                    if sl.startswith("*Bản dịch:*"):
                        example_vi = sl[len("*Bản dịch:*") :].strip()
                    elif sl.startswith("Bản dịch:"):
                        example_vi = sl[len("Bản dịch:") :].strip()
                    else:
                        en_parts.append(sl)
                example_en = " ".join(en_parts).strip()
            elif norm_h3_name == "các dạng liên quan":
                rf_table_lines: list[tuple[int, str]] = []
                for sub_off, sl in enumerate(sub_lines):
                    abs_l_idx = r_start + h3_offset + 1 + sub_off
                    if "|" in sl:
                        rf_table_lines.append((abs_l_idx, sl))

                if len(rf_table_lines) >= 2:
                    rf_hdr_idx, rf_hdr_line = rf_table_lines[0]
                    _rf_sep_idx, rf_sep_line = rf_table_lines[1]
                    rf_hdr_cells = parse_table_row(rf_hdr_line)
                    if len(rf_hdr_cells) != 6 or not is_table_separator(rf_sep_line):
                        diagnostics.append(
                            ParseDiagnostic(
                                code="MALFORMED_TABLE",
                                message=(
                                    f"Table in '### Các dạng liên quan' of entry '## {title}' "
                                    f"has invalid columns: expected 6, got {len(rf_hdr_cells)}."
                                ),
                                line=rf_hdr_idx + 1,
                            )
                        )
                    else:
                        for row_l_idx, r_line in rf_table_lines[2:]:
                            r_cells = parse_table_row(r_line)
                            if len(r_cells) != 6:
                                diagnostics.append(
                                    ParseDiagnostic(
                                        code="MALFORMED_TABLE",
                                        message=(
                                            f"Row in '### Các dạng liên quan' of "
                                            f"'## {title}' has {len(r_cells)} cells (expected 6)."
                                        ),
                                        line=row_l_idx + 1,
                                    )
                                )
                            else:
                                rf_form_raw = r_cells[0].strip()
                                rf_lemma, rf_url = parse_markdown_link(rf_form_raw)
                                rf_pos_raw = r_cells[1].strip()
                                rf_ipa = r_cells[2].strip() or None
                                rf_meaning = r_cells[3].strip()
                                rf_ex_en = r_cells[4].strip()
                                rf_ex_vi = r_cells[5].strip()

                                # Validate POS for related form
                                rf_tokens = [t.strip() for t in rf_pos_raw.split(",") if t.strip()]
                                rf_pos_list: list[str] = []
                                valid_rf_pos = bool(rf_tokens)
                                for tok in rf_tokens:
                                    canon = VALID_POS_MAP.get(tok.lower())
                                    if canon is None:
                                        valid_rf_pos = False
                                        break
                                    if canon not in rf_pos_list:
                                        rf_pos_list.append(canon)

                                if rf_lemma and valid_rf_pos and rf_pos_list:
                                    related_forms.append(
                                        RelatedFormItem(
                                            lemma=rf_lemma,
                                            normalized_lemma=normalize_lemma(rf_lemma),
                                            parts_of_speech=rf_pos_list,
                                            raw_pos=rf_pos_raw,
                                            ipa_us=rf_ipa,
                                            cambridge_url=rf_url,
                                            meaning_vi=rf_meaning,
                                            example_en=rf_ex_en,
                                            example_vi=rf_ex_vi,
                                            raw_row=r_line,
                                        )
                                    )
                                else:
                                    # Opaque contextual row: survives serialization, no card
                                    opaque_rows.append(r_line.strip())
            else:
                # Opaque subsection (e.g. ### Ghi chú bổ sung)
                opaque_subsections.append("".join(entry_lines[h3_offset:h3_end_offset]))

        entries.append(
            DetailedEntry(
                heading=title,
                lemma=lemma_cell,
                normalized_lemma=normalize_lemma(lemma_cell),
                parts_of_speech=entry_pos_list,
                raw_pos=raw_pos,
                ipa_us=ipa_cell,
                stress=stress_cell,
                cambridge_url=cambridge_url,
                meanings_text=meanings_text,
                context_text=context_text,
                example_en=example_en,
                example_vi=example_vi,
                related_forms=related_forms,
                opaque_rows=opaque_rows,
                opaque_sections=opaque_subsections,
                raw_text=raw_section_text,
            )
        )

    # Build semantic forms
    semantic_forms: list[SemanticForm] = []
    for entry in entries:
        norm_root = normalize_lemma(entry.lemma)
        ex_tuple = (
            [
                (
                    unicodedata.normalize("NFC", entry.example_en),
                    unicodedata.normalize("NFC", entry.example_vi),
                )
            ]
            if entry.example_en
            else []
        )
        meanings_list = (
            [unicodedata.normalize("NFC", entry.meanings_text)] if entry.meanings_text else []
        )

        for pos in entry.parts_of_speech:
            semantic_forms.append(
                SemanticForm(
                    lemma=entry.lemma,
                    normalized_lemma=norm_root,
                    part_of_speech=pos,
                    is_primary=True,
                    family_root=norm_root,
                    ipa_us=entry.ipa_us,
                    cambridge_url=entry.cambridge_url,
                    stress=entry.stress,
                    meanings_vi=meanings_list,
                    examples=ex_tuple,
                    source_date=h1_iso,
                    source_date_legacy=h1_legacy,
                )
            )

        for rf in entry.related_forms:
            rf_norm = normalize_lemma(rf.lemma)
            rf_ex = (
                [
                    (
                        unicodedata.normalize("NFC", rf.example_en),
                        unicodedata.normalize("NFC", rf.example_vi),
                    )
                ]
                if rf.example_en
                else []
            )
            rf_meanings = [unicodedata.normalize("NFC", rf.meaning_vi)] if rf.meaning_vi else []
            for rf_pos in rf.parts_of_speech:
                semantic_forms.append(
                    SemanticForm(
                        lemma=rf.lemma,
                        normalized_lemma=rf_norm,
                        part_of_speech=rf_pos,
                        is_primary=False,
                        family_root=norm_root,
                        ipa_us=rf.ipa_us,
                        cambridge_url=rf.cambridge_url,
                        stress=None,
                        meanings_vi=rf_meanings,
                        examples=rf_ex,
                        source_date=h1_iso,
                        source_date_legacy=h1_legacy,
                    )
                )

    is_valid = len(diagnostics) == 0
    status: Literal["VALID", "INVALID"] = "VALID" if is_valid else "INVALID"

    parsed_doc = ParsedDocument(
        note_date=h1_iso,
        note_date_legacy=h1_legacy,
        raw_content=content,
        quick_lookups=quick_lookups,
        entries=entries,
        semantic_forms=semantic_forms,
        opaque_blocks=opaque_blocks,
        diagnostics=diagnostics,
    )

    return ParseResult(
        is_valid=is_valid,
        status=status,
        document=parsed_doc,
        diagnostics=diagnostics,
    )
