import streamlit as st
from datetime import date, datetime
import google.generativeai as genai
import json

st.set_page_config(page_title="GCP Infra Marketplace", layout="wide")

# --- Safe rerun helper ---
def safe_rerun():
    try:
        st.experimental_rerun()
    except AttributeError:
        import streamlit.runtime.scriptrunner.script_runner as script_runner
        from streamlit.runtime.scriptrunner import RerunException, RerunData
        raise RerunException(RerunData())

# --- Gemini prompt builder ---
def build_prompt_from_fields(fields: dict) -> str:
    prompt = (
        "You are an expert Google Cloud architect and FinOps specialist. "
        "Given the user requirements below, provide an optimized Google Cloud infrastructure recommendation. "
        "Output ONLY a valid JSON object with keys: summary (a concise 2-3 sentence explanation), "
        "recommendation (a list of bullet points), and config (dictionary of optimized parameters). "
        "Do NOT include any markdown, explanation, or extra text outside the JSON.\n\n"
        "Input:\n"
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
        "\nPlease respond now."
    )
    return prompt

# --- Extract JSON from GenAI response robustly ---
def extract_json_from_text(text: str) -> dict:
    text = text.strip()
    if text.startswith("``"):
        text = text.strip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"error": "No JSON found in response.", "raw_text": text}
    json_str = text[start:end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {"error": f"JSON decode error: {e}", "raw_json": json_str}

# --- Call Gemini GenAI API ---
def call_genai_and_parse(fields: dict) -> dict:
    api_key = st.secrets["genai"]["api_key"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    prompt = build_prompt_from_fields(fields)
    response = model.generate_content(prompt)
    parsed = extract_json_from_text(response.text)
    return parsed

# --- Initialize session_state variables ---
if "page" not in st.session_state:
    st.session_state.page = "input"  # can be 'input' or 'recommendation'

if "user_fields" not in st.session_state:
    st.session_state.user_fields = {}

if "genai_parsed_result" not in st.session_state:
    st.session_state.genai_parsed_result = {}

if "editable_rec" not in st.session_state:
    st.session_state.editable_rec = {}

if "removed_fields" not in st.session_state:
    st.session_state.removed_fields = []

# --- UI Functions ---
def show_input_form():
    st.title("GCP Infrastructure Marketplace - Input")

    env = st.sidebar.selectbox(
        "Environment",
        ["Development", "QA", "Production", "Sandbox", "Other"],
        help="Where resources will be used",
        key="sidebar_env",
    )
    purpose = st.sidebar.selectbox(
        "Purpose",
        ["Lab", "Hackathon", "Development"],
        help="Primary reason for this infra request",
        key="sidebar_purpose",
    )

    mode = st.radio(
        "Choose input method:",
        ["Web Form (Structured)", "Chatbot (Free Text)"],
        help="Select your preferred input method",
        key="input_mode",
    )

    user_data = {}

    if mode == "Web Form (Structured)":
        with st.form("input_form"):
            project_name = st.text_input("Project Name", help="Unique project identifier")
            description = st.text_area("Project Description", help="Brief description of your workload")
            workload_type = st.selectbox(
                "Workload Type",
                ["Batch", "Service", "AI/ML", "Storage", "Other"],
                help="Type of workload",
            )
            compute = st.number_input("Compute (vCPUs)", min_value=1, max_value=128, step=1, help="Number of vCPUs")
            storage = st.number_input("Storage (GB)", min_value=0, step=1, help="Disk size in GB")
            gpu = st.selectbox("GPU Type", ["None", "NVIDIA A100", "NVIDIA T4", "NVIDIA V100"], help="GPU needed if any")
            region = st.selectbox("Region", ["us-central1", "us-east1", "europe-west1", "asia-east1"], help="GCP region")
            start_date = st.date_input("Start Date", min_value=date.today(), help="Resource start date")
            end_date = st.date_input("End Date", min_value=start_date, help="Resource end date")
            budget = st.number_input("Budget (USD)", min_value=0, help="Max budget")
            special_needs = st.text_area("Special Needs (optional)", help="Custom requirements")

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
                special_needs=special_needs,
                environment=env,
                purpose=purpose,
            )
    else:  # Chatbot mode
        st.write(
            "Example: 'Need 8 vCPUs, 100GB storage, NVIDIA T4 GPU for AI hackathon in us-central1 from Aug 20-Sept 5, budget $1500.'"
        )
        raw_text = st.text_area("Describe your infrastructure needs:")

        if st.button("Submit Chatbot"):
            if not raw_text.strip():
                st.warning("Please enter your infrastructure description.")
            else:
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
                    special_needs="",
                    environment=env,
                    purpose=purpose,
                )

    if user_data:
        st.session_state.user_fields = user_data
        st.session_state.page = "recommendation"
        safe_rerun()
        return

def show_recommendation_page():
    st.title("GCP Infrastructure Marketplace - Recommendation")

    if not st.session_state.genai_parsed_result:
        with st.spinner("Generating recommendation..."):
            result = call_genai_and_parse(st.session_state.user_fields)
            st.session_state.genai_parsed_result = result
            config = result.get("config", {})
            st.session_state.editable_rec = dict(config)

    result = st.session_state.genai_parsed_result
    editable_rec = st.session_state.editable_rec
    removed_fields = st.session_state.removed_fields

    if summary := result.get("summary"):
        st.success(summary)

    if recommendations := result.get("recommendation"):
        st.markdown("### Key Recommendations:")
        if isinstance(recommendations, list):
            for rec in recommendations:
                st.markdown(f"- {rec}")
        else:
            st.markdown(recommendations)

    st.markdown("---")
    st.subheader("Customize Your Recommendation")

    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 10, "max": 20000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100},
    }

    cols = st.columns(len(editable_fields))
    st.write("Uncheck any resource you want to remove:")
    for idx, field in enumerate(editable_fields):
        keep = cols[idx].checkbox(
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

    for field, opts in editable_fields.items():
        if field in editable_rec:
            val_raw = editable_rec[field]
            if isinstance(val_raw, (dict, list)):
                st.warning(f"Skipping slider for '{field}' because value is complex.")
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
                key=f"slider_{field}",
            )
            editable_rec[field] = new_val

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

    col_accept, = st.columns(1)
    with col_accept:
        if st.button("Accept and Submit for Approval"):
            st.success("Configuration accepted! Approval workflow will be triggered next.")
            # Implement approval/provisioning logic here

if st.session_state.page == "input":
    show_input_form()
elif st.session_state.page == "recommendation":
    show_recommendation_page()
else:
    st.error(f"Unknown page in session state: {st.session_state.page}")
