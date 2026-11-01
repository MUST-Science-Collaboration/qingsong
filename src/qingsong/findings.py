"""Check results (docs/SPEC.md §10)."""

from dataclasses import asdict, dataclass

severity_order = {"error": 0, "warning": 1, "info": 2}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    message: str
    record: str | None = None
    file: str | None = None
    fix: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)

    def line(self) -> str:
        where = self.record or self.file or "vault"
        text = f"{self.severity.upper():7s} {self.rule:34s} {where}: {self.message}"
        return text + (f"\n        fix: {self.fix}" if self.fix else "")
