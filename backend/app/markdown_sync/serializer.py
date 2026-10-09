"""Lossless Markdown serializer for academic vocabulary daily logs (T020).

Pure serializer boundary: no filesystem access, no SQLite, no network, no AI, no global state.
"""

import json
import re
import unicodedata
from typing import Any

from backend.app.markdown_sync.parser import (
    STRUCTURED_HEADING,
    VALID_POS_MAP,
    ParsedDocument,
    SemanticForm,
    normalize_lemma,
    structured_semantics,
)


def _legacy_data(form: SemanticForm) -> dict[str, Any]:
    """Carry precisely the legacy semantics into the explicit extension."""
    return {
        "lemma": form.lemma, "partOfSpeech": form.part_of_speech,
        "meaningsEn": [
            {"text": text, "language": "en", "verificationStatus": "UNVERIFIED"}
            for text in form.meanings_en
        ],
        "meaningsVi": [
            {"text": text, "language": "vi", "verificationStatus": "UNVERIFIED"}
            for text in form.meanings_vi
        ],
        "examples": [
            {"english": en, "vietnamese": vi, "verificationStatus": "UNVERIFIED"}
            for en, vi in form.examples
        ],
        "ipaUs": form.ipa_us, "cambridgeUrl": form.cambridge_url,
        "ipaStatus": "MISSING" if form.ipa_us is None else "UNVERIFIED",
        "cambridgeStatus": "MISSING" if form.cambridge_url is None else "UNVERIFIED",
    }


