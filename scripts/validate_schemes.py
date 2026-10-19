import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Make "app" importable when running from the project root
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.config import SCHEMES_PATH

TOP_LEVEL_FIELDS = {
    "id": str, "name": str, "short_name": str, "aliases": list,
    "category": str, "ministry": str, "description": str,
    "benefit_type": str, "benefits": list, "eligibility": dict,
    "eligibility_text": list, "exclusions": list, "documents": list,
    "how_to_apply": list, "apply_url": str, "helpline": str,
    "deadline_info": str, "related_schemes": list,
    "source_url": str, "last_verified": str,
}

ELIGIBILITY_FIELDS = {
    "min_age", "max_age", "max_income", "gender", "occupation",
    "category", "states", "minority_required", "other_conditions",
}

VALID_CATEGORIES = {
    "agriculture", "health", "education", "pension",
    "housing", "women_child", "livelihood",
}
VALID_BENEFIT_TYPES = {
    "cash", "credit", "insurance", "free_services",
    "pension", "subsidy", "scholarship",
}
VALID_GENDERS = {None, "male", "female"}
VALID_CASTE_CATEGORIES = {None, "SC", "ST", "OBC", "General"}
NON_EMPTY_LISTS = {"aliases", "benefits", "eligibility_text", "documents", "how_to_apply"}

errors, warnings = [], []


def err(sid, msg):
    errors.append(f"[{sid}] {msg}")


def warn(sid, msg):
    warnings.append(f"[{sid}] {msg}")


def has_verify(value):
    """True if the string 'VERIFY' appears anywhere inside the value."""
    return "VERIFY" in json.dumps(value)


def check_record(rec, index):
    sid = rec.get("id", f"record #{index}")

    # 1. Required fields and types
    for field, ftype in TOP_LEVEL_FIELDS.items():
        if field not in rec:
            err(sid, f"missing field '{field}'")
        elif not isinstance(rec[field], ftype):
            err(sid, f"'{field}' should be {ftype.__name__}")

    for field in NON_EMPTY_LISTS:
        if isinstance(rec.get(field), list) and not rec[field]:
            err(sid, f"'{field}' is empty")

    # 2. Allowed values
    if rec.get("category") not in VALID_CATEGORIES:
        err(sid, f"invalid category '{rec.get('category')}'")
    if rec.get("benefit_type") not in VALID_BENEFIT_TYPES:
        err(sid, f"invalid benefit_type '{rec.get('benefit_type')}'")

    # 3. Eligibility block
    elig = rec.get("eligibility")
    if isinstance(elig, dict):
        missing = ELIGIBILITY_FIELDS - elig.keys()
        extra = elig.keys() - ELIGIBILITY_FIELDS
        if missing:
            err(sid, f"eligibility missing {sorted(missing)}")
        if extra:
            err(sid, f"eligibility has unknown keys {sorted(extra)}")

        if elig.get("gender") not in VALID_GENDERS:
            err(sid, f"invalid gender '{elig.get('gender')}'")
        if elig.get("category") not in VALID_CASTE_CATEGORIES:
            err(sid, f"invalid eligibility category '{elig.get('category')}'")

        lo, hi = elig.get("min_age"), elig.get("max_age")
        for name, val in (("min_age", lo), ("max_age", hi), ("max_income", elig.get("max_income"))):
            if val is not None and not isinstance(val, (int, float)):
                err(sid, f"'{name}' should be a number or null")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
            err(sid, "min_age is greater than max_age")

        if not isinstance(elig.get("states"), list) or not elig.get("states"):
            err(sid, "'states' should be a non-empty list (use [\"ALL\"] for nationwide)")
        if not isinstance(elig.get("minority_required"), bool):
            err(sid, "'minority_required' should be true or false")

    # 4. Leftover VERIFY markers
    if has_verify(rec):
        err(sid, "still contains 'VERIFY' markers")

    # 5. URLs and date
    for field in ("apply_url", "source_url"):
        val = rec.get(field, "")
        if isinstance(val, str) and not has_verify(val) and not val.startswith(("www.")):
            err(sid, f"'{field}' should start with http:// or https://")

    date = rec.get("last_verified", "")
    if isinstance(date, str) and not has_verify(date):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            err(sid, "last_verified should be in YYYY-MM-DD format")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                err(sid, f"last_verified '{date}' is not a real date")

    # 6. Soft checks
    if isinstance(rec.get("helpline"), str) and not rec["helpline"].strip():
        warn(sid, "helpline is empty")
    if isinstance(rec.get("aliases"), list) and rec.get("id"):
        if rec["id"] not in [a.lower() for a in rec["aliases"]] and rec.get("short_name", "").lower() not in [a.lower() for a in rec["aliases"]]:
            warn(sid, "neither id nor short_name appears in aliases")


def main():
    try:
        with open(SCHEMES_PATH, encoding="utf-8") as f:
            schemes = json.load(f)
    except FileNotFoundError:
        sys.exit(f"File not found: {SCHEMES_PATH}")
    except json.JSONDecodeError as e:
        sys.exit(f"Invalid JSON at line {e.lineno}, column {e.colno}: {e.msg}")

    if not isinstance(schemes, list):
        sys.exit("schemes.json must contain a single JSON array")

    # Per-record checks
    for i, rec in enumerate(schemes):
        if not isinstance(rec, dict):
            err(f"record #{i}", "is not an object")
            continue
        check_record(rec, i)

    # Cross-record checks
    ids = [r.get("id") for r in schemes if isinstance(r, dict)]
    id_set = set(ids)

    for sid in {x for x in ids if ids.count(x) > 1}:
        err(sid, "duplicate id")

    for rec in schemes:
        if not isinstance(rec, dict):
            continue
        sid = rec.get("id")
        for ref in rec.get("related_schemes", []):
            if ref not in id_set:
                err(sid, f"related_schemes points to unknown id '{ref}'")
            if ref == sid:
                err(sid, "related_schemes points to itself")

    # Alias collisions: the same alias used by several records
    alias_owners = {}
    for rec in schemes:
        if isinstance(rec, dict):
            for a in rec.get("aliases", []):
                alias_owners.setdefault(a.lower(), []).append(rec.get("id"))
    for alias, owners in alias_owners.items():
        if len(owners) > 1:
            warn("aliases", f"'{alias}' is shared by {owners} (fine if intentional, e.g. 'nsap')")

    # Report
    print(f"Checked {len(schemes)} records\n")
    if warnings:
        print(f"WARNINGS ({len(warnings)})")
        for w in warnings:
            print("  -", w)
        print()
    if errors:
        print(f"ERRORS ({len(errors)})")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()