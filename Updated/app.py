import streamlit as st
from datetime import date, datetime
import google.generativeai as genai
import json
import google.auth
from googleapiclient.discovery import build

# Page config
st.set_page_config(page_title="Google Cloud Marketplace", layout="wide")

# Safe rerun helper
def safe_rerun():
    try:
        st.experimental_rerun()
    except AttributeError:
        import streamlit.runtime.scriptrunner.script_runner as script_runner
        from streamlit.runtime.scriptrunner import RerunException, RerunData
        raise RerunException(RerunData())

# Initialize Cloud Billing API client using ADC
@st.cache_resource(ttl=3600)
def init_billing_client():
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-billing"])
        service = build('cloudbilling', 'v1', credentials=credentials)
        return service
    except Exception as e:
        st.error(f"Failed to initialize Cloud Billing client via ADC: {e}")
        return None

# Fetch pricing SKUs from billing account (cached)
@st.cache_data(ttl=86400)
def fetch_pricing_skus(service, billing_account_id):
    if service is None or billing_account_id is None:
        return {}

    skus_price_map = {}
    page_token = None
    try:
        while True:
            response = service.billingAccounts().skus().list(
                parent=billing_account_id, pageToken=page_token, pageSize=500
            ).execute()

            for sku in response.get("skus", []):
                service_name = sku['category']['serviceDisplayName']
                sku_desc = sku.get("description", "")
                usage_type = sku['category'].get('usageType', '')
                region = sku['serviceRegions'][0] if sku.get('serviceRegions') else ""

                if "Compute Engine" in service_name:
                    for price_info in sku.get("pricingInfo", []):
                        pricing_expression = price_info.get("pricingExpression", {})
                        tiered_rates = pricing_expression.get("tieredRates", [])
                        if tiered_rates:
                            unit_price = tiered_rates[0].get("unitPrice", {})
                            units = unit_price.get("units", 0)
                            nanos = unit_price.get("nanos", 0)
                            price_per_unit = units + nanos / 1e9
                            key = (sku_desc, region, usage_type)
                            skus_price_map[key] = price_per_unit
            page_token = response.get("nextPageToken", None)
            if not page_token:
                break
    except Exception as e:
        st.warning(f"Error fetching pricing SKUs: {str(e)}")

    return skus_price_map

def get_price_for_resource(resource_desc, region, usage_type, skus_price_map):
    for (desc, rgn, usage), price in skus_price_map.items():
        if resource_desc in desc and (region in rgn or rgn == "global") and usage == usage_type:
            return price
    return None

# Prompt to extract fields from chatbot text including memory
def make_extraction_prompt(free_text, env, purpose):
    return (
        "Extract the following fields as JSON from the user's text.\n"
        "Fields: project_name, description, workload_type, compute, memory, storage, gpu, region, start_date, end_date, budget, special_needs, environment, purpose, monitoring.\n"
        "If any field is missing, try to infer or use empty string. Dates as 'YYYY-MM-DD', numbers as integers.\n"
        f"\nUser text:\n{free_text}\nEnvironment: {env}\nPurpose: {purpose}\nRespond ONLY with valid JSON."
    )

# Build prompt for recommendation including memory
def build_prompt(fields: dict) -> str:
    prompt = (
        "You are an expert Google Cloud architect and FinOps advisor.\n"
        "Given the following user requirements, provide an optimized GCP infrastructure recommendation.\n"
        "Respond ONLY with a valid JSON object containing keys: summary, recommendation, config.\n"
        "Do NOT add extra text or formatting.\n\n"
        f"User Requirements:\n"
        f"Project Name: {fields.get('project_name')}\n"
        f"Description: {fields.get('description')}\n"
        f"Purpose: {fields.get('purpose')}\n"
        f"Environment: {fields.get('environment')}\n"
        f"Workload Type: {fields.get('workload_type')}\n"
        f"vCPUs: {fields.get('compute')}\n"
        f"Memory (GB): {fields.get('memory')}\n"
        f"Storage (GB): {fields.get('storage')}\n"
        f"GPU: {fields.get('gpu')}\n"
        f"Region: {fields.get('region')}\n"
        f"Start Date: {fields.get('start_date')}\n"
        f"End Date: {fields.get('end_date')}\n"
        f"Budget: {fields.get('budget')}\n"
        f"Monitoring: {fields.get('monitoring')}\n"
        f"Special Needs: {fields.get('special_needs')}\n"
        "Please respond now."
    )
    return prompt

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

