import streamlit as st
from datetime import datetime, date

def safe_rerun():
    try:
        st.experimental_rerun()
    except AttributeError:
        import streamlit.runtime.scriptrunner.script_runner as script_runner
        from streamlit.runtime.scriptrunner import RerunException, RerunData
        raise RerunException(RerunData())

def show_recommendation_page():
    st.title("GCP Infrastructure Marketplace - Recommendation")

    # Validate required state
    if "genai_parsed_result" not in st.session_state:
        st.warning("No recommendation data found. Please submit your input first.")
        st.stop()

    result = st.session_state.genai_parsed_result

    # Initialize editable_rec with config data if not already done
    if "editable_rec" not in st.session_state:
        try:
            st.session_state.editable_rec = dict(result.get("config", {}))
        except Exception:
            st.session_state.editable_rec = {}

    editable_rec = st.session_state.editable_rec

    # Track removed numeric fields
    if "removed_fields" not in st.session_state:
        st.session_state.removed_fields = []
    removed_fields = st.session_state.removed_fields

    # Define the numeric fields editable via sliders
    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 10, "max": 20000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100},
    }

    # Display summary if available
    if summary := result.get("summary"):
        st.success(summary)

    # Display bullet point recommendations
    if recommendations := result.get("recommendation"):
        st.markdown("### Key Recommendations:")
        if isinstance(recommendations, list):
            for item in recommendations:
                st.markdown(f"- {item}")
        else:
            st.markdown(recommendations)

    st.markdown("---")
    st.subheader("Customize Your Configuration")

    # Columns for checkboxes for keeping/removing fields
    cols = st.columns(len(editable_fields))
    st.write("Uncheck any resource you want to remove:")
    for idx, field in enumerate(editable_fields):
        keep = cols[idx].checkbox(
            f"Keep {editable_fields[field]['label']}",
            value=field not in removed_fields,
            key=f"keep_{field}"
        )
        if not keep and field not in removed_fields:
            removed_fields.append(field)
            editable_rec.pop(field, None)
        elif keep and field in removed_fields:
            removed_fields.remove(field)
            # If field was removed, add default value back (optional)
            defaults = {"compute": 4, "storage": 100, "budget": 1000}
            if field not in editable_rec:
                editable_rec[field] = defaults[field]

    st.session_state.removed_fields = removed_fields

    # Sliders for numeric fields with value type checking
    for field, opts in editable_fields.items():
        if field in editable_rec:
            val_raw = editable_rec[field]
            # Skip if value is complex type (dict/list)
            if isinstance(val_raw, (dict, list)):
                st.warning(f"Skipping slider for '{field}' because value is complex type.")
                continue
            try:
                val = int(val_raw)
            except Exception:
                st.warning(f"Skipping slider for '{field}' due to invalid value: {val_raw}")
                continue

            new_val = st.slider(
                opts["label"],
                min_value=opts["min"],
                max_value=opts["max"],
                value=val,
                step=opts["step"],
                key=f"slider_{field}"
            )
            editable_rec[field] = new_val

    # Editable inputs for other fields (text and dates)
    for field in list(editable_rec.keys()):
        if field not in editable_fields:
            val = editable_rec[field]
            if field in ["start_date", "end_date"]:
                try:
                    dt = datetime.strptime(val, "%Y-%m-%d").date()
                except Exception:
                    dt = date.today()
                new_date = st.date_input(field.replace("_", " ").title(), value=dt, key=f"date_{field}")
                editable_rec[field] = new_date.strftime("%Y-%m-%d")
            else:
                new_val = st.text_input(field.replace("_", " ").title(), value=val, key=f"text_{field}")
                editable_rec[field] = new_val

    st.markdown("---")
    st.subheader("Final Editable Configuration")
    st.json(editable_rec)

    # Navigation buttons layout: Back and Accept/Submit
    cols = st.columns(2)

    with cols[0]:
        if st.button("← Back to Input"):
            st.session_state.page = "input"
            st.session_state.genai_parsed_result = {}
            st.session_state.editable_rec = {}
            st.session_state.removed_fields = []
            safe_rerun()
            return

    with cols[1]:
        if st.button("Accept and Submit for Approval"):
            st.success("Configuration accepted! Approval workflow will be triggered next.")
            # Place approval or provisioning logic here as next step
