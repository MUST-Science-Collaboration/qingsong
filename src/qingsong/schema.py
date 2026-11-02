"""Record schemas (docs/SPEC.md §4–§5). Unknown fields are errors; nothing is defaulted on reading
except empty lists and absent optional values."""

import datetime
import math
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LocalizedText = dict[str, str]
Maturity = Literal["concept", "draft", "agreed", "baselined"]
Lifecycle = Literal["current", "superseded", "withdrawn"]
Certainty = Literal["firm", "provisional", "tbc", "tbd"]
VerificationMethod = Literal["test", "analysis", "inspection", "demonstration", "review_of_design"]
ChangeClass = Literal["editorial", "value", "reallocate"]
EventKind = Literal[
    "created",
    "imported",
    "revised",
    "approved",
    "confirmed",
    "superseded",
    "withdrawn",
    "renumbered",
    "released",
]
NodeKind = Literal["product", "work", "context"]

maturity_order: dict[str, int] = {"concept": 0, "draft": 1, "agreed": 2, "baselined": 3}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HistoryEvent(StrictModel):
    revision: int
    date: datetime.date
    by: str
    event: EventKind
    change_class: ChangeClass | None = None
    summary: str
    decision: str | None = None
    via: str | None = None


class Alias(StrictModel):
    id: str
    kind: Literal["legacy", "vendor", "external"]
    document: str
    from_version: str | None = None
    to_version: str | None = None
    note: str | None = None


class Link(StrictModel):
    id: str
    normative_revision: int


class SourceCitation(StrictModel):
    source: str
    locator: str


class Tolerance(StrictModel):
    plus: float
    minus: float


class ValueSlot(StrictModel):
    quantity: str | None = None
    relation: Literal["eq", "le", "lt", "ge", "gt", "range", "approx"]
    value: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    tolerance: Tolerance | None = None
    unit: str | None = None
    certainty: Certainty
    issue: str | None = None
    condition: LocalizedText | None = None

    @model_validator(mode="after")
    def check_numbers(self) -> "ValueSlot":
        for number in (self.value, self.minimum, self.maximum):
            if number is not None and not math.isfinite(number):
                raise ValueError("values must be finite numbers")
        if self.tolerance and (self.tolerance.plus < 0 or self.tolerance.minus < 0):
            raise ValueError("tolerances are given as non-negative magnitudes")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum is larger than maximum")
        if self.certainty == "tbd":
            return self
        if self.relation == "range":
            if self.minimum is None or self.maximum is None:
                raise ValueError("a range needs minimum and maximum")
        elif self.value is None:
            raise ValueError(f"relation {self.relation} needs a value (or certainty tbd)")
        return self


class Verification(StrictModel):
    methods: list[VerificationMethod] = Field(min_length=1)
    level: str | None = None
    criteria: LocalizedText


class Approval(StrictModel):
    by: str
    date: datetime.date
    ref: str
    normative_revision: int
    text_hash: str


class TranslationState(StrictModel):
    source_hash: str
    status: Literal["machine", "reviewed"]
    by: str | None = None
    date: datetime.date | None = None


class Variant(StrictModel):
    source: str
    label: str
    relation: Literal["vendor_stated", "proposed", "rejected"]
    statement: LocalizedText | None = None
    values: dict[str, ValueSlot] = Field(default_factory=dict)


class RecordBase(StrictModel):
    id: str
    type: str
    title: LocalizedText
    lifecycle: Lifecycle
    superseded_by: list[str] = Field(default_factory=list)
    aliases: list[Alias] = Field(default_factory=list)
    revision: int
    normative_revision: int
    normative_hash: str
    history: list[HistoryEvent]
    stamp: str


class Requirement(RecordBase):
    type: Literal["requirement"]
    statement: LocalizedText
    values: dict[str, ValueSlot] = Field(default_factory=dict)
    rationale: LocalizedText | None = None
    notes: LocalizedText | None = None
    suggestions: LocalizedText | None = None
    justification: LocalizedText | None = None
    justified_by: str | None = None
    level: str
    allocated_to: str
    interface: str | None = None
    derives_from: list[Link] = Field(default_factory=list)
    constrained_by: list[Link] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    sources: list[SourceCitation] = Field(default_factory=list)
    verification: Verification | None = None
    maturity: Maturity
    approval: Approval | None = None
    text_origin: str
    translation: dict[str, TranslationState] = Field(default_factory=dict)
    variants: list[Variant] = Field(default_factory=list)


