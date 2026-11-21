# Evaluation summary

Seed 20261121, 60 admissions x 14 days per policy.

## Standard policy

- Stale prevalence: day 7 = 0.317, day 14 = 0.286
- Overall staleness half-life: 1.43 days
- Mention accuracy: fresh 1.000 vs copied 0.727

## Detectors (standard policy)

- age_only: P 0.305 / R 0.475 / F1 0.372
- cue_only: P 1.000 / R 0.217 / F1 0.357
- provenance_x_contradiction: P 0.405 / R 0.561 / F1 0.471
- similarity_only: P 0.273 / R 0.887 / F1 0.417

## Harm by policy

- low_copy: 1.08 stale mention-days/admission, stale share 0.128, phantom problems on final day 0.02
- standard: 3.68 stale mention-days/admission, stale share 0.216, phantom problems on final day 0.17
- attentive: 1.22 stale mention-days/admission, stale share 0.095, phantom problems on final day 0.00
- high_copy: 7.63 stale mention-days/admission, stale share 0.362, phantom problems on final day 0.30
