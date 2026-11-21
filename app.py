"""Streamlit dashboard for copy-forward-staleness-decay.

Three tabs:
1. Admission timeline -- one seeded admission under a chosen copy
   policy, with each day's problem list, ground-truth staleness
   labels and detector flags.
2. Decay curves -- stale prevalence by hospital day, accuracy by
   span provenance, and the staleness half-life per finding type.
3. Evaluation -- the stored headline results
   (results/evaluation.json): detector benchmark and harm by policy.

Run: streamlit run app.py
"""

import json
import os

import pandas as pd
import streamlit as st

from copy_forward.detect import detector_score, flag_combined, mention_features
from copy_forward.evaluate import DEFAULT_CONFIG
from copy_forward.generate import POLICY_ORDER, generate_admissions
from copy_forward.measure import (
    accuracy_by_origin,
    half_life_by_type,
    prevalence_by_day,
)
from copy_forward.models import mention_is_stale

st.set_page_config(page_title="Copy-Forward Staleness Decay", layout="wide")

SEED = DEFAULT_CONFIG["seed"]
N_DAYS = DEFAULT_CONFIG["n_days"]


@st.cache_data
def load_admissions(policy, n=12):
    return generate_admissions(n, SEED, n_days=N_DAYS, policy=policy)


@st.cache_data
def load_results():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "results", "evaluation.json"
    )
    if not os.path.exists(path):
        return None
    with open(path) as handle:
        return json.load(handle)


st.title("Copy-Forward Staleness Decay")
st.caption(
    "How long resolved findings persist in copied-forward notes after "
    "they stop being true -- measured against generated ground truth."
)

tab1, tab2, tab3 = st.tabs(["Admission timeline", "Decay curves", "Evaluation"])

with tab1:
    policy = st.selectbox("Copy policy", POLICY_ORDER, index=1)
    admissions = load_admissions(policy)
    idx = st.slider("Admission", 0, len(admissions) - 1, 0)
    admission = admissions[idx]
    st.subheader("Ground truth")
    truth_rows = []
    for finding in admission.findings:
        truth_rows.append(
            {
                "finding": finding.finding_type,
                "onset day": finding.onset_day,
                "resolution day": finding.resolution_day,
                "resolution noticed day": finding.resolution_observed_day,
            }
        )
    st.dataframe(pd.DataFrame(truth_rows))
    st.subheader("Daily problem lists")
    rows = []
    for note in admission.notes:
        for mention in note.mentions:
            features = mention_features(admission, mention)
            rows.append(
                {
                    "day": mention.day,
                    "finding": mention.finding_type,
                    "span": mention.text,
                    "origin": mention.origin,
                    "span age": mention.span_age,
                    "stale (truth)": mention_is_stale(admission, mention),
                    "detector score": round(detector_score(features), 2),
                    "detector flagged": flag_combined(features),
                }
            )
    if rows:
        st.dataframe(pd.DataFrame(rows))
    else:
        st.write("No mentions in this admission.")

with tab2:
    admissions = load_admissions("standard", n=30)
    st.subheader("Stale prevalence by hospital day (standard policy)")
    prevalence = prevalence_by_day(admissions)
    prev_df = pd.DataFrame(
        {"day": list(prevalence.keys()), "stale share": list(prevalence.values())}
    ).set_index("day")
    st.line_chart(prev_df)
    st.subheader("Mention accuracy by span provenance")
    by_origin = accuracy_by_origin(admissions)
    origin_df = pd.DataFrame(
        {"provenance": list(by_origin.keys()), "accuracy": list(by_origin.values())}
    ).set_index("provenance")
    st.bar_chart(origin_df)
    st.subheader("Staleness half-life by finding type (days)")
    half = half_life_by_type(admissions)
    half_rows = [
        {
            "finding type": finding_type,
            "half-life (days)": (
                values["half_life_days"] if values["half_life_days"] is not None else -1
            ),
        }
        for finding_type, values in half.items()
    ]
    st.dataframe(pd.DataFrame(half_rows))
    st.caption("Half-life -1 means the survival curve never crossed 50% within the stay.")

with tab3:
    results = load_results()
    if results is None:
        st.write("No stored results yet. Run: python -m copy_forward evaluate")
    else:
        std = results["standard"]
        st.subheader("Headline (standard policy)")
        st.write(
            "Stale prevalence day 7: %.3f | day %d: %.3f | overall "
            "staleness half-life: %s days"
            % (
                std["prevalence_day7"],
                results["config"]["n_days"],
                std["prevalence_day14"],
                std["overall_half_life_days"],
            )
        )
        st.write(
            "Accuracy -- fresh: %.3f, edited: %.3f, copied: %.3f"
            % (
                std["accuracy_fresh_vs_copied"]["fresh"],
                std["accuracy_fresh_vs_copied"]["edited"],
                std["accuracy_fresh_vs_copied"]["copied"],
            )
        )
        st.subheader("Detectors")
        det_rows = []
        for name, scores in sorted(std["detectors"].items()):
            det_rows.append(
                {
                    "detector": name,
                    "precision": scores["precision"],
                    "recall": scores["recall"],
                    "F1": scores["f1"],
                }
            )
        st.dataframe(pd.DataFrame(det_rows))
        st.subheader("Harm by copy policy")
        harm_rows = []
        for policy_name, harm in results["harm"].items():
            harm_rows.append(
                {
                    "policy": policy_name,
                    "stale mention-days / admission": harm[
                        "stale_days_per_admission"
                    ],
                    "stale share": harm["stale_share"],
                    "phantom problems, final day": harm["phantom_final_day"],
                }
            )
        st.dataframe(pd.DataFrame(harm_rows))
