"""Lossless Markdown serializer for academic vocabulary daily logs (T020).

Pure serializer boundary: no filesystem access, no SQLite, no network, no AI, no global state.
"""

from backend.app.markdown_sync.parser import ParsedDocument


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
