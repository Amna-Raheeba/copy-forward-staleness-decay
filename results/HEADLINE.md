# Headline results

Copy-forward staleness measured on 60 seeded synthetic admissions (14 hospital days each, seed 20261121; reproduce with `python scripts/reproduce_results.py`).

- Under the standard copy policy, **31.6%** of the problem list is stale -- asserting findings that have already resolved -- by day 7, and **28.6%** by day 14.
- Once a finding resolves, its copied span keeps asserting it with a staleness half-life of **1.4 days**: half of resolved findings are still being charted as active that long after they stopped being true.
- Freshly written spans are **100.0%** accurate; copied spans are **72.7%** accurate. The gap is the decay the copy button causes.
- The provenance x contradiction detector flags stale spans at precision **0.405** / recall **0.561** (F1 **0.471**). The text-similarity-only baseline reaches F1 **0.417** (precision 0.273) -- it flags every verbatim copy, live or stale, and cannot tell the difference.
- Copy policy is the lever: high-copy documentation produces **7.6 stale mention-days per admission** vs **1.1** under low-copy, while an attentive writer at the same copy rate cuts it to **1.2**.

Caveat: all admissions are synthetic and seeded, generated from known resolution schedules; copy, edit and observation rates are declared parameters, not measurements of any real EHR. The audit measures what copy-forward costs under those declared conditions, and gives the detector benchmark a ground truth that observational copy-paste studies do not have.