class FigureFile(StrictModel):
    path: str
    sha256: str

    @field_validator("path")
    @classmethod
    def plain_name(cls, path: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", path):
            raise ValueError("an image is a plain file name next to the figure record")
        return path


class Provenance(StrictModel):
    script: str | None = None
    repository: str | None = None
    version: str | None = None
    data: str | None = None
    date: datetime.date | None = None
    note: str | None = None


class Figure(RecordBase):
    type: Literal["figure"]
    caption: LocalizedText
    alt: LocalizedText | None = None
    files: list[FigureFile]
    provenance: Provenance | None = None
    text_origin: str
    translation: dict[str, TranslationState] = Field(default_factory=dict)


class Condition(RecordBase):
    type: Literal["condition"]
    node: str
    description: LocalizedText | None = None
    values: dict[str, ValueSlot] = Field(default_factory=dict)
    evidence_basis: Literal["measured", "modelled", "assumed"]
    date: datetime.date | None = None
    sources: list[SourceCitation] = Field(default_factory=list)


class Quantity(RecordBase):
    type: Literal["quantity"]
    symbol: str | None = None
    dimension: str
    unit: str
    kpp: bool = False
    description: LocalizedText | None = None
    # A condition to be withstood (e.g. an operating temperature range): a child's range must
    # cover its parent's instead of lying inside it (docs/SPEC.md §10).
    environmental: bool | None = None


TextHash = Annotated[str, Field(pattern=r"^([0-9a-f]{16})?$")]
IssueKind = Literal[
    "tbd", "tbc", "provisional", "tbj", "wording", "translation", "question", "conflict"
]


class ProposedChange(StrictModel):
    record: str
    field: Literal[
        "title", "statement", "rationale", "notes", "suggestions", "verification.criteria"
    ]
    text: LocalizedText = Field(min_length=1)
    base: dict[str, TextHash] = Field(default_factory=dict)


class Proposal(StrictModel):
    number: int = Field(ge=1)
    date: datetime.date
    by: str
    via: str | None = None
    summary: LocalizedText
    change_class: ChangeClass = "editorial"
    status: Literal["proposed", "accepted", "rejected"]
    reason: LocalizedText | None = None
    changes: list[ProposedChange] = Field(default_factory=list)


class Issue(RecordBase):
    type: Literal["issue"]
    kind: IssueKind
    status: Literal["open", "closed"]
    description: LocalizedText
    owner: str | None = None
    due: str | None = None
    closure_plan: LocalizedText | None = None
    records: list[str] = Field(default_factory=list)
    # Fields added after records existed default to None, so that existing stamps stay valid.
    rule: str | None = None
    proposals: list[Proposal] | None = None
    outcome: Literal["fixed", "accepted_as_written", "answered", "withdrawn"] | None = None
    accepted: dict[str, TextHash] | None = None
    resolution: LocalizedText | None = None


class Decision(RecordBase):
    type: Literal["decision"]
    date: datetime.date
    by: str
    statement: LocalizedText
    rationale: LocalizedText | None = None
    records: list[str] = Field(default_factory=list)


class Source(RecordBase):
    type: Literal["source"]
    kind: Literal["project_document", "standard", "publication", "vendor_document", "dataset"]
    number: str | None = None
    version: str | None = None
    date: datetime.date | None = None
    file: str | None = None
    sha256: str | None = None
    location: str | None = None
    url: str | None = None


class Interface(RecordBase):
    type: Literal["interface"]
    owner_end: str
    other_end: str
    description: LocalizedText | None = None
    values: dict[str, ValueSlot] = Field(default_factory=dict)


class Evidence(StrictModel):
    kind: Literal["file", "source", "analysis", "report"]
    reference: str
    note: str | None = None


class VerificationRecord(RecordBase):
    type: Literal["verification"]
    requirement: str
    requirement_normative_revision: int
    method: VerificationMethod
    status: Literal[
        "planned", "predicted", "compliant", "partially_compliant", "non_compliant", "waived"
    ]
    evidence: list[Evidence] = Field(default_factory=list)


class Waiver(RecordBase):
    type: Literal["waiver"]
    requirement: str
    requirement_normative_revision: int
    scope: LocalizedText
    reason: LocalizedText
    approver: str
    expires: datetime.date | None = None


class Baseline(RecordBase):
    type: Literal["baseline"]
    tag: str
    review: str
    records: list[str] = Field(default_factory=list)


class Role(StrictModel):
    role: LocalizedText
    person: str


class Release(StrictModel):
    version: str
    date: datetime.date
    summary: LocalizedText
    by: str | None = None
    note: LocalizedText | None = None
    tag: str | None = None
    made_with_qingsong: bool
    engine: str | None = None


class FrontMatter(StrictModel):
    roles: list[Role] = Field(default_factory=list)
    reference_documents: list[str] = Field(default_factory=list)
    bibliography: list[str] = Field(default_factory=list)
    acronyms: list[str] = Field(default_factory=list)


class TableBlock(StrictModel):
    caption: LocalizedText | None = None
    header: list[LocalizedText]
    rows: list[list[LocalizedText]]

    @model_validator(mode="after")
    def check_widths(self) -> "TableBlock":
        for index, row in enumerate(self.rows):
            if len(row) != len(self.header):
                raise ValueError(
                    f"table row {index + 1} has {len(row)} cells, the header {len(self.header)}"
                )
        return self


class DefinitionsBlock(StrictModel):
    terms: list[str]
    caption: LocalizedText | None = None


class Block(StrictModel):
    section: "Section | None" = None
    text: LocalizedText | None = None
    requirement: str | None = None
    figure: str | None = None
    table: TableBlock | None = None
    definitions: DefinitionsBlock | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "Block":
        present = [name for name in type(self).model_fields if getattr(self, name) is not None]
        if len(present) != 1:
            raise ValueError(
                f"a block holds exactly one of section, text, requirement, figure, "
                f"table, definitions; found {present or 'none'}"
            )
        return self


class Section(StrictModel):
    key: str
    title: LocalizedText
    blocks: list[Block] = Field(default_factory=list)


Block.model_rebuild()


class Document(RecordBase):
    type: Literal["document"]
    scope: list[str] = Field(default_factory=list)
    front: FrontMatter = Field(default_factory=FrontMatter)
    outline: list[Block] = Field(default_factory=list)
    releases: list[Release] = Field(default_factory=list)


Record = Annotated[
    Requirement
    | Figure
    | Condition
    | Quantity
    | Issue
    | Decision
    | Source
    | Interface
    | VerificationRecord
    | Waiver
    | Baseline
    | Document,
    Field(discriminator="type"),
]

record_classes: dict[str, type[RecordBase]] = {
    "requirement": Requirement,
    "figure": Figure,
    "condition": Condition,
    "quantity": Quantity,
    "issue": Issue,
    "decision": Decision,
    "source": Source,
    "interface": Interface,
    "verification": VerificationRecord,
    "waiver": Waiver,
    "baseline": Baseline,
    "document": Document,
}

record_folders: dict[str, str] = {
    "requirement": "requirements",
    "figure": "figures",
    "condition": "conditions",
    "quantity": "quantities",
    "issue": "issues",
    "decision": "decisions",
    "source": "sources",
    "interface": "interfaces",
    "verification": "verifications",
    "waiver": "waivers",
    "baseline": "baselines",
    "document": "documents",
}
folders_with_system: set[str] = {"requirement", "figure"}


class Node(StrictModel):
    node: str
    names: LocalizedText
    kind: NodeKind
    status: Literal["active", "placeholder", "retired"]
    structural_code: str | None = None
    text_origin: str | None = None
    description: LocalizedText | None = None
    owners: list[str] = Field(default_factory=list)
    design_stage: str | None = None
    note: str | None = None
    children: list["Node"] = Field(default_factory=list)


class TreeFile(Node):
    parent: str | None = None


class Person(StrictModel):
    name: str
    organization: str | None = None
    github: str | None = None
    email: str | None = None
    languages: list[str] = Field(default_factory=list)
    approver: bool = False


class PeopleFile(StrictModel):
    people: dict[str, Person]

    @field_validator("people")
    @classmethod
    def check_ids(cls, people: dict[str, Person]) -> dict[str, Person]:
        for person_id in people:
            if not re.fullmatch(r"[a-z][a-z0-9_]*", person_id):
                raise ValueError(f"person ID {person_id!r} must be snake_case")
        return people


class GlossaryEntry(StrictModel):
    kind: Literal["acronym", "term", "symbol"]
    text: str | None = None
    expansion: LocalizedText | None = None
    definition: LocalizedText | None = None


class GlossaryFile(StrictModel):
    terms: dict[str, GlossaryEntry] = Field(default_factory=dict)


class ProjectConfig(StrictModel):
    code: str
    names: LocalizedText


class LanguageConfig(StrictModel):
    reference: str
    second: str
    default_text_origin: str
    bilingual_fields: list[str]


class LevelConfig(StrictModel):
    name: str
    names: LocalizedText


class VaultConfig(StrictModel):
    project: ProjectConfig
    languages: LanguageConfig
    levels: list[LevelConfig]
    top_namespaces: dict[str, str]
    related: dict[str, str] = Field(default_factory=dict)
    tree_order: list[str] = Field(default_factory=list)
    documents: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_levels(self) -> "VaultConfig":
        names = [level.name for level in self.levels]
        if len(set(names)) != len(names):
            raise ValueError("level names must be unique")
        for namespace, level in self.top_namespaces.items():
            if level not in names:
                raise ValueError(f"top namespace {namespace} names unknown level {level}")
        return self

    @property
    def level_rank(self) -> dict[str, int]:
        return {level.name: index for index, level in enumerate(self.levels)}


def plain(data: Any) -> Any:
    """Convert ruamel containers to plain Python containers."""
    if isinstance(data, dict):
        return {str(key): plain(value) for key, value in data.items()}
    if isinstance(data, list):
        return [plain(value) for value in data]
    return data
