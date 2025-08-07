import streamlit as st
from datetime import date, datetime
import google.generativeai as genai
import json


# Set page config
st.set_page_config(page_title="Google Cloud Marketplace", layout="wide")


# Safe rerun helper
def safe_rerun():
    try:
        st.experimental_rerun()
    except AttributeError:
        import streamlit.runtime.scriptrunner.script_runner as script_runner
        from streamlit.runtime import runtime as rt
        from streamlit.runtime.scriptrunner import RerunException, RerunData

        raise RerunException(RerunData())


# Build prompt for Gemini 2.5 Pro
def build_prompt(fields: dict) -> str:
    prompt = (
        "You are an expert Google Cloud architect and FinOps advisor.\n"
        "Given the following user requirements, provide an optimized GCP infrastructure recommendation.\n"
        "Respond ONLY with a valid JSON object containing the following keys:\n"
        "- summary: a 2-3 sentence concise explanation.\n"
        "- recommendation: a bullet-point list of recommendations.\n"
        "- config: a dictionary with final suggested configurations including vCPUs, storage, GPU, budget, and other fields.\n"
        "Do NOT add any extra text or markdown formatting.\n\n"
        f"User Requirements:\n"
        f"Project Name: {fields.get('project_name')}\n"
        f"Description: {fields.get('description')}\n"
        f"Purpose: {fields.get('purpose')}\n"
        f"Environment: {fields.get('environment')}\n"
        f"Workload Type: {fields.get('workload_type')}\n"
        f"vCPUs: {fields.get('compute')}\n"
        f"Storage (GB): {fields.get('storage')}\n"
        f"GPU: {fields.get('gpu')}\n"
        f"Region: {fields.get('region')}\n"
        f"Start Date: {fields.get('start_date')}\n"
        f"End Date: {fields.get('end_date')}\n"
        f"Budget: {fields.get('budget')}\n"
        f"Special Needs: {fields.get('special_needs')}\n"
        "Please respond now."
    )
    return prompt