def call_gemini_extract_fields(free_text, env, purpose):
    api_key = st.secrets["genai_api_key"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = make_extraction_prompt(free_text, env, purpose)
    response = model.generate_content(prompt)
    return extract_json(response.text)

def call_gemini(fields: dict) -> dict:
    api_key = st.secrets["genai_api_key"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = build_prompt(fields)
    response = model.generate_content(prompt)
    return extract_json(response.text)

# Estimate cost from GCP pricing API data
def estimate_billing_cost_from_api(config, region, skus_price_map):
    try:
        vcpu_count = int(config.get("compute", 0) or 0)
    except Exception:
        vcpu_count = 0
    try:
        memory_gb = int(config.get("memory", 0) or 0)
    except Exception:
        memory_gb = 0
    try:
        storage_gb = int(config.get("storage", 0) or 0)
    except Exception:
        storage_gb = 0

    gpu_name = str(config.get("gpu", "None") or "None")

    try:
        start = datetime.strptime(str(config.get("start_date", "")), "%Y-%m-%d").date()
        end = datetime.strptime(str(config.get("end_date", "")), "%Y-%m-%d").date()
        days = max((end - start).days, 1)
    except Exception:
        days = 1

    cpu_desc = "N1 Predefined Instance Core"
    memory_desc = "N1 Predefined Instance Ram"
    storage_desc = "SSD"
    gpu_desc_map = {
        "None": None,
        "NVIDIA T4": "NVIDIA T4",
        "NVIDIA A100": "NVIDIA A100",
        "NVIDIA V100": "NVIDIA V100",
    }

    usage_type = "OnDemand"

    cpu_price = get_price_for_resource(cpu_desc, region, usage_type, skus_price_map) or 0
    mem_price = get_price_for_resource(memory_desc, region, usage_type, skus_price_map) or 0
    storage_price = get_price_for_resource(storage_desc, region, usage_type, skus_price_map) or 0

    gpu_price = 0
    gpu_desc = gpu_desc_map.get(gpu_name, None)
    if gpu_desc:
        gpu_price = get_price_for_resource(gpu_desc, region, usage_type, skus_price_map) or 0

    hours = days * 24

    total_cost = ((cpu_price * vcpu_count) + (mem_price * memory_gb) + (storage_price * storage_gb) + gpu_price) * hours

    return round(total_cost, 2), days

# Initialize session state keys
def init_session_state():
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
    if "billing_client" not in st.session_state:
        st.session_state.billing_client = None
    if "skus_price_map" not in st.session_state:
        st.session_state.skus_price_map = {}

init_session_state()

# Initialize billing client and pricing SKUs once
if not st.session_state.billing_client:
    st.session_state.billing_client = init_billing_client()

BILLING_ACCOUNT_ID = st.secrets.get("billing_account_id", None)

if st.session_state.billing_client and BILLING_ACCOUNT_ID and not st.session_state.skus_price_map:
    st.session_state.skus_price_map = fetch_pricing_skus(st.session_state.billing_client, BILLING_ACCOUNT_ID)

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
            memory = st.number_input(
                "Memory (GB)",
                min_value=1,
                max_value=1024,
                step=1,
                help="Amount of RAM required in GB",
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
                memory=memory,
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
            "Example: 'I need 8 vCPUs, 32 GB RAM, 100 GB storage, T4 GPU for AI hackathon in us-central1 from Aug 20 to Sept 5, budget 1500 USD, monitoring yes.'"
        )
        raw_text = st.text_area("Describe your infrastructure needs")
        if st.button("Submit Chatbot"):
            if raw_text.strip():
                st.info("Extracting fields from free text using Gemini. Please wait...")
                parsed_fields = call_gemini_extract_fields(raw_text, env, purpose)
                if "error" in parsed_fields:
                    st.warning("Could not extract details from text. Please check your input.")
                else:
                    parsed_fields["environment"] = env
                    parsed_fields["purpose"] = purpose
                    if "memory" not in parsed_fields:
                        parsed_fields["memory"] = 0
                    user_data = parsed_fields
            else:
                st.warning("Please enter your requirement details")
    if user_data:
        st.session_state.user_fields = user_data
        st.session_state.page = "recommendation"
        st.session_state.genai_result = {}
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

    NUM_COLS = 3
    st.markdown("---")
    st.write("Select resources to keep:")

    checkbox_cols = st.columns(NUM_COLS)
    field_names = ["compute", "memory", "storage", "budget"]
    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "memory": {"label": "Memory (GB)", "min": 1, "max": 1024, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 1, "max": 20000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100},
    }
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
                defaults = {"compute": 4, "memory": 16, "storage": 100, "budget": 1000}
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

    region = editable_rec.get("region", "us-central1")
    cost, duration_days = estimate_billing_cost_from_api(editable_rec, region, st.session_state.skus_price_map)
    st.markdown(f"**Estimated billing cost for {duration_days} days: ${cost}**")

    other_fields = [k for k in editable_rec.keys() if k not in editable_fields]
    if other_fields:
        st.markdown("---")
        st.write("Other configuration options:")
        other_cols = st.columns(NUM_COLS)
        for i, field in enumerate(other_fields):
            col = other_cols[i % NUM_COLS]
            val = editable_rec.get(field, "")

            display_val = ""
            if isinstance(val, dict):
                for k in ("value", "amount", "answer", "option", "selection"):
                    if k in val:
                        display_val = val[k]
                        break
                else:
                    display_val = ", ".join(str(v) for v in val.values())
            elif isinstance(val, list):
                display_val = ", ".join(str(x) for x in val)
            else:
                display_val = val if val is not None else ""

            with col:
                if field == "monitoring":
                    choice = st.radio(
                        "Enable Monitoring?",
                        options=["Yes", "No"],
                        index=0 if str(display_val).lower() == "yes" else 1,
                        key=f"radio_{field}",
                    )
                    editable_rec[field] = choice
                elif field in ("start_date", "end_date"):
                    try:
                        dt = datetime.strptime(str(display_val), "%Y-%m-%d").date()
                    except Exception:
                        dt = date.today()
                    dt_val = st.date_input(
                        field.replace("_", " ").title(),
                        value=dt,
                        key=f"date_{field}",
                    )
                    editable_rec[field] = dt_val.strftime("%Y-%m-%d")
                elif field == "estimated_cost":
                    try:
                        cost_val = float(display_val)
                    except Exception:
                        cost_val = 0.0
                    st.number_input("Estimated Cost (USD)", value=cost_val, disabled=True, key="estimated_cost_display")
                    editable_rec[field] = cost_val
                else:
                    new_val = st.text_input(
                        field.replace("_", " ").title(),
                        value=str(display_val),
                        key=f"text_{field}",
                    )
                    editable_rec[field] = new_val

    st.markdown("---")
    if st.button("Accept and Submit"):
        st.success("Configuration accepted! Proceeding to approval...")

# Main app flow
if st.session_state.page == "input":
    show_input_page()
elif st.session_state.page == "recommendation":
    show_recommendation_page()
else:
    st.error(f"Unknown page state: {st.session_state.page}")
