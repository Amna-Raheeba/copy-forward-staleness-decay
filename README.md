# Copy-Forward Staleness Decay

Chart lore, quantified: a seeded simulator of copy-forward clinical
documentation that measures **how long resolved findings persist in
notes after they stop being true** — the staleness half-life of
copied text, and the accuracy gap between copied and freshly
written spans.

## 1. What it is

Clinicians write today's note by copying yesterday's. The copied
problem list is convenient and mostly right — but when a finding
resolves, its copied span often keeps asserting it for days. That
false content is "chart lore": everyone downstream treats the note
as current, and the note is quietly lying. Observational studies
can count how much text is copied; they cannot say how much of it
is *stale*, because nobody recorded the moment each finding
actually resolved.

This tool can, because it generates the truth first. It:

1. simulates synthetic admissions whose findings onset and resolve
   on a ground-truth schedule the note-writer only partially
   observes;
2. builds each day's note the way copy-forward really works —
   yesterday's spans are copied verbatim, edited, or dropped, and
   resolutions are noticed late, partially, or never;
3. labels every mention exactly against the known resolution day
   and measures stale prevalence, the staleness half-life per
   finding type, and the harm profile of each copy policy;
4. benchmarks a staleness detector that combines copy provenance
   (span age) with contradiction cues (the course log already said
   "resolved"; the problem list never got the memo) against the
   text-similarity-only baseline the copy-paste literature implies.

Everything is offline, deterministic and seeded. Pure Python
standard library; no API keys, no model downloads, no network. All
clinical content is synthetic — no real patient data anywhere.

## 2. The novel mechanism

Two ideas, neither of which exists in the copy-paste literature:

**A seeded resolution ground truth.** Each finding has a drawn
onset day and resolution day; the writer observes resolutions only
probabilistically, and even an observed resolution is written to
the course log while the problem-list span survives with
probability 0.35. Staleness is therefore not estimated — it is
*known*, per mention, per day. That makes two new quantities
measurable: the **staleness half-life** (once a finding resolves,
how long until half of its copied spans have stopped asserting it)
and the **accuracy decay by provenance** (fresh vs edited vs
copied spans scored against truth).

**Provenance × contradiction detection.** The detector scores each
span from chart-visible evidence only: how old the exact span text
is, how long the finding has sat on the problem list, and whether
the chart already asserts its resolution elsewhere. Text
similarity — the signal prior copy-paste work uses — is scored as
the baseline, and it cannot do this job: most verbatim copies are
still true, so flagging copies flags the living along with the
dead.

## 3. Prior art and the differentiator

Copy-paste research is observational. Wang et al. (JAMA Internal
Medicine) measured text provenance in real notes (46% of text
copied from earlier notes); a CHEST ICU study linked copied
content to documentation errors. Both are valuable and both stop
at counting copies or auditing errors by hand: real charts carry
no resolution ground truth, so staleness itself is never measured,
no half-life exists, and no detector is benchmarked. This project
is the seeded counterpart: a simulator with known resolution
times, exact staleness labels, a half-life per finding type, and
a detector scored against the similarity baseline on the same
labelled corpus.

## 4. Headline results (measured)

60 seeded admissions × 14 days under each of four copy policies
(seed 20261121; reproduce with
`python scripts/reproduce_results.py`). Full numbers in
`results/HEADLINE.md` and `results/evaluation_summary.md`.

**Staleness under the standard policy (copy probability 0.75):**

- Stale prevalence climbs from 0% on day 1 to **31.6% of the
  problem list by day 7** and is still **28.6% on day 14** —
  nearly a third of what the note asserts is no longer true.
- The overall staleness **half-life is 1.43 days**: half of
  resolved findings stop being asserted within about a day and a
  half, but the survival tail is long (3.5% still asserted 8 days
  after resolution). Per type, half-lives run from 0.7 days
  (pressure injury) to 1.9 days (fever).

**Accuracy decays with provenance:**

- Freshly written spans (written at onset or after the writer
  re-examines the patient): **100.0%** accurate — by construction
  of the writer model, and stated as such.
- Copied spans: **72.7%** accurate. Edited spans — reworded in
  place without re-examination: **68.0%** accurate, *worse* than
  copying. Rewording launders the provenance signal while keeping
  the falsehood.
