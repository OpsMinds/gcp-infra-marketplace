import streamlit as st
from datetime import datetime, date
import requests
import json

st.set_page_config(page_title="GCP Infra Marketplace", layout='wide')

# --- ServiceNow Config from Streamlit Secrets ---
# Your secrets.toml should contain:
# [servicenow]
# instance_url = "https://yourinstance.service-now.com"
# user = "your_servicenow_user"
# password = "your_servicenow_password"

#SN_INSTANCE_URL = st.secrets["servicenow"]["instance_url"]
#SN_USER = st.secrets["servicenow"]["user"]
#SN_PASSWORD = st.secrets["servicenow"]["password"]

def servicenow_api_post(api_path, payload):
    url = f"{SN_INSTANCE_URL}{api_path}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    response = requests.post(url, auth=(SN_USER, SN_PASSWORD), headers=headers, json=payload)
    if not response.ok:
        st.error(f"ServiceNow API error {response.status_code}: {response.text}")
        return None
    return response.json()

# --- Constants ---
ENVIRONMENTS = ["Development", "QA", "Production", "Sandbox", "Other"]
PURPOSES = ["Lab", "Hackathon", "Development"]

# --- Utility functions ---

def create_change_request(data):
    """Create a ServiceNow Change Request (for Production workflow)."""
    payload = {
        "short_description": f"Infra Request - {data['project_name']}",
        "description": json.dumps(data, indent=2),
        "category": "Infrastructure",
        "type": "Normal",
        "state": "New",
        # Add additional required fields like assignment_group, risk, impact, etc.
    }
    api_path = "/api/now/table/change_request"
    result = servicenow_api_post(api_path, payload)
    return result

def create_approval_request(data):
    """Create Approval Workflow in ServiceNow for non-production."""
    payload = {
        "short_description": f"Infra Request - {data['project_name']}",
        "description": json.dumps(data, indent=2),
        "approval_group": "Your Approval Group Sys ID",  # Customize per your hierarchy rules
        # Add other fields as per your ServiceNow approval form API
    }
    api_path = "/api/now/table/your_custom_approval_table"  # Change to your approval table API path
    result = servicenow_api_post(api_path, payload)
    return result

# --- Main Streamlit app ---

st.title("GCP Infrastructure Marketplace")

# Select Environment and Purpose
env = st.selectbox("Select Environment", ENVIRONMENTS)
purpose = st.selectbox("Select Purpose", PURPOSES)

st.markdown(
    """
    ---
    """
)

# Dual input method: Web Form or Chatbot Input
mode = st.radio("Choose Input Method", options=["Web Form (Structured)", "Chatbot (Free Text)"])

recommendation = {}

if mode == "Web Form (Structured)":
    with st.form("structured_form"):
        project_name = st.text_input("Project Name", help="Name your project")
        description = st.text_area("Project Description")
        workload_type = st.selectbox("Workload Type", ["Batch", "Service", "AI/ML", "Storage", "Other"])
        compute = st.number_input("Compute (vCPUs)", min_value=1, max_value=128, step=1)
        storage = st.number_input("Storage (GB)", min_value=0, step=1)
        gpu = st.selectbox("GPU Type", ["None", "NVIDIA A100", "NVIDIA T4", "NVIDIA V100"])
        region = st.selectbox("Region", ["us-central1", "us-east1", "europe-west1", "asia-east1"])
        start_date = st.date_input("Start Date", min_value=date.today())
        end_date = st.date_input("End Date", min_value=start_date)
        budget = st.number_input("Budget (USD)", min_value=0)
        special_needs = st.text_area("Special Needs")
        submitted = st.form_submit_button("Get Recommendation")

    if submitted:
        recommendation = {
            "project_name": project_name,
            "description": description,
            "workload_type": workload_type,
            "compute": compute,
            "storage": storage,
            "gpu": gpu,
            "region": region,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "budget": budget,
            "special_needs": special_needs,
            "environment": env,
            "purpose": purpose
        }
        st.success("Recommendation generated! Please review below.")
