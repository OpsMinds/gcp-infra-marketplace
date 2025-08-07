import streamlit as st
from datetime import datetime

def show_recommendation_ui(recommendation: dict):
    # Neat layout and interactivity
    st.title("Review & Customize Your GCP Recommendation")

    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 10, "max": 10000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100}
    }
    # Initialize state
    if 'editable_rec' not in st.session_state:
        st.session_state.editable_rec = recommendation.copy()
    if 'removed_fields' not in st.session_state:
        st.session_state.removed_fields = []

    removed_fields = st.session_state.removed_fields

    st.write("Uncheck any resource you want to remove:")
    cols = st.columns(len(editable_fields))
    for idx, field in enumerate(editable_fields):
        keep = cols[idx].checkbox(
            f"Keep {editable_fields[field]['label']}",
            value=field not in removed_fields,
            key=f"keep_{field}"
        )
        if not keep and field not in removed_fields:
            removed_fields.append(field)
            st.session_state.editable_rec.pop(field, None)
        elif keep and field in removed_fields:
            removed_fields.remove(field)
            if field not in st.session_state.editable_rec:
                defaults = {"compute": 4, "storage": 100, "budget": 1000}
                st.session_state.editable_rec[field] = defaults.get(field, 0)
    st.session_state.removed_fields = removed_fields

    st.markdown("---")

    for field, opts in editable_fields.items():
        if field in st.session_state.editable_rec:
            new_val = st.slider(
                editable_fields[field]["label"],
                min_value=opts["min"],
                max_value=opts["max"],
                value=int(st.session_state.editable_rec[field]),
                step=opts["step"],
                key=f"slider_{field}"
            )
            st.session_state.editable_rec[field] = new_val

    st.markdown("---")

    for field in st.session_state.editable_rec:
        if field not in editable_fields:
            if field in ["start_date", "end_date"]:
                try:
                    val = datetime.strptime(st.session_state.editable_rec[field], "%Y-%m-%d").date()
                except Exception:
                    val = datetime.today().date()
                new_val = st.date_input(field.replace("_", " ").title(), value=val, key=f"date_{field}")
                st.session_state.editable_rec[field] = new_val.strftime("%Y-%m-%d")
            else:
                new_val = st.text_input(
                    field.replace("_", " ").title(),
                    value=st.session_state.editable_rec[field],
                    key=f"text_{field}"
                )
                st.session_state.editable_rec[field] = new_val

    st.markdown("---")

    # ---- Compute Engine SUGGESTION ----
    st.subheader("Suggested Compute Engine Type")
    compute = st.session_state.editable_rec.get("compute", 4)
    gpu = st.session_state.editable_rec.get("gpu", "None")
    engine_suggestion = "E2 (General Purpose) for light workloads."
    if gpu and gpu != "None":
        engine_suggestion = "A2, N1, or N2 (with attached GPU) for ML/AI or GPU needs."
    elif compute >= 32:
        engine_suggestion = "C2 (High-CPU) or N2 for performance-intensive jobs."
    elif compute >= 16:
        engine_suggestion = "N2 or E2 for balanced/medium workloads."
    st.info(engine_suggestion)

    st.markdown("---")
    st.subheader("Final Configuration")
    st.json(st.session_state.editable_rec)

    if st.button("Accept & Proceed"):
        st.success("Configuration accepted! (Call your backend/provisioning here.)")

# For demo, you can call show_recommendation_ui(recommendation_dict)