def structured_section(data: dict[str, Any]) -> str:
    """Deterministic readable data block; JSON escaping keeps text out of syntax."""
    structured_semantics(data, "")
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
    # str.splitlines recognizes these Unicode separators even inside JSON strings.
    # Keep them escaped so untrusted text cannot become a Markdown heading.
    for separator, escape in [
        ("\u0085", "\\u0085"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029"),
    ]:
        encoded = encoded.replace(separator, escape)
    return (
        f"### {STRUCTURED_HEADING}\n\n```json\n"
        + encoded
        + "\n```\n\n"
    )


def _item_key(value: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", value[field]) for field in fields)


def _form_identity(form: dict[str, Any]) -> tuple[str, str]:
    pos = VALID_POS_MAP.get(form["partOfSpeech"].lower())
    if pos is None:
        raise ValueError("Invalid structured identity")
    return normalize_lemma(form["lemma"]), pos


def _merge_form(prior: dict[str, Any], form: dict[str, Any]) -> dict[str, Any]:
    merged = {**prior, **form}
    for name, fields in [
        ("meaningsEn", ("text", "language")),
        ("meaningsVi", ("text", "language")),
        ("examples", ("english", "vietnamese")),
    ]:
        old = {_item_key(value, fields): value for value in prior.get(name, [])}
        merged[name] = [
            {**old.get(_item_key(value, fields), {}), **value} for value in form[name]
        ]
    return merged


def upsert_structured_family(document: ParsedDocument, data: dict[str, Any]) -> str:
    """Change only one family's explicit data, preserving every other raw byte."""
    new_forms = structured_semantics(data, document.note_date)
    root = new_forms[0].family_root
    matches = [entry for entry in document.entries if (
        normalize_lemma(str(entry.structured_data["familyRoot"]))
        if entry.structured_data is not None else entry.normalized_lemma
    ) == root]
    if len(matches) > 1:
        raise ValueError("Ambiguous source family")
    content = serialize_document(document)
    if not matches:
        return content + ("" if content.endswith("\n\n") else "\n\n") + (
            "## Word family\n\n" + structured_section(data)
        )
    entry = matches[0]
    if entry.structured_data is not None:
        merged = dict(entry.structured_data)
        prior = {
            _form_identity(f): f
            for f in merged["forms"]
        }
        forms = []
        updates = {}
        for form in data["forms"]:
            identity = _form_identity(form)
            updates[identity] = _merge_form(prior.get(identity, {}), form)
        # A preview can add a subset to an existing family. Other family forms stay.
        forms.extend(updates.pop(key, form) for key, form in prior.items())
        forms.extend(updates.values())
        merged.update(data)
        merged["forms"] = forms
        replacement = re.sub(
            rf"(?ms)^###[ \t]+{re.escape(STRUCTURED_HEADING)}[ \t]*\r?\n.*?(?=^### |\Z)",
            lambda _match: structured_section(merged), entry.raw_text, count=1,
        )
    else:
        # Existing legacy prose remains byte-for-byte. The explicitly marked data
        # block owns this family's semantics once present; unknown context stays raw.
        merged = dict(data)
        incoming = {(f.normalized_lemma, f.part_of_speech) for f in new_forms}
        merged["forms"] = list(data["forms"]) + [
            _legacy_data(form) for form in document.semantic_forms
            if form.family_root == root
            and (form.normalized_lemma, form.part_of_speech) not in incoming
        ]
        replacement = entry.raw_text + "\n" + structured_section(merged)
    if content.count(entry.raw_text) != 1:
        raise ValueError("Ambiguous source section")
    return content.replace(entry.raw_text, replacement, 1)


def serialize_document(document: ParsedDocument) -> str:
    """Serialize a parsed document back to Markdown losslessly.

    For an unchanged parsed document, returns the exact raw content.
    If reconstructed or modified, reconstructs valid Markdown matching legacy format.
    """
    if document is None:
        raise ValueError("Cannot serialize None document")

    if document.raw_content:
        return document.raw_content

    # Fallback reconstruction
    parts: list[str] = [f"# {document.note_date_legacy}\n\n"]

    if document.quick_lookups:
        parts.append("## Tra cứu nhanh\n\n")
        parts.append("| Từ/cụm từ | IPA (US) | Nghĩa ngắn | Ví dụ ngắn | Dịch ví dụ |\n")
        parts.append("|---|---|---|---|---|\n")
        for item in document.quick_lookups:
            row_str = (
                f"| {item.raw_term} | {item.ipa_us} | {item.short_meaning} | "
                f"{item.short_example} | {item.short_translation} |\n"
            )
            parts.append(row_str)
        parts.append("\n")

    for entry in document.entries:
        if entry.raw_text:
            parts.append(entry.raw_text)
        elif entry.structured_data is not None:
            parts.append("## Word family\n\n" + structured_section(entry.structured_data))
        else:
            parts.append(f"## {entry.heading}\n\n")
            parts.append("| Từ/cụm từ | Từ loại | IPA (US) | Trọng âm | Nguồn |\n")
            parts.append("|---|---|---|---|---|\n")
            source_link = (
                f"[Cambridge Dictionary]({entry.cambridge_url})" if entry.cambridge_url else ""
            )
            entry_row = (
                f"| {entry.lemma} | {entry.raw_pos} | {entry.ipa_us or ''} | "
                f"{entry.stress or ''} | {source_link} |\n\n"
            )
            parts.append(entry_row)
            if entry.meanings_text:
                parts.append(f"### Ý nghĩa\n\n{entry.meanings_text}\n\n")
            if entry.context_text:
                parts.append(f"### Trong ngữ cảnh\n\n{entry.context_text}\n\n")
            if entry.example_en or entry.example_vi:
                parts.append("### Ví dụ\n\n")
                if entry.example_en:
                    parts.append(f"{entry.example_en}\n\n")
                if entry.example_vi:
                    parts.append(f"*Bản dịch:* {entry.example_vi}\n\n")
            if entry.related_forms or entry.opaque_rows:
                parts.append("### Các dạng liên quan\n\n")
                parts.append("| Dạng từ | Từ loại | IPA (US) | Nghĩa | Ví dụ ngắn | Dịch ví dụ |\n")
                parts.append("|---|---|---|---|---|---|\n")
                for rf in entry.related_forms:
                    form_display = (
                        f"[{rf.lemma}]({rf.cambridge_url})" if rf.cambridge_url else rf.lemma
                    )
                    rf_row = (
                        f"| {form_display} | {rf.raw_pos} | {rf.ipa_us or ''} | "
                        f"{rf.meaning_vi} | {rf.example_en} | {rf.example_vi} |\n"
                    )
                    parts.append(rf_row)
                for orow in entry.opaque_rows:
                    parts.append(f"{orow}\n")
                parts.append("\n")
            for osub in entry.opaque_sections:
                parts.append(f"{osub}\n")

    for block in document.opaque_blocks:
        parts.append(block)

    return "".join(parts)
