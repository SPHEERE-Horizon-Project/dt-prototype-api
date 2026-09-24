"""Compare current Python source with the archived pre-refactor snapshot.

This is a provenance aid, not a plagiarism detector or a legal conclusion. It
normalizes package and variable names before comparing token sequences, which
makes a renamed-but-copied module visible while still requiring manual review.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import io
import json
import keyword
import tokenize
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]

# The archive contains the source trees before the current package was
# consolidated and renamed. These mappings are deliberately explicit so the
# report remains auditable.
SOURCE_ROOTS = {
    "dynamic": "DYNAMIC RC/src/mypackage",
    "monthly": "SEMI-STATIONARY/src/semistationary",
    "integration": "SPREADSHEETS INTEGRATION/src/model3_integration",
    "model3": "SPREADSHEETS INTEGRATION/third_party/model3_legacy",
}
CURRENT_ROOTS = {
    "dynamic": ROOT / "src/dt_prototype/dynamic",
    "monthly": ROOT / "src/dt_prototype/monthly",
    "integration": ROOT / "src/dt_prototype/integration",
    "model3": ROOT / "src/dt_prototype/integration/model3",
    "common": ROOT / "src/dt_prototype/common",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_tokens(path: Path) -> list[str]:
    """Return a name-normalized token sequence for similarity comparison."""

    text = tokenize.open(path).read()
    result: list[str] = []
    try:
        stream = tokenize.generate_tokens(io.StringIO(text).readline)
        for token in stream:
            if token.type in {
                tokenize.ENCODING,
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.ENDMARKER,
            }:
                continue
            if token.type == tokenize.NAME:
                result.append(token.string if keyword.iskeyword(token.string) else "<NAME>")
            elif token.type == tokenize.STRING:
                result.append("<STRING>")
            elif token.type == tokenize.NUMBER:
                result.append("<NUMBER>")
            else:
                result.append(token.string)
    except (IndentationError, tokenize.TokenError, SyntaxError):
        return []
    return result


def syntax_fingerprint(path: Path) -> str | None:
    """Return a compact AST shape to distinguish code from prose/boilerplate."""

    try:
        tree = ast.parse(tokenize.open(path).read())
    except (SyntaxError, IndentationError, UnicodeDecodeError):
        return None
    for node in ast.walk(tree):
        for field in ("name", "arg", "attr"):  # names are not provenance evidence
            if hasattr(node, field):
                value = getattr(node, field)
                if isinstance(value, str):
                    setattr(node, field, "<NAME>")
        if isinstance(node, ast.Constant):
            node.value = "<CONSTANT>"
    return ast.dump(tree, annotate_fields=False, include_attributes=False)


def score(current: Path, candidate: Path) -> tuple[float, float, int, int]:
    current_tokens = source_tokens(current)
    candidate_tokens = source_tokens(candidate)
    if len(current_tokens) < 20 or len(candidate_tokens) < 20:
        return 0.0, 0.0, len(current_tokens), len(candidate_tokens)
    token_ratio = difflib.SequenceMatcher(
        None, current_tokens, candidate_tokens, autojunk=False
    ).ratio()
    current_lines = current.read_text(encoding="utf-8").splitlines()
    candidate_lines = candidate.read_text(encoding="utf-8").splitlines()
    line_ratio = difflib.SequenceMatcher(
        None, current_lines, candidate_lines, autojunk=False
    ).ratio()
    # Tokens are the primary evidence; raw lines retain a penalty for major
    # restructuring even when the algorithmic token pattern remains similar.
    return 0.75 * token_ratio + 0.25 * line_ratio, token_ratio, len(current_tokens), len(candidate_tokens)


def band(value: float) -> str:
    if value >= 0.90:
        return "very_high_review_priority"
    if value >= 0.70:
        return "substantial_similarity_review"
    return "low_similarity_or_new_code"


def compare_component(component: str, current_root: Path, source_root: Path) -> list[dict]:
    current_files = sorted(current_root.rglob("*.py")) if current_root.is_dir() else []
    source_files = sorted(source_root.rglob("*.py")) if source_root.is_dir() else []
    records = []
    for current in current_files:
        candidates = []
        for source in source_files:
            similarity, token_similarity, current_count, source_count = score(current, source)
            candidates.append((similarity, token_similarity, current_count, source_count, source))
        if not candidates:
            records.append(
                {
                    "component": component,
                    "current_file": current.relative_to(ROOT).as_posix(),
                    "source_file": None,
                    "similarity": 0.0,
                    "token_similarity": 0.0,
                    "current_tokens": len(source_tokens(current)),
                    "source_tokens": 0,
                    "raw_sha256_equal": False,
                    "review_band": "no_source_snapshot",
                }
            )
            continue
        similarity, token_similarity, current_count, source_count, source = max(
            candidates, key=lambda item: item[0]
        )
        records.append(
            {
                "component": component,
                "current_file": current.relative_to(ROOT).as_posix(),
                "source_file": source.relative_to(source_root).as_posix(),
                "similarity": round(similarity, 6),
                "token_similarity": round(token_similarity, 6),
                "current_tokens": current_count,
                "source_tokens": source_count,
                "raw_sha256_equal": sha256(current) == sha256(source),
                "review_band": band(similarity),
            }
        )
    return records


def markdown_report(records: list[dict], archive: Path) -> str:
    comparable = [row for row in records if row["source_file"]]
    lines = [
        "# DT-Prototype code-lineage comparison",
        "",
        "This report compares the current source with the archived pre-refactor",
        f"snapshot `{archive.name}`. It is a provenance aid, not a legal conclusion:",
        "normalized token similarity can identify likely copied or lightly modified",
        "code, but every high-scoring pair still requires human review.",
        "",
        f"Compared current Python files: **{len(records)}**; files with a source candidate: **{len(comparable)}**.",
        "",
        "## Review bands",
        "",
        "- `very_high_review_priority` (score ≥ 0.90): inspect as likely copied or lightly modified.",
        "- `substantial_similarity_review` (0.70–0.89): inspect algorithm and history.",
        "- `low_similarity_or_new_code` (< 0.70): likely substantially rewritten or new, but not proof of independence.",
        "",
        "The score normalizes package names, variable names, strings and numeric literals.",
        "It therefore survives package renaming but does not distinguish independently",
        "written code that follows the same common algorithmic pattern.",
        "",
        "## File comparison",
        "",
        "| Component | Current file | Best archived source | Score | Token score | Raw hash equal | Review band |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for row in sorted(records, key=lambda item: (item["component"], item["current_file"])):
        lines.append(
            "| {component} | `{current_file}` | `{source_file}` | {similarity:.3f} | {token_similarity:.3f} | {raw_sha256_equal} | {review_band} |".format(
                **row,
                source_file=row["source_file"] or "(none)",
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive",
        type=Path,
        default=ROOT / "archive/pre_refactor_sources_20260917.zip",
        help="pre-refactor source archive",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/code_lineage_comparison",
        help="new directory for JSON and Markdown reports",
    )
    args = parser.parse_args()
    archive = args.archive.resolve()
    output = args.output.resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.mkdir(parents=True)

    with TemporaryDirectory(prefix="dt_lineage_") as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(archive) as source_zip:
            source_zip.extractall(extracted)
        records: list[dict] = []
        for component, current_root in CURRENT_ROOTS.items():
            if component == "common":
                source_roots = [
                    extracted / SOURCE_ROOTS["dynamic"],
                    extracted / SOURCE_ROOTS["monthly"],
                    extracted / SOURCE_ROOTS["integration"],
                ]
                candidates = []
                for source_root in source_roots:
                    candidates.extend(compare_component(component, current_root, source_root))
                # Keep one best source match per current file across the relevant
                # source trees.
                best: dict[str, dict] = {}
                for record in candidates:
                    previous = best.get(record["current_file"])
                    if previous is None or record["similarity"] > previous["similarity"]:
                        best[record["current_file"]] = record
                records.extend(best.values())
                continue
            records.extend(
                compare_component(
                    component,
                    current_root,
                    extracted / SOURCE_ROOTS[component],
                )
            )

        metadata = {
            "archive": str(archive),
            "archive_sha256": sha256(archive),
            "current_root": str(ROOT),
            "record_count": len(records),
            "review_band_counts": {
                review_band: sum(row["review_band"] == review_band for row in records)
                for review_band in sorted({row["review_band"] for row in records})
            },
            "records": records,
        }
        (output / "code_lineage_comparison.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        (output / "code_lineage_comparison.md").write_text(
            markdown_report(records, archive), encoding="utf-8"
        )
        print(json.dumps(metadata["review_band_counts"], indent=2))
        print(output)


if __name__ == "__main__":
    main()
