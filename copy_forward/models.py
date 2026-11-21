"""Data model for the copy-forward staleness simulation.

An admission is a sequence of daily notes. Each note carries a problem
list of *mentions* -- one span of text per finding the writer believes
is still active. Every finding also has a ground-truth course the
writer only partially observes: an onset day and a resolution day.
A mention that asserts a finding is active on or after its resolution
day is *stale*, and the gap is exactly measurable because the truth
schedule is generated, not inferred.

Provenance is tracked the way a chart reviewer could see it: each
mention knows the day its exact span text was born (span_birth_day),
how many copy hops it has survived (generation), and the first day the
finding was ever written (first_day). Resolution assertions live in a
separate chart-level course log -- which is precisely why a copied
problem-list mention can contradict them.
"""

from dataclasses import dataclass, field

# Finding types with declared simulation parameters.
# hazard: per-day probability that an active finding resolves
#         (expected true duration is roughly 1 / hazard days).
# prevalence: probability an admission includes this finding at all.
# copy_mult: multiplier on the policy's base copy probability --
#         some findings are stickier in the chart than others.
FINDING_TYPES = {
    "fever": {
        "label": "Fever",
        "hazard": 0.40,
        "prevalence": 0.55,
        "copy_mult": 1.00,
        "spans": [
            "Fever to 38.9 C, ongoing",
            "Febrile, temp 38.9 C",
            "Fever, presumed infectious source",
        ],
    },
    "delirium": {
        "label": "Delirium",
        "hazard": 0.45,
        "prevalence": 0.30,
        "copy_mult": 0.95,
        "spans": [
            "Acute delirium, CAM positive",
            "Delirium, fluctuating attention",
            "Acute confusional state",
        ],
    },
    "acute_kidney_injury": {
        "label": "Acute kidney injury",
        "hazard": 0.28,
        "prevalence": 0.35,
        "copy_mult": 1.00,
        "spans": [
            "AKI, creatinine rising",
            "Acute kidney injury, oliguric",
            "AKI on CKD, monitoring fluids",
        ],
    },
    "wound_infection": {
        "label": "Wound infection",
        "hazard": 0.24,
        "prevalence": 0.30,
        "copy_mult": 1.05,
        "spans": [
            "Surgical wound infection, on antibiotics",
            "Wound infection, erythema at margins",
            "Infected wound, daily dressings",
        ],
    },
    "pneumonia": {
        "label": "Pneumonia",
        "hazard": 0.17,
        "prevalence": 0.40,
        "copy_mult": 1.05,
        "spans": [
            "Hospital-acquired pneumonia, day of therapy noted",
            "Pneumonia, right lower lobe infiltrate",
            "Pneumonia, on IV antibiotics",
        ],
    },
    "pleural_effusion": {
        "label": "Pleural effusion",
        "hazard": 0.15,
        "prevalence": 0.35,
        "copy_mult": 1.10,
        "spans": [
            "Left pleural effusion, moderate",
            "Pleural effusion, tracking size",
            "Bilateral pleural effusions, small",
        ],
    },
    "anemia": {
        "label": "Anemia",
        "hazard": 0.11,
        "prevalence": 0.45,
        "copy_mult": 1.10,
        "spans": [
            "Anemia, Hb trending down",
            "Normocytic anemia, workup pending",
            "Anemia, transfuse if symptomatic",
        ],
    },
    "pressure_injury": {
        "label": "Pressure injury",
        "hazard": 0.09,
        "prevalence": 0.25,
        "copy_mult": 1.15,
        "spans": [
            "Stage 2 pressure injury, sacrum",
            "Pressure injury, turning schedule",
            "Sacral pressure injury, wound care",
        ],
    },
}

TYPE_ORDER = sorted(FINDING_TYPES.keys())


def span_text(finding_type, variant):
    """Deterministic span text for a finding type and variant index."""
    spans = FINDING_TYPES[finding_type]["spans"]
    return spans[variant % len(spans)]


