"""Words next to a number or a value slot (docs/SPEC.md §5.2).

Relation words say what a number is: a limit, a range, an approximation. Qualifiers say what it
counts: per item, in total, on average. The slot move refuses a literal with either kind just
outside it, so that the slot's data says what the sentence says. The check for a relation said
twice ("at least ≥ 40 %") uses the relation words only."""

import re

relation_words = {
    "en": (
        "at least",
        "at most",
        "up to",
        "no more than",
        "no less than",
        "no fewer than",
        "no greater than",
        "not more than",
        "not less than",
        "not exceed",
        "not exceeding",
        "more than",
        "less than",
        "fewer than",
        "greater than",
        "smaller than",
        "exceed",
        "exceeds",
        "exceeding",
        "below",
        "above",
        "under",
        "over",
        "between",
        "within",
        "approximately",
        "about",
        "around",
        "roughly",
        "nearly",
        "almost",
        "maximum",
        "minimum",
        "max",
        "min",
        "not",
    ),
    "zh": (
        "不小于",
        "不大于",
        "不低于",
        "不高于",
        "不少于",
        "不多于",
        "不超过",
        "至少",
        "至多",
        "最多",
        "最少",
        "以上",
        "以下",
        "以内",
        "超过",
        "低于",
        "高于",
        "大于",
        "小于",
        "多于",
        "少于",
        "大约",
        "约",
        "左右",
    ),
}
relation_signs = (">=", "<=", "≥", "≤", ">", "<", "≈", "~")
qualifier_words = {
    "en": ("per", "each", "every", "total", "average", "mean", "median", "rms", "peak"),
    "zh": ("每", "平均", "累计", "总"),
}


def neighbour_problem(
    text: str, start: int, end: int, language: str, qualifiers: bool = True
) -> str | None:
    """A relation word (and, with `qualifiers`, a qualifier) right before or after the span."""
    words = relation_words.get(language, ()) + (
        qualifier_words.get(language, ()) if qualifiers else ()
    )
    before = text[max(0, start - 24) : start].casefold()
    after = text[end : end + 24].casefold()
    stripped_before, stripped_after = before.rstrip(), after.lstrip()
    for sign in relation_signs:
        if stripped_before.endswith(sign) or stripped_after.startswith(sign):
            return sign
    for word in words:
        if language == "zh":
            if stripped_before.endswith(word) or stripped_after.startswith(word):
                return word
        else:
            last_words = " ".join(re.findall(r"[a-z]+", before)[-3:])
            first_words = " ".join(re.findall(r"[a-z]+", after)[:2])
            if re.search(rf"\b{re.escape(word)}$", last_words) or re.search(
                rf"^{re.escape(word)}\b", first_words
            ):
                return word
    return None