else:
    # Chatbot mode: user enters free-text for AI parsing - Placeholder implementation
    user_text = st.text_area("Describe your infrastructure needs:")
    if st.button("Analyze"):
        if not user_text.strip():
            st.warning("Please enter a description to analyze.")
        else:
            # Here you would call your GenAI or backend API to parse and get recommendation
            # For demo, mock a recommendation
            recommendation = {
                "project_name": "AI Hackathon Project",
                "description": user_text,
                "workload_type": "AI/ML",
                "compute": 16,
                "storage": 128,
                "gpu": "NVIDIA A100",
                "region": "us-central1",
                "start_date": date.today().strftime("%Y-%m-%d"),
                "end_date": (date.today().replace(day=date.today().day+7)).strftime("%Y-%m-%d"),
                "budget": 2000,
                "special_needs": "",
                "environment": env,
                "purpose": purpose
            }
            st.success("AI parsing complete! Please review below.")

# --- Recommendation Review & Editing UI ---

if recommendation:
    st.markdown("---")
    st.header("Review and Customize Your Recommendation")

    # Sliders and checkboxes for resource customization
    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 10, "max": 10000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100},
    }
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
            defaults = {"compute": 4, "storage": 100, "budget": 1000}
            if field not in st.session_state.editable_rec:
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
                    val = date.today()
                new_val = st.date_input(field.replace("_", " ").title(), value=val, key=f"date_{field}")
                st.session_state.editable_rec[field] = new_val.strftime("%Y-%m-%d")
            else:
                new_val = st.text_input(
                    field.replace("_", " ").title(),
                    value=st.session_state.editable_rec[field],
                    key=f"text_{field}"
                )
                st.session_state.editable_rec[field] = new_val

    # Software selection before provisioning
    st.markdown("---")
    st.header("Select Software to Pre-Install on the Server")

    software_options = ["Docker", "Python 3.10", "Node.js", "TensorFlow", "VS Code", "Jupyter Lab"]
    selected_software = st.multiselect("Select software:", software_options)
    custom_software = st.text_input("Other software (comma separated):")
    custom_sw_list = [x.strip() for x in custom_software.split(",") if x.strip()]
    full_software_list = selected_software + custom_sw_list
    st.write("You have selected:", ", ".join(full_software_list) if full_software_list else "None")

    st.session_state.editable_rec["software_to_install"] = full_software_list

    st.markdown("---")

    # Display approval workflow info
    st.subheader("Approval Workflow")

    if env == "Production":
        approval_description = """
        For **Production** environment, a Change Request (CR) will be raised in ServiceNow.
        You must follow the change approval process before provisioning.
        """
    else:
        approval_description = """
        For non-production environments, an approval form will be submitted to a ServiceNow approval workflow.
        The approval hierarchy depends on the selected environment and purpose.
        """
    st.info(approval_description)

    # Button to submit approval requests to ServiceNow
    if st.button("Submit for Approval & Start Procurement"):
        st.info("Submitting your request to ServiceNow...")
        payload = st.session_state.editable_rec.copy()

        if env == "Production":
            # Create Change Request
            cr_response = create_change_request(payload)
            if cr_response:
                cr_number = cr_response.get("result", {}).get("number", "N/A")
                st.success(f"Change Request created successfully: {cr_number}")
                st.info("Please track this CR for approval status before provisioning.")
            else:
                st.error("Failed to create Change Request in ServiceNow.")
        else:
            # Create Approval Request for Non-production
            approval_response = create_approval_request(payload)
            if approval_response:
                approval_id = approval_response.get("result", {}).get("sys_id", "N/A")
                st.success(f"Approval request submitted: {approval_id}")
                st.info("Track approval status in your ServiceNow dashboard.")
            else:
                st.error("Failed to submit approval request in ServiceNow.")

        # Optionally here: save request info/log or enable next steps on UI (e.g., provisioning)