# Extract JSON from AI response robustly
def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("``"):
        text = text.strip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"error": "No JSON found in response.", "raw_text": text}
    json_str = text[start : end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {e}", "raw_json": json_str}


# Call Gemini model and parse output
def call_gemini(fields: dict) -> dict:
    try:
        api_key = st.secrets["genai"]["api_key"]
    except KeyError:
        st.error("API key for Gemini is not set in secrets.")
        return {}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")

    prompt = build_prompt(fields)
    response = model.generate_content(prompt)

    parsed = extract_json(response.text)
    return parsed


# Initialize session variables
if "page" not in st.session_state:
    st.session_state.page = "input"

if "user_fields" not in st.session_state:
    st.session_state.user_fields = {}

if "genai_result" not in st.session_state:
    st.session_state.genai_result = {}

if "editable_rec" not in st.session_state:
    st.session_state.editable_rec = {}

if "removed_fields" not in st.session_state:
    st.session_state.removed_fields = []


def show_input_page():
    st.title("Google Cloud Marketplace - Request Input")

    env = st.sidebar.selectbox(
        "Environment",
        ["Development", "QA", "Production", "Sandbox", "Other"],
        help="Where the resources will be deployed",
        key="sidebar_env",
    )
    purpose = st.sidebar.selectbox(
        "Purpose",
        ["Lab", "Hackathon", "Development"],
        help="Reason for infrastructure request",
        key="sidebar_purpose",
    )

    mode = st.radio(
        "Input Type",
        ["Web Form", "Chatbot"],
        key="input_mode",
        help="Choose how to specify your requirements",
    )

    user_data = {}

    if mode == "Web Form":
        with st.form("input_form"):
            project_name = st.text_input(
                "Project Name", placeholder="My AI Project", help="Name of your project"
            )
            description = st.text_area(
                "Description",
                placeholder="Briefly describe your project or workload",
                help="Describe what the resources are for",
            )
            workload_type = st.selectbox(
                "Workload Type",
                ["Batch", "Service", "AI/ML", "Storage", "Other"],
                help="The main type of workload",
            )
            compute = st.number_input(
                "Compute (vCPUs)",
                min_value=1,
                max_value=128,
                step=1,
                help="Number of CPUs required",
            )
            storage = st.number_input(
                "Storage (GB)",
                min_value=0,
                step=1,
                help="Size of storage needed",
            )
            gpu = st.selectbox(
                "GPU",
                ["None", "NVIDIA A100", "NVIDIA T4", "NVIDIA V100"],
                help="Select GPU if needed",
            )
            region = st.selectbox(
                "Region",
                ["us-central1", "us-east1", "europe-west1", "asia-east1"],
                help="Choose the GCP region",
            )
            start_date = st.date_input("Start Date", min_value=date.today(), help="When to start using resources")
            end_date = st.date_input("End Date", min_value=start_date, help="When to de-provision resources")
            budget = st.number_input(
                "Budget (USD)",
                min_value=0,
                help="Maximum budget allowed",
            )
            monitoring = st.radio(
                "Monitoring",
                ['Yes', 'No'],
                index=1,
                help="Do you want monitoring enabled?",
            )
            special_needs = st.text_area(
                "Special Needs",
                placeholder="Docker, special images, networking...",
                help="Additional requirements",
            )

            submitted = st.form_submit_button("Submit")

        if submitted:
            user_data = dict(
                project_name=project_name,
                description=description,
                workload_type=workload_type,
                compute=compute,
                storage=storage,
                gpu=gpu,
                region=region,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                budget=budget,
                monitoring=monitoring,
                special_needs=special_needs,
                environment=env,
                purpose=purpose,
            )

    else:  # Chatbot input
        st.write(
            "Example: 'I need 8 vCPUs, 100 GB storage, T4 GPU for AI hackathon in us-central1 from Aug 20 to Sept 5, budget 1500 USD, monitoring yes.'"
        )
        raw_text = st.text_area("Describe your infrastructure needs")
        if st.button("Submit Chatbot"):
            if raw_text.strip():
                user_data = dict(
                    project_name="[From Chatbot]",
                    description=raw_text,
                    workload_type="",
                    compute=None,
                    storage=None,
                    gpu="",
                    region="",
                    start_date="",
                    end_date="",
                    budget=None,
                    monitoring="No",
                    special_needs="",
                    environment=env,
                    purpose=purpose,
                )
            else:
                st.warning("Please enter your requirement details")

    if user_data:
        st.session_state.user_fields = user_data
        st.session_state.page = "recommendation"
        safe_rerun()


def show_recommendation_page():
    st.title("Recommendation & Customization")

    if not st.session_state.genai_result:
        with st.spinner("Generating recommendation..."):
            res = call_gemini(st.session_state.user_fields)
            st.session_state.genai_result = res
            st.session_state.editable_rec = dict(res.get("config", {}))

    res = st.session_state.genai_result
    editable_rec = st.session_state.editable_rec
    removed_fields = st.session_state.removed_fields

    if summary := res.get("summary"):
        st.success(summary)

    if recommendations := res.get("recommendation"):
        st.markdown("### Recommendations:")
        if isinstance(recommendations, list):
            for rec in recommendations:
                st.markdown(f"- {rec}")
        else:
            st.markdown(recommendations)

    # Use 3 columns layout
    NUM_COLS = 3

    st.markdown("---")
    st.write("Select resources to keep:")

    checkbox_cols = st.columns(NUM_COLS)
    field_names = list({
        **{'compute': {'label': 'vCPUs', 'min': 1, 'max': 128, 'step': 1}},
        **{'storage': {'label': 'Storage (GB)', 'min': 1, 'max': 20000, 'step': 10}},
        **{'budget': {'label': 'Budget (USD)', 'min': 0, 'max': 100000, 'step': 100}},
    }.keys())

    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 1, "max": 20000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100},
    }

    # Render checkboxes per resource
    for i, field in enumerate(field_names):
        col = checkbox_cols[i % NUM_COLS]
        with col:
            keep = st.checkbox(
                f"Keep {editable_fields[field]['label']}",
                value=field not in removed_fields,
                key=f"keep_{field}",
            )
            if not keep and field not in removed_fields:
                removed_fields.append(field)
                editable_rec.pop(field, None)
            elif keep and field in removed_fields:
                removed_fields.remove(field)
                defaults = {"compute": 4, "storage": 100, "budget": 1000}
                if field not in editable_rec:
                    editable_rec[field] = defaults.get(field, 0)
    st.session_state.removed_fields = removed_fields

    st.markdown("---")
    st.write("Adjust resource allocation:")

    slider_cols = st.columns(NUM_COLS)
    kept_fields = [f for f in field_names if f not in removed_fields]

    for i, field in enumerate(kept_fields):
        col = slider_cols[i % NUM_COLS]
        params = editable_fields[field]
        col_label = params["label"]
        col_min = params["min"]
        col_max = params["max"]
        col_step = params["step"]

        with col:
            val_raw = editable_rec.get(field, 0)

            if isinstance(val_raw, (dict, list)):
                st.warning(f"Skipping slider for '{field}' due to invalid type.")
                continue

            try:
                val = int(val_raw)
            except Exception:
                st.warning(f"Invalid value for '{field}', resetting to minimum.")
                val = col_min

            new_val = st.slider(
                col_label,
                min_value=col_min,
                max_value=col_max,
                value=val,
                step=col_step,
                key=f"slider_{field}",
            )
            editable_rec[field] = new_val

    # Render other fields in columns (monitoring as radio, others as text/date)
    other_fields = [k for k in editable_rec.keys() if k not in editable_fields]
    if other_fields:
        st.markdown("---")
        st.write("Other configuration options:")

        other_cols = st.columns(NUM_COLS)
        for i, field in enumerate(other_fields):
            col = other_cols[i % NUM_COLS]
            val = editable_rec.get(field, "")

            with col:
                if field == "monitoring":
                    # Radio for monitoring yes/no
                    choice = st.radio(
                        "Enable Monitoring?",
                        options=["Yes", "No"],
                        index=0 if str(val).lower() == "yes" else 1,
                        key=f"radio_{field}",
                    )
                    editable_rec[field] = choice

                elif field in ("start_date", "end_date"):
                    try:
                        dt = datetime.strptime(val, "%Y-%m-%d").date()
                    except Exception:
                        dt = date.today()
                    dt_val = st.date_input(
                        field.replace("_", " ").title(),
                        value=dt,
                        key=f"date_{field}",
                    )
                    editable_rec[field] = dt_val.strftime("%Y-%m-%d")
                else:
                    new_val = st.text_input(
                        field.replace("_", " ").title(),
                        value=val,
                        key=f"text_{field}",
                    )
                    editable_rec[field] = new_val

    st.markdown("---")
    #col_accept = st.columns()
    #with col_accept[0]:
    if st.button("Accept and Submit"):
        st.success("Configuration accepted! Proceeding to approval...")



if st.session_state.page == "input":
    show_input_page()
elif st.session_state.page == "recommendation":
    show_recommendation_page()
else:
    st.error(f"Unknown page state: {st.session_state.page}")
