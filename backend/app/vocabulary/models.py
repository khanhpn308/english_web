"""Domain models, value objects, and helpers for vocabulary storage (T019)."""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Literal

VerificationStatus = Literal["VERIFIED", "UNVERIFIED", "MISSING"]
SourceStatus = Literal["VALID", "INVALID", "MISSING"]
PreviewStatus = Literal["PREVIEW", "CONSUMED", "EXPIRED", "FAILED"]


def normalize_lemma(lemma: str) -> str:
    """Normalize lemma using Unicode NFC, strip whitespace, lowercase, and collapse spaces."""
    normalized = unicodedata.normalize("NFC", lemma.strip().lower())
    return re.sub(r"\s+", " ", normalized)


def compute_verification_summary(
    *,
    meanings_en: list["MeaningEn"],
    meanings_vi: list["MeaningVi"],
    examples: list["ExampleSentence"],
    ipa_us: str | None,
    cambridge_url: str | None,
    ipa_status: VerificationStatus,
    cambridge_status: VerificationStatus,
) -> VerificationStatus:
    """Compute aggregate verification summary per ADR-0004 and api-contract.

    A separate read-only verificationSummary is VERIFIED only when all learning/display
    fields are verified, MISSING when one is missing (including nullable IPA/link),
    and UNVERIFIED otherwise.
    """
    if ipa_us is None or cambridge_url is None:
        return "MISSING"
    if ipa_status == "MISSING" or cambridge_status == "MISSING":
        return "MISSING"
    if any(m.verification_status == "MISSING" for m in meanings_en):
        return "MISSING"
    if any(m.verification_status == "MISSING" for m in meanings_vi):
        return "MISSING"
    if any(e.verification_status == "MISSING" for e in examples):
        return "MISSING"

    all_en_verified = bool(meanings_en) and all(
        m.verification_status == "VERIFIED" for m in meanings_en
    )
    all_vi_verified = bool(meanings_vi) and all(
        m.verification_status == "VERIFIED" for m in meanings_vi
    )
    all_ex_verified = bool(examples) and all(e.verification_status == "VERIFIED" for e in examples)

    if (
        all_en_verified
        and all_vi_verified
        and all_ex_verified
        and ipa_status == "VERIFIED"
        and cambridge_status == "VERIFIED"
    ):
        return "VERIFIED"

    return "UNVERIFIED"


@dataclass(frozen=True)
class MeaningEn:
    text: str
    language: str = "en"
    verification_status: VerificationStatus = "UNVERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "verificationStatus": self.verification_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeaningEn":
        return cls(
            text=str(data.get("text", "")),
            language=str(data.get("language", "en")),
            verification_status=data.get("verificationStatus", "UNVERIFIED"),
        )


@dataclass(frozen=True)
class MeaningVi:
    text: str
    language: str = "vi"
    verification_status: VerificationStatus = "UNVERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "verificationStatus": self.verification_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeaningVi":
        return cls(
            text=str(data.get("text", "")),
            language=str(data.get("language", "vi")),
            verification_status=data.get("verificationStatus", "UNVERIFIED"),
        )


@dataclass(frozen=True)
class ExampleSentence:
    english: str
    vietnamese: str
    verification_status: VerificationStatus = "UNVERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "english": self.english,
            "vietnamese": self.vietnamese,
            "verificationStatus": self.verification_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExampleSentence":
        return cls(
            english=str(data.get("english", "")),
            vietnamese=str(data.get("vietnamese", "")),
            verification_status=data.get("verificationStatus", "UNVERIFIED"),
        )


@dataclass(frozen=True)
class SourceReference:
    source_id: str
    note_date: str
    status: SourceStatus = "VALID"

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "noteDate": self.note_date,
            "status": self.status,
        }


@dataclass(frozen=True)
class WordFamily:
    id: str
    root_lemma: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class WordForm:
    id: str
    family_id: str
    lemma: str
    normalized_lemma: str
    part_of_speech: str
    meanings_en: list[MeaningEn]
    meanings_vi: list[MeaningVi]
    examples: list[ExampleSentence]
    ipa_us: str | None
    ipa_status: VerificationStatus
    cambridge_url: str | None
    cambridge_status: VerificationStatus
    verification_summary: VerificationStatus
    revision: int
    created_at: str
    updated_at: str
    source_refs: list[SourceReference] = field(default_factory=list)


@dataclass(frozen=True)
class SourceFile:
    id: str
    relative_path: str
    note_date: str
    status: SourceStatus
    revision: int
    etag: str
    content_hash: str | None
    last_parsed_at: str | None
    error_code: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class WordFormDraft:
    form_id: str
    lemma: str
    part_of_speech: str
    meanings_en: list[MeaningEn]
    meanings_vi: list[MeaningVi]
    examples: list[ExampleSentence]
    ipa_us: str | None = None
    cambridge_url: str | None = None
    ipa_status: VerificationStatus = "UNVERIFIED"
    cambridge_status: VerificationStatus = "UNVERIFIED"
    verification_summary: VerificationStatus = "UNVERIFIED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "formId": self.form_id,
            "lemma": self.lemma,
            "partOfSpeech": self.part_of_speech,
            "meaningsEn": [m.to_dict() for m in self.meanings_en],
            "meaningsVi": [m.to_dict() for m in self.meanings_vi],
            "examples": [e.to_dict() for e in self.examples],
            "ipaUs": self.ipa_us,
            "cambridgeUrl": self.cambridge_url,
            "ipaStatus": self.ipa_status,
            "cambridgeStatus": self.cambridge_status,
            "verificationSummary": self.verification_summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WordFormDraft":
        meanings_en = [MeaningEn.from_dict(m) for m in data.get("meaningsEn", [])]
        meanings_vi = [MeaningVi.from_dict(m) for m in data.get("meaningsVi", [])]
        examples = [ExampleSentence.from_dict(e) for e in data.get("examples", [])]
        ipa_us = data.get("ipaUs")
        cambridge_url = data.get("cambridgeUrl")
        ipa_status = data.get("ipaStatus", "MISSING" if ipa_us is None else "UNVERIFIED")
        cambridge_status = data.get(
            "cambridgeStatus", "MISSING" if cambridge_url is None else "UNVERIFIED"
        )
        summary = data.get(
            "verificationSummary",
            compute_verification_summary(
                meanings_en=meanings_en,
                meanings_vi=meanings_vi,
                examples=examples,
                ipa_us=ipa_us,
                cambridge_url=cambridge_url,
                ipa_status=ipa_status,
                cambridge_status=cambridge_status,
            ),
        )
        return cls(
            form_id=str(data.get("formId", "")),
            lemma=str(data.get("lemma", "")),
            part_of_speech=str(data.get("partOfSpeech", "")).upper(),
            meanings_en=meanings_en,
            meanings_vi=meanings_vi,
            examples=examples,
            ipa_us=ipa_us,
            cambridge_url=cambridge_url,
            ipa_status=ipa_status,
            cambridge_status=cambridge_status,
            verification_summary=summary,
        )


@dataclass(frozen=True)
class LookupPreview:
    lookup_id: str
    operation_id: str | None
    owner_session_id: str
    term: str
    forms: list[WordFormDraft]
    provider: str
    model: str
    prompt_version: str
    verification_summary: VerificationStatus
    status: PreviewStatus
    created_at: float
    expires_at: float | None = None
