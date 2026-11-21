"""Plain-text rendering of one admission's chart and its audit."""

from .detect import detector_score, flag_combined, mention_features
from .models import mention_is_stale


def render_admission_report(admission):
    lines = []
    lines.append(
        "Admission %d (%d days, policy %s)"
        % (admission.admission_id, admission.n_days, admission.policy)
    )
    lines.append("")
    lines.append("Ground truth:")
    for finding in admission.findings:
        resolution = (
            "resolves day %d" % finding.resolution_day
            if finding.resolution_day is not None
            else "active at discharge"
        )
        observed = (
            "noticed day %d" % finding.resolution_observed_day
            if finding.resolution_observed_day is not None
            else "never noticed"
        )
        lines.append(
            "  - %s: onset day %d, %s, resolution %s"
            % (finding.finding_type, finding.onset_day, resolution, observed)
        )
    lines.append("")
    lines.append("Daily problem lists (STALE = asserts a resolved finding):")
    for note in admission.notes:
        lines.append("  Day %d:" % note.day)
        if not note.mentions:
            lines.append("    (empty)")
        for mention in note.mentions:
            stale = mention_is_stale(admission, mention)
            features = mention_features(admission, mention)
            flagged = flag_combined(features)
            tags = []
            if stale:
                tags.append("STALE")
            if flagged:
                tags.append("detector-flagged")
            lines.append(
                "    - [%s] %s (span age %d, gen %d, score %.2f%s)"
                % (
                    mention.finding_type,
                    mention.text,
                    mention.span_age,
                    mention.generation,
                    detector_score(features),
                    ("; " + ", ".join(tags)) if tags else "",
                )
            )
    lines.append("")
    assertions = admission.resolution_assertions
    if assertions:
        lines.append("Course-log resolution assertions:")
        for day, fid in assertions:
            lines.append("  - day %d: %s" % (day, fid))
    return "\n".join(lines)
