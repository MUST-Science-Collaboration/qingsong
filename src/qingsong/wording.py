"""Relation words next to a number or a value slot (docs/SPEC.md §5.2). Shared by the slot move,
which refuses a literal with such a word outside it, and by the check that flags a slot whose sign
is said twice ("at least ≥ 40 %")."""

import re

# Relation words that, next to a literal but outside it, would change what the number means.
neighbour_words = {
    "en": (
        "at least",
        "at most",
        "up to",
        "no more than",
        "no less than",
        "not more than",
        "not less than",
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
        "per",
        "each",
        "every",
        "total",
        "average",
        "mean",
        "median",
        "rms",
        "peak",
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
        "每",
        "平均",
        "累计",
        "总",
    ),
}


def neighbour_problem(text: str, start: int, end: int, language: str) -> str | None:
    """A relation word right before or after the literal, outside it."""
    before = text[max(0, start - 24) : start].casefold()
    after = text[end : end + 24].casefold()
    for word in neighbour_words.get(language, ()):
        if language == "zh":
            if before.rstrip().endswith(word) or after.lstrip().startswith(word):
                return word
        else:
            last_words = " ".join(re.findall(r"[a-z]+", before)[-3:])
            first_words = " ".join(re.findall(r"[a-z]+", after)[:2])
            if re.search(rf"\b{re.escape(word)}$", last_words) or re.search(
                rf"^{re.escape(word)}\b", first_words
            ):
                return word
    return None