- By span age, accuracy falls from 0.92 on the day a span is
  written to 0.63 for spans six or more days old.

**Detector vs baseline (standard policy, 1,023 mentions, 221 stale):**

| Detector | Precision | Recall | F1 |
|---|---|---|---|
| Provenance × contradiction | 0.405 | 0.561 | **0.471** |
| Text similarity only (baseline) | 0.273 | 0.887 | 0.417 |
| Age only | 0.305 | 0.475 | 0.372 |
| Contradiction cue only | 1.000 | 0.217 | 0.357 |

The similarity baseline has the best recall and nearly the worst
precision: it flags every verbatim copy, and 73% of its flags are
findings that are still true. The cue alone is never wrong (a
course-log resolution the problem list ignores is stale by
construction) but fires rarely. Combining provenance with the cue
beats both — modestly, and the modesty is itself a result: without
a contradiction cue, an old-but-live span and an old-and-stale
span look identical in the chart, and no threshold separates them
(a grid search over detector weights on this corpus found nothing
better than the declared rule by more than 0.002 F1).

**Copy policy is the lever (harm per admission):**

| Policy | Stale mention-days | Stale share | Phantom problems, final day |
|---|---|---|---|
| low_copy (copy 0.50) | 1.08 | 0.128 | 0.02 |
| standard (copy 0.75) | 3.68 | 0.216 | 0.17 |
| attentive (copy 0.75, observe 0.90) | 1.22 | 0.095 | 0.00 |
| high_copy (copy 0.92) | 7.63 | 0.362 | 0.30 |

Copying more multiplies stale content seven-fold from low to
high; paying attention at the same copy rate cuts it by two
thirds. The harm is a behaviour parameter, not a constant.

## 5. How it works

1. `copy_forward/generate.py` — the longitudinal note generator:
   ground-truth finding courses, four declared copy policies,
   partial resolution observation, course-log assertions that the
   problem list can fail to follow.
2. `copy_forward/measure.py` — exact staleness labels, prevalence
   by day, survival curves and half-lives, harm profile, accuracy
   by provenance and span age.
3. `copy_forward/detect.py` — chart-visible features (span age,
   days present, verbatim-copy flag, contradiction cue), the
   combined detector, the similarity baseline, and the ablations.
4. `copy_forward/evaluate.py` — the headline experiment across
   all four policies, result files, and the drift guard the
   reproduce script checks.

## 6. Run it

```bash
pip install -r requirements.txt
python -m copy_forward demo       # one admission, audited day by day
python -m copy_forward audit      # detector scores on a seeded batch
python -m copy_forward evaluate   # full experiment, writes results/
python scripts/reproduce_results.py   # verify the headline numbers
python scripts/build_cases.py     # rebuild data/demo_admission.json
streamlit run app.py              # dashboard: timeline, curves, results
pytest                            # 60 tests
```

## 7. Honest limits

- All admissions are synthetic and seeded. Copy, edit, drop,
  recheck and observation probabilities are declared parameters,
  not measurements of any real EHR or clinician population; the
  prevalences and half-lives quantify the mechanism under those
  parameters, not any hospital's chart lore.
- Fresh-span accuracy of 100% is a property of the writer model
  (fresh text is only written after patient contact), not an
  empirical claim about real documentation.
- Findings are single episodes: a finding never recurs within an
  admission, which is what makes the contradiction cue perfectly
  precise here. Real charts have recurrences, and a real cue
  would not be.
- Notes are problem-list spans, not prose; section structure,
  hedging language and authorship changes are out of scope.
- The detector's weights are declared constants evaluated
  in-sample on the seeded corpus; treat its F1 as a benchmark of
  the signal combination, not a deployable operating point.

## 8. Layout

```
copy_forward/   generator, measurement, detector, evaluation, CLI
data/           stored demo admission (regenerable)
examples/       runnable audit example + captured sample report
notebooks/      01 demo run, 02 evaluation experiment (runnable .py)
scripts/        build_cases.py, reproduce_results.py (drift guard)
results/        evaluation.json/.csv, summary and headline
tests/          60 tests
app.py          Streamlit dashboard (3 tabs)
```

Author: Amna Raheeba. MIT license.
