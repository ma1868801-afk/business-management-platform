"""Deterministic chunker for `rag_sources/**/*.md` (04_rag_design.md section 4).

Implements the chunking rules exactly as written: a header chunk, one chunk per `##`
section when it fits the 200-token body budget, a split at `###` headings for larger
sections, block-packing (paragraph/list/table/code fence) for anything still too large,
and the rule that any unit containing a code fence is kept whole with a `description`-only
`embed_text` (section 4.3).

This module does not depend on the real embedding-model tokenizer (unavailable in this
sandbox, see the Phase 3 notes in README.md): it uses the heuristic estimator the spec
itself defines for the documentation checks (section 4.2) and documents, in
`tests/test_chunker_corpus.py`, how closely the result tracks the published counts
(section 2 and section 13) -- this is not guaranteed to be bit-for-bit identical to the
original reference chunker, which is not available to this implementation.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

TOKEN_BUDGET = 200
MAX_EMBED_TOKENS = 256
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")
_CODE_FENCE_RE = re.compile(r"```[a-zA-Z]*\n.*?```", re.S)
_HEADER_FIELD_RE = re.compile(r"^-\s*([A-Za-z][A-Za-z \-]*?):\s*(.+?)\s*$")
_H2_RE = re.compile(r"^##\s+(.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(.+?)\s*$")
_H1_RE = re.compile(r"^#\s+(.+?)\s*$")

# knowledge_base documents whose "## <ID> <name>" sections are themselves the subject (one
# section per employee record, section 3.1); for these, a "##" heading that matches this
# pattern is NOT a numbered policy section, it is a record and is treated like a "###" unit
# for chunking purposes (i.e. each one is its own chunk when it fits, split by blocks if not).
_RECORD_HEADING_RE = re.compile(r"^(EMP-\d{4}|[A-Z]{3,5}-\d{4})\b")


def estimate_tokens(text: str) -> int:
    """Section 4.2: 1.3 * count of \\w+ or punctuation tokens."""
    return int(round(1.3 * len(_TOKEN_RE.findall(text))))


def has_code_fence(text: str) -> bool:
    return "```" in text


def strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", text).strip()


@dataclass
class HeaderBlock:
    doc_id: str = ""
    fields: dict = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_no: int
    section_path: str
    kind: str  # "text" | "code"
    body: str
    embed_text_suffix: str  # the part after the "Title (Doc ID) | Section path" prefix


@dataclass
class ParsedDocument:
    title: str
    doc_id: str
    header_fields: dict
    source_path: str
    raw_lines: list[str]


class ChunkerError(Exception):
    pass


def parse_header(lines: list[str]) -> tuple[str, HeaderBlock, int]:
    """Returns (title, header_block, index_of_first_content_line_after_header)."""
    if not lines or not _H1_RE.match(lines[0]):
        raise ChunkerError("file does not start with a level-1 '# Title' heading")
    title = _H1_RE.match(lines[0]).group(1)
    i = 1
    header = HeaderBlock()
    while i < len(lines) and not lines[i].strip():
        i += 1
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith("##"):
            break
        m = _HEADER_FIELD_RE.match(line)
        if not m:
            break
        key, value = m.group(1).strip(), m.group(2).strip()
        header.fields[key] = value
        if key == "Document ID":
            header.doc_id = value
        i += 1
    if not header.doc_id:
        raise ChunkerError("no 'Document ID' field found in the header block")
    return title, header, i


def _split_top_level(lines: list[str], start: int) -> list[tuple[str, int, int]]:
    """Splits lines[start:] into (heading_text, body_start, body_end) for each top-level
    '## ' heading (body_end exclusive)."""
    sections = []
    i = start
    cur_heading = None
    cur_body_start = None
    while i <= len(lines):
        is_h2 = i < len(lines) and _H2_RE.match(lines[i])
        if is_h2 or i == len(lines):
            if cur_heading is not None:
                sections.append((cur_heading, cur_body_start, i))
            if is_h2:
                cur_heading = _H2_RE.match(lines[i]).group(1)
                cur_body_start = i + 1
        i += 1
    return sections


def _split_h3(lines: list[str], start: int, end: int) -> tuple[int, list[tuple[str, int, int]]]:
    """Within lines[start:end], finds the first '### ' heading and returns
    (intro_end, [(h3_heading, body_start, body_end), ...])."""
    first_h3 = None
    for i in range(start, end):
        if _H3_RE.match(lines[i]):
            first_h3 = i
            break
    if first_h3 is None:
        return end, []
    units = []
    i = first_h3
    cur_heading = None
    cur_body_start = None
    while i <= end:
        is_h3 = i < end and _H3_RE.match(lines[i])
        if is_h3 or i == end:
            if cur_heading is not None:
                units.append((cur_heading, cur_body_start, i))
            if is_h3:
                cur_heading = _H3_RE.match(lines[i]).group(1)
                cur_body_start = i + 1
        i += 1
    return first_h3, units


def _is_record_style_h2(section_lines: list[str]) -> bool:
    """True if this '##' section is itself a record (employee record sets, section 3.1):
    the heading looks like 'EMP-0001 Name' rather than a numbered topic."""
    return False  # handled at the heading-text level by the caller (see _looks_like_record)


def _looks_like_record(heading_text: str) -> bool:
    return bool(_RECORD_HEADING_RE.match(heading_text.strip()))


# --- block-level splitting (rule 4) ---------------------------------------------------------

@dataclass
class Block:
    kind: str  # "para" | "list" | "table" | "code"
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip()


def _split_blocks(body_lines: list[str]) -> list[Block]:
    blocks: list[Block] = []
    i = 0
    n = len(body_lines)
    while i < n:
        line = body_lines[i]
        if not line.strip():
            i += 1
            continue
        if line.lstrip().startswith("```"):
            j = i + 1
            while j < n and not body_lines[j].lstrip().startswith("```"):
                j += 1
            j = min(j + 1, n)
            blocks.append(Block("code", body_lines[i:j]))
            i = j
        elif line.lstrip().startswith("|"):
            j = i
            while j < n and body_lines[j].lstrip().startswith("|"):
                j += 1
            blocks.append(Block("table", body_lines[i:j]))
            i = j
        elif re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            j = i
            while j < n and (body_lines[j].strip() == "" or re.match(r"^\s*([-*]\s+|\d+\.\s+|\s)", body_lines[j])) and not body_lines[j].lstrip().startswith("```") and not body_lines[j].lstrip().startswith("|"):
                if body_lines[j].strip() == "" and (j + 1 >= n or not re.match(r"^\s*([-*]\s+|\d+\.\s+)", body_lines[j + 1] if j + 1 < n else "")):
                    break
                j += 1
            blocks.append(Block("list", body_lines[i:j]))
            i = j
        else:
            j = i
            while j < n and body_lines[j].strip() and not body_lines[j].lstrip().startswith("```") and not body_lines[j].lstrip().startswith("|") and not re.match(r"^\s*([-*]\s+|\d+\.\s+)", body_lines[j]):
                j += 1
            blocks.append(Block("para", body_lines[i:j]))
            i = j
    return blocks


def _split_table_block(block: Block, budget: int) -> list[str]:
    lines = [l for l in block.lines if l.strip()]
    if len(lines) < 2:
        return [block.text] if block.text else []
    header, sep, rows = lines[0], lines[1], lines[2:]
    out = []
    cur = [header, sep]
    for row in rows:
        trial = "\n".join(cur + [row])
        if estimate_tokens(trial) > budget and len(cur) > 2:
            out.append("\n".join(cur))
            cur = [header, sep, row]
        else:
            cur.append(row)
    if len(cur) > 2:
        out.append("\n".join(cur))
    return out or [block.text]


def _split_list_block(block: Block, budget: int) -> list[str]:
    items: list[list[str]] = []
    cur: list[str] = []
    for line in block.lines:
        if re.match(r"^\s*([-*]\s+|\d+\.\s+)", line) and cur:
            items.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        items.append(cur)
    out, buf = [], []
    for item in items:
        trial = "\n".join(["\n".join(buf_item) for buf_item in buf] + ["\n".join(item)])
        if estimate_tokens(trial) > budget and buf:
            out.append("\n".join("\n".join(b) for b in buf))
            buf = [item]
        else:
            buf.append(item)
    if buf:
        out.append("\n".join("\n".join(b) for b in buf))
    return out or [block.text]


_SENT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_paragraph_block(block: Block, budget: int) -> list[str]:
    text = block.text
    sentences = _SENT_RE.split(text)
    out, cur = [], ""
    for s in sentences:
        trial = (cur + " " + s).strip() if cur else s
        if estimate_tokens(trial) > budget and cur:
            out.append(cur)
            cur = s
        else:
            cur = trial
    if cur:
        out.append(cur)
    return out or [text]


def _pack_blocks(blocks: list[Block], budget: int) -> list[str]:
    """Packs blocks into chunks of at most `budget` tokens; a block that alone exceeds the
    budget is split further (rule 4) -- except a code block, which is never split."""
    pieces: list[str] = []
    for b in blocks:
        if not b.text:
            continue
        if estimate_tokens(b.text) <= budget:
            pieces.append(b.text)
        elif b.kind == "table":
            pieces.extend(_split_table_block(b, budget))
        elif b.kind == "list":
            pieces.extend(_split_list_block(b, budget))
        elif b.kind == "para":
            pieces.extend(_split_paragraph_block(b, budget))
        else:  # code fence, never split
            pieces.append(b.text)

    packed: list[str] = []
    cur = ""
    for piece in pieces:
        trial = (cur + "\n\n" + piece).strip() if cur else piece
        if estimate_tokens(trial) > budget and cur:
            packed.append(cur)
            cur = piece
        else:
            cur = trial
    if cur:
        packed.append(cur)
    return packed


# --- top-level chunking -----------------------------------------------------------------------

def chunk_document(title: str, doc_id: str, lines: list[str], header_end: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    header_text_lines = ["- {}: {}".format(k, v) for k, v in _iter_header_fields(lines, header_end)]
    # Header chunk: title + the raw header block text as written (rule 1).
    header_body = "\n".join(lines[1:header_end]).strip()
    chunks.append(Chunk(0, "Header", "text", f"{title}\n\n{header_body}" if header_body else title, ""))

    for heading, body_start, body_end in _split_top_level(lines, header_end):
        section_lines = lines[body_start:body_end]
        section_text = "\n".join(section_lines).strip()
        if not section_text:
            continue
        if _looks_like_record(heading):
            # Employee-record-style "##" section: treat as a single retrievable unit, same
            # rule as a "###" unit (section 3.1: "employee record sets use one `##` section
            # per employee").
            _append_unit(chunks, heading, section_lines, is_code_bearing=has_code_fence(section_text))
            continue

        tokens = estimate_tokens(section_text)
        if tokens <= TOKEN_BUDGET or (has_code_fence(section_text) and not _has_h3(section_lines)):
            _append_unit(chunks, heading, section_lines, is_code_bearing=has_code_fence(section_text))
            continue

        intro_end, h3_units = _split_h3(section_lines, 0, len(section_lines))
        intro_lines = section_lines[:intro_end]
        intro_text = "\n".join(intro_lines).strip()
        if intro_text:
            for piece in _pack_blocks(_split_blocks(intro_lines), TOKEN_BUDGET):
                chunks.append(Chunk(0, heading, "text", piece, ""))

        for h3_heading, h3_start, h3_end in h3_units:
            u_lines = section_lines[h3_start:h3_end]
            u_text = "\n".join(u_lines).strip()
            if not u_text:
                continue
            sub_path = f"{heading} > {h3_heading}"
            u_has_code = has_code_fence(u_text)
            if estimate_tokens(u_text) <= TOKEN_BUDGET or u_has_code:
                _append_unit(chunks, sub_path, u_lines, is_code_bearing=u_has_code)
            else:
                for piece in _pack_blocks(_split_blocks(u_lines), TOKEN_BUDGET):
                    chunks.append(Chunk(0, sub_path, "text", piece, ""))

    for idx, c in enumerate(chunks):
        c.chunk_no = idx
    return chunks


def _has_h3(section_lines: list[str]) -> bool:
    return any(_H3_RE.match(l) for l in section_lines)


def _append_unit(chunks: list[Chunk], section_path: str, unit_lines: list[str], is_code_bearing: bool) -> None:
    text = "\n".join(unit_lines).strip()
    if is_code_bearing:
        chunks.append(Chunk(0, section_path, "code", text, strip_code_fences(text)))
    else:
        chunks.append(Chunk(0, section_path, "text", text, ""))


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Section 4.3: the description of a code-bearing unit is truncated to the 256-token
    limit (here, to whatever budget remains after the prefix). Truncates on word boundaries."""
    if max_tokens <= 0:
        return ""
    if estimate_tokens(text) <= max_tokens:
        return text
    words = text.split()
    lo, hi = 0, len(words)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if estimate_tokens(" ".join(words[:mid])) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1
    return " ".join(words[:lo])