@dataclass
class Finding:
    """Ground truth for one finding instance in one admission."""

    finding_id: str
    finding_type: str
    onset_day: int
    # First day the finding is NO LONGER true; None = still active at
    # discharge.
    resolution_day: object = None
    # Day the writer noticed the resolution; None = never noticed.
    resolution_observed_day: object = None
    first_written_day: object = None

    def is_active(self, day):
        if day < self.onset_day:
            return False
        if self.resolution_day is not None and day >= self.resolution_day:
            return False
        return True

    def is_stale_on(self, day):
        """True if asserting this finding active on `day` is false."""
        return self.resolution_day is not None and day >= self.resolution_day


@dataclass
class Mention:
    """One problem-list span in one day's note."""

    finding_id: str
    finding_type: str
    day: int
    text: str
    variant: int
    span_birth_day: int
    first_day: int
    generation: int
    written_today: bool
    # How this span came to be in today's note:
    # "new" (first written today), "recheck" (rewritten after the
    # writer re-examined the patient), "edit" (reworded in place,
    # no re-examination), "copy" (carried forward verbatim).
    origin: str = "copy"

    @property
    def span_age(self):
        """Days since this exact span text was (re)written."""
        return self.day - self.span_birth_day

    @property
    def copied(self):
        """True if the span survived at least one copy hop."""
        return self.generation > 0


@dataclass
class DayNote:
    day: int
    mentions: list = field(default_factory=list)


@dataclass
class Admission:
    """One synthetic admission: ground truth plus the written chart."""

    admission_id: int
    n_days: int
    policy: str
    findings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    # Chart-level course log: (day, finding_id) resolution assertions.
    resolution_assertions: list = field(default_factory=list)

    def finding_by_id(self, finding_id):
        for finding in self.findings:
            if finding.finding_id == finding_id:
                return finding
        raise KeyError(finding_id)

    def note_for_day(self, day):
        for note in self.notes:
            if note.day == day:
                return note
        raise KeyError(day)

    def all_mentions(self):
        out = []
        for note in self.notes:
            out.extend(note.mentions)
        return out

    def assertion_days(self, finding_id):
        return sorted(
            day for (day, fid) in self.resolution_assertions if fid == finding_id
        )


def mention_is_stale(admission, mention):
    """Ground-truth label: does this mention assert a resolved finding?"""
    finding = admission.finding_by_id(mention.finding_id)
    return finding.is_stale_on(mention.day)


def mention_to_dict(mention):
    return {
        "finding_id": mention.finding_id,
        "finding_type": mention.finding_type,
        "day": mention.day,
        "text": mention.text,
        "variant": mention.variant,
        "span_birth_day": mention.span_birth_day,
        "first_day": mention.first_day,
        "generation": mention.generation,
        "written_today": mention.written_today,
        "origin": mention.origin,
    }


def finding_to_dict(finding):
    return {
        "finding_id": finding.finding_id,
        "finding_type": finding.finding_type,
        "onset_day": finding.onset_day,
        "resolution_day": finding.resolution_day,
        "resolution_observed_day": finding.resolution_observed_day,
        "first_written_day": finding.first_written_day,
    }


def admission_to_dict(admission):
    return {
        "admission_id": admission.admission_id,
        "n_days": admission.n_days,
        "policy": admission.policy,
        "findings": [finding_to_dict(f) for f in admission.findings],
        "notes": [
            {"day": note.day, "mentions": [mention_to_dict(m) for m in note.mentions]}
            for note in admission.notes
        ],
        "resolution_assertions": [
            [day, fid] for (day, fid) in admission.resolution_assertions
        ],
    }


def admission_from_dict(data):
    findings = [
        Finding(
            finding_id=f["finding_id"],
            finding_type=f["finding_type"],
            onset_day=f["onset_day"],
            resolution_day=f["resolution_day"],
            resolution_observed_day=f["resolution_observed_day"],
            first_written_day=f["first_written_day"],
        )
        for f in data["findings"]
    ]
    notes = []
    for note_data in data["notes"]:
        mentions = [Mention(**m) for m in note_data["mentions"]]
        notes.append(DayNote(day=note_data["day"], mentions=mentions))
    return Admission(
        admission_id=data["admission_id"],
        n_days=data["n_days"],
        policy=data["policy"],
        findings=findings,
        notes=notes,
        resolution_assertions=[(d, fid) for (d, fid) in data["resolution_assertions"]],
    )
