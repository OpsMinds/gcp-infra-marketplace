import streamlit as st
from datetime import datetime

def show_recommendation_ui(recommendation: dict):
    # Initialize session state for editable_rec if not set
    if 'editable_rec' not in st.session_state:
        st.session_state.editable_rec = recommendation.copy()
    # To track removed fields
    if 'removed_fields' not in st.session_state:
        st.session_state.removed_fields = []

    editable_fields = {
        "compute": {"label": "Compute (vCPUs)", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 10, "max": 4000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 10000, "step": 100}
    }

    st.title("Review & Edit Recommendations")

    removed_fields = st.session_state.removed_fields

    st.subheader("Select the parameters you want to keep")
    for field in list(st.session_state.editable_rec.keys()):
        if field in editable_fields:
            keep = st.checkbox(f"Keep {editable_fields[field]['label']}", key=f"keep_{field}", value=field not in removed_fields)
            if not keep and field not in removed_fields:
                removed_fields.append(field)
                st.session_state.editable_rec.pop(field, None)
            elif keep and field in removed_fields:
                removed_fields.remove(field)
                # You may restore default value or keep it removed as per your logic
    st.session_state.removed_fields = removed_fields

    # Show sliders for numeric fields
    for field, opts in editable_fields.items():
        if field in st.session_state.editable_rec:
            current_value = st.session_state.editable_rec[field]
            new_value = st.slider(
                opts["label"],
                min_value=opts["min"],
                max_value=opts["max"],
                value=int(current_value) if isinstance(current_value, (int, float)) else opts["min"],
                step=opts["step"],
                key=f"slider_{field}"
            )
            st.session_state.editable_rec[field] = new_value

    # Show editable inputs for other fields
    for field in st.session_state.editable_rec:
        if field not in editable_fields:
            if field in ["start_date", "end_date"]:
                default_val = (
                    datetime.strptime(st.session_state.editable_rec[field], "%Y-%m-%d").date()
                    if isinstance(st.session_state.editable_rec[field], str) else datetime.today().date()
                )
                val = st.date_input(field.replace("_", " ").title(), value=default_val, key=f"input_{field}")
            else:
                val = st.text_input(field.replace("_", " ").title(), value=st.session_state.editable_rec[field], key=f"input_{field}")
            st.session_state.editable_rec[field] = val

    st.markdown("---")
    st.subheader("Final Configuration")
    st.json(st.session_state.editable_rec)

    if st.button("Accept & Proceed"):
        st.success("Configuration Accepted! You can proceed with provisioning workflow here.")
        # TODO: call provisioning backend or next step

    return st.session_state.editable_rec