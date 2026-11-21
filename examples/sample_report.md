# Sample report

Output of `python examples/run_audit.py` on the stored demo admission
(data/demo_admission.json, seed 20261121, standard policy):

```
Admission 0 (14 days, policy standard)

Ground truth:
  - fever: onset day 4, resolves day 6, resolution noticed day 6
  - anemia: onset day 1, resolves day 5, resolution noticed day 7
  - pneumonia: onset day 5, resolves day 14, resolution never noticed

Daily problem lists (STALE = asserts a resolved finding):
  Day 1:
    - [anemia] Anemia, Hb trending down (span age 0, gen 0, score 0.10)
  Day 2:
    - [anemia] Anemia, Hb trending down (span age 1, gen 1, score 0.55)
  Day 3:
    - [anemia] Anemia, Hb trending down (span age 2, gen 2, score 1.00)
  Day 4:
    - [anemia] Anemia, Hb trending down (span age 3, gen 3, score 1.45)
    - [fever] Fever to 38.9 C, ongoing (span age 0, gen 0, score 0.10)
  Day 5:
    - [anemia] Anemia, Hb trending down (span age 4, gen 4, score 1.90; STALE, detector-flagged)
    - [fever] Fever to 38.9 C, ongoing (span age 1, gen 1, score 0.55)
    - [pneumonia] Hospital-acquired pneumonia, day of therapy noted (span age 0, gen 0, score 0.10)
  Day 6:
    - [pneumonia] Hospital-acquired pneumonia, day of therapy noted (span age 1, gen 1, score 0.55)
  Day 7:
    - [pneumonia] Hospital-acquired pneumonia, day of therapy noted (span age 2, gen 2, score 1.00)
  Day 8:
    - [pneumonia] Hospital-acquired pneumonia, day of therapy noted (span age 3, gen 3, score 1.45)
  Day 9:
    (empty)
  Day 10:
    - [pneumonia] Pneumonia, right lower lobe infiltrate (span age 0, gen 0, score 0.10)
  Day 11:
    (empty)
  Day 12:
    (empty)
  Day 13:
    (empty)
  Day 14:
    (empty)

Course-log resolution assertions:
  - day 6: adm0-fever
  - day 7: adm0-anemia
```
