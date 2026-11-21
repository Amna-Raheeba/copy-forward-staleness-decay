# Changelog

## 0.1.0 — 2026-11-21

- Initial release.
- Seeded longitudinal note generator: synthetic admissions whose
  findings onset and resolve on a ground-truth schedule the
  note-writer only partially observes; daily notes are built by
  copying, editing or dropping yesterday's problem-list spans under
  four declared copy policies (low_copy, standard, attentive,
  high_copy).
- Exact staleness labelling: every mention is scored against the
  known resolution day of its finding.
- Staleness analytics: stale prevalence by hospital day, survival
  curves and staleness half-life per finding type, harm profile
  (stale mention-days, phantom problems on the final day, mean
  stale age), and mention accuracy by span provenance (fresh /
  edited / copied) and by span age.
- Staleness detector combining copy provenance (span age, days
  present) with contradiction cues (a course-log resolution
  assertion the problem list ignores), benchmarked against a
  text-similarity-only baseline and age-only / cue-only ablations.
- Headline evaluation on 60 seeded admissions x 14 days under all
  four policies, CLI, Streamlit dashboard, and a reproduce script
  with a headline-drift guard.
