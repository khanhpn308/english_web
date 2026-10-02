"""Generate the deterministic synthetic T042 search benchmark fixture.

The fixture is intentionally independent of the production search index.  The
reference matcher in this module performs a small, direct scan over the stored
Vietnamese meanings; tests separately compare that oracle with a bounded T026
projection sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_FORM_COUNT = 100_000
DEFAULT_SEED = 29
MAX_FORM_COUNT = 1_000_000
MAX_SEED = 2**32 - 1
SCHEMA_VERSION = "t042-fixture-v1"
GENERATOR_VERSION = "t042-generator-v1"

_POS_VALUES = ("ADJECTIVE", "NOUN", "VERB", "ADVERB")
_PHRASES = (
    "bài học trực tuyến",
    "học tập hiệu quả",
    "phân tích dữ liệu",
    "tài liệu tham khảo",
    "quy trình kiểm thử",
    "mô hình ngôn ngữ",
    "kết quả chính xác",
    "thực hành hằng ngày",
    "cải thiện kỹ năng",
    "ngữ cảnh phù hợp",
    "độ tin cậy cao",
    "điều chỉnh tốc độ",
    "phản hồi nhanh chóng",
    "phương án dự phòng",
    "cấu trúc rõ ràng",
    "từ vựng học thuật",
    "bản ghi phiên bản",
    "tìm kiếm nội dung",
    "kết nối an toàn",
    "lưu trữ cục bộ",
)
_SPECIAL_MEANINGS = {
    0: ("bền vững", "ADJECTIVE"),
    1: ("đáng tin cậy", "ADJECTIVE"),
    2: ("đáng tin cậy", "VERB"),
    3: ("cà phê", "NOUN"),
    4: ("điều kiện", "NOUN"),
    5: ("tỉ lệ 50% [ước tính]; giá trị_chuẩn", "NOUN"),
    6: ("phương pháp", "NOUN"),
    7: ("đo lường", "VERB"),
    8: ("mục tiêu", "NOUN"),
    9: ("người học", "NOUN"),
    10: ("bền bỉ", "ADJECTIVE"),
    11: ("ngôn ngữ tự nhiên", "NOUN"),
}


class FixtureValidationError(ValueError):
    """Raised when a fixture row, count, identity, or checksum is invalid."""


@dataclass(frozen=True)
class FixtureSummary:
    form_count: int
    unique_ids: int
    sha256: str


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _reference_exact(text: str) -> str:
    """Independent NFC/casefold/space reference normalization for the oracle."""
    normalized = unicodedata.normalize("NFC", text.strip().casefold())
    return " ".join(normalized.split())


def _reference_fold(text: str) -> str:
    """Independent accent-folded reference normalization for the oracle."""
    value = text.strip().casefold().replace("đ", "d").replace("Đ", "d")
    decomposed = unicodedata.normalize("NFD", value)
    without_marks = "".join(
        character for character in decomposed if unicodedata.category(character) != "Mn"
    )
    return " ".join(unicodedata.normalize("NFC", without_marks).split())


def _add_query(
    specs: list[dict[str, str]], seen: set[str], query_id: str, query: str, category: str
) -> None:
    if query in seen:
        return
    specs.append({"id": query_id, "query": query, "category": category})
    seen.add(query)


def build_query_specs() -> list[dict[str, str]]:
    """Return the fixed, seed-independent set of exactly 100 query definitions."""
    specs: list[dict[str, str]] = []
    seen: set[str] = set()
    _add_query(specs, seen, "q001-exact-unique", "bền vững", "exact")
    _add_query(specs, seen, "q002-infix-middle", "tin cậy", "infix")
    _add_query(specs, seen, "q003-one-character-d", "đ", "one-character")
    _add_query(specs, seen, "q004-one-character-folded-d", "d", "one-character-folded")
    _add_query(specs, seen, "q005-two-character", "bề", "two-character")
    _add_query(specs, seen, "q006-three-character", "vững", "three-character")
    _add_query(specs, seen, "q007-nfc-precomposed", "cà phê", "NFC")
    _add_query(
        specs,
        seen,
        "q008-nfc-combining",
        unicodedata.normalize("NFD", "cà phê"),
        "combining-mark",
    )
    _add_query(specs, seen, "q009-accent-fold", "ben vung", "accent-fold")
    _add_query(specs, seen, "q010-d-stroke-fold", "dieu kien", "d-fold")
    _add_query(specs, seen, "q011-casefold", "ĐIỀU KIỆN", "case-fold")
    _add_query(specs, seen, "q012-punctuation-percent", "50%", "punctuation")
    _add_query(specs, seen, "q013-punctuation-underscore", "giá trị_chuẩn", "punctuation")
    _add_query(specs, seen, "q014-punctuation-brackets", "[ước tính]", "punctuation")
    _add_query(specs, seen, "q015-pos-duplicate", "đáng tin cậy", "multiple-POS")
    _add_query(specs, seen, "q016-zero-semantic", "kiên cố", "no-semantic-guessing")
    _add_query(specs, seen, "q017-zero-absent", "không tồn tại", "zero-match")
    _add_query(specs, seen, "q018-infix-boundary", "học", "infix")
    _add_query(specs, seen, "q019-exact-second-special", "đo lường", "exact")
    _add_query(specs, seen, "q020-short-folded", "ca phe", "accent-fold")

    for index, phrase in enumerate(_PHRASES):
        _add_query(specs, seen, f"q{len(specs) + 1:03d}-phrase-exact-{index:02d}", phrase, "exact")
    for index, phrase in enumerate(_PHRASES):
        first_word = phrase.split(" ", 1)[0]
        _add_query(
            specs,
            seen,
            f"q{len(specs) + 1:03d}-phrase-infix-{index:02d}",
            first_word[:3],
            "infix",
        )

    for index, short_query in enumerate(
        ("q", "x", "j", "w", "z", "f", "v", "ô", "ư", "ă", "â", "ê", "ơ", "ý", "đ")
    ):
        _add_query(
            specs, seen, f"q{len(specs) + 1:03d}-short-{index:02d}", short_query, "one-character"
        )

    for index, phrase in enumerate(_PHRASES[:10]):
        _add_query(
            specs,
            seen,
            f"q{len(specs) + 1:03d}-folded-{index:02d}",
            _reference_fold(phrase),
            "accent-fold",
        )

    index = 0
    while len(specs) < 100:
        _add_query(
            specs,
            seen,
            f"q{len(specs) + 1:03d}-zero-{index:02d}",
            f"không có mục {index:02d}",
            "zero-match",
        )
        index += 1

    while len(specs) < 100:
        index = len(specs)
        _add_query(
            specs,
            seen,
            f"q{index + 1:03d}-three-character-{index:02d}",
            f"zz{index:02d}",
            "three-character",
        )
    return specs


def _form_record(index: int, seed: int) -> dict[str, Any]:
    special = _SPECIAL_MEANINGS.get(index)
    if special is None:
        bucket = (index * 2_654_435_761 + seed * 97) % len(_PHRASES)
        meaning, pos = _PHRASES[bucket], _POS_VALUES[bucket % len(_POS_VALUES)]
    else:
        meaning, pos = special
    source_bucket = (index + seed) % 31
    source_id = f"t042-source-{source_bucket:02d}"
    date = f"2026-01-{source_bucket + 1:02d}"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "id": f"t042-{seed}-{index:06d}",
        "familyId": f"t042-family-{index % 257:03d}",
        "lemma": f"synthetic-lemma-{seed}-{index:06d}",
        "normalizedLemma": f"synthetic-lemma-{seed}-{index:06d}",
        "partOfSpeech": pos,
        "meaningsVi": [meaning],
        "sourceRefs": [{"sourceId": source_id, "noteDate": date, "status": "VALID"}],
        "verificationSummary": "VERIFIED",
        "revision": 1,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


def independent_match_ids(rows: Iterable[dict[str, Any]], query: str) -> list[str]:
    """Brute-force expected IDs using stored meanings and source validity only."""
    query_exact = _reference_exact(query)
    query_folded = _reference_fold(query)
    if not query_exact:
        return []
    matches: list[str] = []
    for row in rows:
        refs = row.get("sourceRefs", [])
        if not any(ref.get("status") == "VALID" for ref in refs):
            continue
        meanings = row.get("meaningsVi", [])
        if any(
            query_exact in _reference_exact(str(meaning))
            or query_folded in _reference_fold(str(meaning))
            for meaning in meanings
        ):
            matches.append(str(row["id"]))
    return sorted(matches)


def validate_form_record(row: object) -> None:
    if not isinstance(row, dict):
        raise FixtureValidationError("record must be a JSON object")
    required = {
        "schemaVersion",
        "id",
        "familyId",
        "lemma",
        "normalizedLemma",
        "partOfSpeech",
        "meaningsVi",
        "sourceRefs",
        "verificationSummary",
        "revision",
        "createdAt",
        "updatedAt",
    }
    missing = sorted(required - set(row))
    if missing:
        raise FixtureValidationError(f"missing fields: {', '.join(missing)}")
    if row["schemaVersion"] != SCHEMA_VERSION:
        raise FixtureValidationError("unsupported schemaVersion")
    if not isinstance(row["id"], str) or not row["id"]:
        raise FixtureValidationError("id must be a non-empty string")
    meanings = row["meaningsVi"]
    if (
        not isinstance(meanings, list)
        or not meanings
        or not all(isinstance(meaning, str) and meaning for meaning in meanings)
    ):
        raise FixtureValidationError("meaningsVi must be a non-empty list of strings")
    refs = row["sourceRefs"]
    if not isinstance(refs, list) or not refs:
        raise FixtureValidationError("sourceRefs must be a non-empty list")
    for ref in refs:
        if not isinstance(ref, dict) or not {"sourceId", "noteDate", "status"} <= set(ref):
            raise FixtureValidationError("sourceRefs contains a malformed reference")
        if ref["status"] not in {"VALID", "INVALID", "MISSING"}:
            raise FixtureValidationError("sourceRefs contains an invalid status")


def iter_fixture_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise FixtureValidationError(f"blank record at line {line_number}")
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise FixtureValidationError(f"invalid JSON at line {line_number}") from error
            validate_form_record(row)
            yield row


def validate_fixture_file(path: Path, expected_count: int) -> FixtureSummary:
    if expected_count <= 0:
        raise FixtureValidationError("expected count must be positive")
    hasher = hashlib.sha256()
    count = 0
    ids: set[str] = set()
    with path.open("rb") as stream:
        for line_number, raw_line in enumerate(stream, start=1):
            hasher.update(raw_line)
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise FixtureValidationError(f"invalid JSON at line {line_number}") from error
            validate_form_record(row)
            form_id = str(row["id"])
            if form_id in ids:
                raise FixtureValidationError(f"duplicate form id: {form_id}")
            ids.add(form_id)
            count += 1
    if count != expected_count:
        raise FixtureValidationError(f"expected {expected_count} records, got {count}")
    return FixtureSummary(count, len(ids), hasher.hexdigest())


def validate_report(
    report_path: Path, fixture_path: Path, expected_forms: int, expected_seed: int
) -> dict[str, Any]:
    """Validate report metadata, query checksums, expected IDs, and fixture bytes."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureValidationError("unable to read search report") from error
    if not isinstance(report, dict):
        raise FixtureValidationError("search report must be a JSON object")
    fixture_summary = validate_fixture_file(fixture_path, expected_forms)
    if report.get("seed") != expected_seed:
        raise FixtureValidationError("search report seed mismatch")
    if report.get("actualFormCount") != expected_forms or report.get("queryCount") != 100:
        raise FixtureValidationError("search report count mismatch")
    if report.get("fixtureSha256") != fixture_summary.sha256:
        raise FixtureValidationError("search report fixture checksum mismatch")
    queries = report.get("queries")
    if not isinstance(queries, list) or len(queries) != 100:
        raise FixtureValidationError("search report must contain exactly 100 queries")
    query_payload = []
    ground_truth_payload = []
    query_ids: set[str] = set()
    for query in queries:
        if not isinstance(query, dict) or not {
            "id",
            "query",
            "category",
            "expectedMatchIds",
        } <= set(query):
            raise FixtureValidationError("search report contains a malformed query")
        query_id = str(query["id"])
        if query_id in query_ids:
            raise FixtureValidationError(f"duplicate query id: {query_id}")
        query_ids.add(query_id)
        if not isinstance(query["expectedMatchIds"], list) or not all(
            isinstance(form_id, str) for form_id in query["expectedMatchIds"]
        ):
            raise FixtureValidationError("search report expected IDs are malformed")
        query_payload.append(
            {"id": query_id, "query": query["query"], "category": query["category"]}
        )
        ground_truth_payload.append({"id": query_id, "expectedMatchIds": query["expectedMatchIds"]})
    if report.get("querySetSha256") != hashlib.sha256(_canonical_bytes(query_payload)).hexdigest():
        raise FixtureValidationError("search report query checksum mismatch")
    if (
        report.get("groundTruthSha256")
        != hashlib.sha256(_canonical_bytes(ground_truth_payload)).hexdigest()
    ):
        raise FixtureValidationError("search report ground-truth checksum mismatch")
    return report


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def generate_fixture(
    forms: int = DEFAULT_FORM_COUNT, seed: int = DEFAULT_SEED, output_dir: Path | str | None = None
) -> dict[str, Any]:
    """Stream a fixture and atomically publish its report and JSONL artifact."""
    if not 1 <= forms <= MAX_FORM_COUNT:
        raise ValueError(f"forms must be between 1 and {MAX_FORM_COUNT}")
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"seed must be between 0 and {MAX_SEED}")
    root = Path(output_dir) if output_dir is not None else Path(__file__).resolve().parent
    fixture_path = root / "fixtures" / "100k_forms.jsonl"
    report_path = root / "artifacts" / "search-report.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    query_specs = build_query_specs()
    expected: dict[str, list[str]] = {spec["id"]: [] for spec in query_specs}
    query_exact = {spec["id"]: _reference_exact(spec["query"]) for spec in query_specs}
    query_folded = {spec["id"]: _reference_fold(spec["query"]) for spec in query_specs}
    fixture_temp: Path | None = None
    hasher = hashlib.sha256()
    count = 0
    try:
        with tempfile.NamedTemporaryFile(
            dir=fixture_path.parent,
            prefix=f".{fixture_path.name}.",
            suffix=".tmp",
            mode="wb",
            delete=False,
        ) as stream:
            fixture_temp = Path(stream.name)
            for index in range(forms):
                row = _form_record(index, seed)
                payload = _canonical_bytes(row) + b"\n"
                stream.write(payload)
                hasher.update(payload)
                count += 1
                meaning_exact = _reference_exact(row["meaningsVi"][0])
                meaning_folded = _reference_fold(row["meaningsVi"][0])
                for spec in query_specs:
                    query_id = spec["id"]
                    if (
                        query_exact[query_id] in meaning_exact
                        or query_folded[query_id] in meaning_folded
                    ):
                        expected[query_id].append(row["id"])
            if count != forms:
                raise FixtureValidationError(f"generated {count} records, expected {forms}")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(fixture_temp, fixture_path)
        fixture_temp = None

        query_payload = [
            {"id": spec["id"], "query": spec["query"], "category": spec["category"]}
            for spec in query_specs
        ]
        ground_truth_payload = [
            {"id": spec["id"], "expectedMatchIds": expected[spec["id"]]} for spec in query_specs
        ]
        report = {
            "schemaVersion": SCHEMA_VERSION,
            "generatorVersion": GENERATOR_VERSION,
            "seed": seed,
            "requestedFormCount": forms,
            "actualFormCount": count,
            "queryCount": len(query_specs),
            "fixtureSha256": hasher.hexdigest(),
            "querySetSha256": hashlib.sha256(_canonical_bytes(query_payload)).hexdigest(),
            "groundTruthSha256": hashlib.sha256(_canonical_bytes(ground_truth_payload)).hexdigest(),
            "queries": [
                {
                    "id": spec["id"],
                    "query": spec["query"],
                    "category": spec["category"],
                    "expectedMatchIds": expected[spec["id"]],
                }
                for spec in query_specs
            ],
        }
        _write_atomic(report_path, _canonical_bytes(report) + b"\n")
        return report
    finally:
        if fixture_temp is not None and fixture_temp.exists():
            fixture_temp.unlink()


def _forms_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("forms must be an integer") from error
    if not 1 <= parsed <= MAX_FORM_COUNT:
        raise argparse.ArgumentTypeError(f"forms must be between 1 and {MAX_FORM_COUNT}")
    return parsed


def _seed_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("seed must be an integer") from error
    if not 0 <= parsed <= MAX_SEED:
        raise argparse.ArgumentTypeError(f"seed must be between 0 and {MAX_SEED}")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forms", type=_forms_arg, default=DEFAULT_FORM_COUNT)
    parser.add_argument("--seed", type=_seed_arg, default=DEFAULT_SEED)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args(argv)
    report = generate_fixture(args.forms, args.seed, args.output_dir)
    print(
        f"generated {report['actualFormCount']} forms and {report['queryCount']} queries "
        f"(fixtureSha256={report['fixtureSha256']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