def _iter_header_fields(lines: list[str], header_end: int):
    for line in lines[1:header_end]:
        m = _HEADER_FIELD_RE.match(line)
        if m:
            yield m.group(1).strip(), m.group(2).strip()


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    index_name: str
    title: str
    source_path: str
    chunk_no: int
    section_path: str
    kind: str
    body: str
    embed_text: str
    token_estimate: int
    content_hash: str
    entities: list[str] = field(default_factory=list)
    classification: Optional[str] = None
    category: Optional[str] = None
    owner: Optional[str] = None
    effective_date: Optional[str] = None
    version: Optional[str] = None
    applies_to: Optional[str] = None


def build_chunk_records(path: Path, rag_sources_root: Path, index_name: str) -> tuple[str, HeaderBlock, list[ChunkRecord]]:
    from app.rag.entities import chunk_entities, doc_subject_ids  # local import: avoids a cycle

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title, header, header_end = parse_header(lines)
    raw_chunks = chunk_document(title, header.doc_id, lines, header_end)
    subject_ids = doc_subject_ids(header.fields)

    records = []
    for c in raw_chunks:
        prefix = f"{title} ({header.doc_id}) | {c.section_path}" if c.section_path else f"{title} ({header.doc_id})"
        if c.kind == "code":
            suffix = _truncate_to_tokens(c.embed_text_suffix, MAX_EMBED_TOKENS - estimate_tokens(prefix))
            embed_text = f"{prefix}\n{suffix}" if suffix else prefix
        else:
            embed_text = f"{prefix}\n{c.body}" if c.section_path else c.body
        chunk_id = f"{header.doc_id}#{c.chunk_no:02d}"
        records.append(ChunkRecord(
            chunk_id=chunk_id,
            doc_id=header.doc_id,
            index_name=index_name,
            title=title,
            source_path=str(path.relative_to(rag_sources_root.parent)),
            chunk_no=c.chunk_no,
            section_path=c.section_path or "Header",
            kind=c.kind,
            body=c.body,
            embed_text=embed_text,
            token_estimate=estimate_tokens(embed_text),
            content_hash=hashlib.sha256(c.body.encode("utf-8")).hexdigest(),
            classification=header.fields.get("Classification"),
            category=header.fields.get("Category"),
            owner=header.fields.get("Owner"),
            effective_date=header.fields.get("Effective date"),
            version=header.fields.get("Version"),
            applies_to=header.fields.get("Applies to"),
            entities=chunk_entities(subject_ids, c.body),
        ))
    return title, header, records
