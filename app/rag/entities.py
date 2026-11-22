"""Entity-aware retrieval (04_rag_design.md section 8): regex patterns for exact identifiers,
and a lexicon built from document titles and chunk headings that maps a name mentioned in a
query back to its entity code.

This module has no network or database dependency and is usable standalone (it only needs
the chunk records the chunker already produced).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_LOCATION_CODES = {"RYD-OLY", "JED-THL", "RYD-MLQ", "DMM-FSL", "KHB-COR", "MED-QBA", "JED-OBH", "ABH-CTY", "RYD-DC"}
_PRODUCT_LINES = {"ELEC", "APPL", "FASH", "GROC", "BEAU", "SPRT", "KIDS", "HOME"}

_PATTERNS: dict[str, re.Pattern] = {
    "supplier_code": re.compile(r"\bSUP-\d{2}\b"),
    "supplier_contract": re.compile(r"\bSC-\d{4}-\d{3}\b"),
    "customer_code": re.compile(r"\bCUST-B\d{3}\b"),
    "customer_contract": re.compile(r"\bCC-\d{4}-\d{3}\b"),
    "sku": re.compile(r"\b(?:ELEC|APPL|FASH|GROC|BEAU|SPRT|KIDS|HOME)-\d{4}\b"),
    "employee_id": re.compile(r"\bEMP-\d{4}\b"),
    "document_id": re.compile(r"\b(?:KB-[A-Z]+-\d{2}|RT-\d{2}|DA-\d{2}|INV-\d{2})\b"),
    "pattern_id": re.compile(r"\b(?:DA|INV)-(?:SQL|PY)-\d{2}\b"),
}
_LOCATION_RE = re.compile(r"\b(?:" + "|".join(re.escape(c) for c in sorted(_LOCATION_CODES)) + r")\b")
_PRODUCT_LINE_RE = re.compile(r"\b(?:" + "|".join(_PRODUCT_LINES) + r")\b(?!-\d)")


def extract_pattern_entities(text: str) -> set[str]:
    """Section 8.1/8.3 step 1: find every entity code in `text` by pattern. Uses no LLM."""
    found: set[str] = set()
    for pattern in _PATTERNS.values():
        found.update(m.group(0) for m in pattern.finditer(text))
    found.update(m.group(0) for m in _LOCATION_RE.finditer(text))
    found.update(m.group(0) for m in _PRODUCT_LINE_RE.finditer(text))
    return found


def normalize_name(name: str) -> str:
    """Case-insensitive, hyphens and spaces normalized (section 8.2)."""
    name = name.lower().replace("-", " ")
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


# Matches a chunk heading that is itself a record: "EMP-0001 Abdulaziz Al-Rashid" or
# "GROC-0001 Qassim Gold Khalas Dates 1kg" (section 8.2's two record-heading examples).
_RECORD_HEADING_RE = re.compile(
    r"^(EMP-\d{4}|(?:ELEC|APPL|FASH|GROC|BEAU|SPRT|KIDS|HOME)-\d{4})\s+(.+)$"
)

_SUPPLIER_TITLE_RE = re.compile(r"^Supplier Contract\s+SC-\d{4}-\d{3}:\s*(.+)$")
_CUSTOMER_TITLE_RE = re.compile(r"^Customer Agreement\s+CC-\d{4}-\d{3}:\s*(.+)$")


@dataclass
class DocInfo:
    doc_id: str
    title: str
    header_fields: dict


def build_lexicon(docs: list[DocInfo], record_headings: list[tuple[str, str]]) -> dict[str, str]:
    """Builds the name -> code lexicon (section 8.2) from document titles, their header
    fields (Supplier code / Customer code / Location code / Product line code), and chunk
    headings that are themselves records (`record_headings`: list of (heading_text, code)
    pairs the caller already knows the code for, e.g. from an "## EMP-0001 Name" heading).
    """
    lex: dict[str, str] = {}

    def add(name: str, code: str) -> None:
        norm = normalize_name(name)
        if norm:
            lex[norm] = code

    for d in docs:
        f = d.header_fields
        if f.get("Supplier code"):
            m = _SUPPLIER_TITLE_RE.match(d.title)
            if m:
                add(m.group(1), f["Supplier code"])
        if f.get("Customer code"):
            m = _CUSTOMER_TITLE_RE.match(d.title)
            if m:
                add(m.group(1), f["Customer code"])
        if f.get("Location code"):
            # Branch titles are e.g. "Riyadh Olaya Flagship Branch Profile"; the location
            # name is the title with the trailing "Branch Profile" removed.
            add(re.sub(r"\s+Branch Profile$", "", d.title), f["Location code"])
        if f.get("Product line code"):
            # "Product Catalog: Consumer Electronics" -> "Consumer Electronics"
            add(re.sub(r"^Product Catalog:\s*", "", d.title), f["Product line code"])
        if f.get("Contract number"):
            add(d.title, f["Contract number"])
        # The bare document title is also searchable (e.g. "Returns and Refunds" -> KB-POL-09).
        add(d.title, d.doc_id)

    for heading, code in record_headings:
        m = _RECORD_HEADING_RE.match(heading.strip())
        if m:
            add(m.group(2), code)

    return lex


def resolve_lexicon_names(query: str, lexicon: dict[str, str]) -> set[str]:
    """Section 8.2: a full name in the query (normalized) is replaced by its entity code.
    Longer entries are checked first so a full company/person name wins over a short
    substring that happens to also be a lexicon key."""
    norm_query = normalize_name(query)
    found: set[str] = set()
    for name, code in sorted(lexicon.items(), key=lambda kv: -len(kv[0])):
        if name and name in norm_query:
            found.add(code)
    return found


def extract_query_entities(query: str, lexicon: dict[str, str]) -> set[str]:
    """Section 8.3 step 1: patterns plus the lexicon, run on the original query."""
    return extract_pattern_entities(query) | resolve_lexicon_names(query, lexicon)


def chunk_entities(doc_subject_ids: set[str], chunk_text: str) -> list[str]:
    """Section 4.4/8.4: a chunk's `entities` = its document's subject IDs plus every entity
    code found in its own text."""
    return sorted(doc_subject_ids | extract_pattern_entities(chunk_text))


def doc_subject_ids(header_fields: dict) -> set[str]:
    """Section 3.2: Supplier code, Customer code, Location code, Product line code and
    Contract number become a document's `subject_ids`."""
    ids = set()
    for key in ("Supplier code", "Customer code", "Location code", "Product line code", "Contract number"):
        v = header_fields.get(key)
        if v:
            ids.add(v)
    return ids
