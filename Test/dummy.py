import streamlit as st
from datetime import datetime, date
import requests
import json

st.set_page_config(page_title="GCP Infra Marketplace", layout='wide')

# --- ServiceNow Config from Streamlit Secrets ---
# Your secrets.toml should contain:
# [servicenow]
# instance_url = "https://yourinstance.service-now.com"
# user = "api_user"
# password = "api_password"

#SN_INSTANCE_URL = st.secrets["servicenow"]["instance_url"]
#SN_USER = st.secrets["servicenow"]["user"]
#SN_PASSWORD = st.secrets["servicenow"]["password"]

# Helper: Call ServiceNow API POST
def servicenow_api_post(api_path, payload):
    url = f"{SN_INSTANCE_URL}{api_path}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    try:
        response = requests.post(url, auth=(SN_USER, SN_PASSWORD), headers=headers, json=payload)
    except Exception as e:
        st.error(f"Error connecting to ServiceNow API: {e}")
        return None
    if not response.ok:
        st.error(f"ServiceNow API error {response.status_code}: {response.text}")
        return None
    return response.json()

# Create Change Request (CR) in ServiceNow for Production
def create_change_request(data):
    payload = {
        "short_description": f"Infra Request - {data.get('project_name','[No Name]')}",
        "description": json.dumps(data, indent=2),
        "category": "Infrastructure",
        "type": "Normal",
        "state": "New",
        # Add assignment_group, risk, impact as labels/fields your org requires
    }
    api_path = "/api/now/table/change_request"
    return servicenow_api_post(api_path, payload)

# Create Non-Production Approval Request in ServiceNow
def create_approval_request(data):
    payload = {
        "short_description": f"Infra Request - {data.get('project_name','[No Name]')}",
        "description": json.dumps(data, indent=2),
        # Adjust group, approvers based on your org & hierarchy logic
        # For example, "approval_group": "sys_id_of_approval_group"
    }
    api_path = "/api/now/table/your_custom_approval_table"  # Change this API path appropriately
    return servicenow_api_post(api_path, payload)

# Suggest Compute Engine Type based on vCPUs and GPU
def suggest_compute_engine(compute, gpu):
    if gpu and gpu != "None":
        return "A2, N1, or N2 machine types with attached GPU recommended for ML/AI workloads."
    elif compute >= 32:
        return "C2 (High-CPU) or N2 machine types suitable for compute-intensive workloads."
    elif compute >= 16:
        return "N2 or E2 machine types offer balance for medium workloads."
    else:
        return "E2 (General Purpose) instances recommended for light workloads."

# Main app starts here
st.title("GCP Infrastructure Marketplace")

# Environment and Purpose selection
env = st.selectbox("Select Environment", options=["Development", "QA", "Production", "Sandbox", "Other"])
purpose = st.selectbox("Select Purpose", options=["Lab", "Hackathon", "Development"])

st.markdown("---")

# Input mode: Structured form or chatbot free-text
mode = st.radio("Choose Input Method", options=["Web Form (Structured)", "Chatbot (Free Text)"])

# Initialize empty recommendation dict
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
        st.success("Recommendation generated! Please review the details below.")
else:
    # Chatbot input mode (placeholder)
    user_text = st.text_area("Describe your infrastructure requirements:")
    if st.button("Analyze"):
        if not user_text.strip():
            st.warning("Please enter your description.")
        else:
            # Here you would call your backend GenAI parsing API; demo mock below
            recommendation = {
                "project_name": "AI Hackathon Project",
                "description": user_text,
                "workload_type": "AI/ML",
                "compute": 16,
                "storage": 128,
                "gpu": "NVIDIA A100",
                "region": "us-central1",
                "start_date": date.today().strftime("%Y-%m-%d"),
                "end_date": (date.today().replace(day=date.today().day + 7)).strftime("%Y-%m-%d"),
                "budget": 2000,
                "special_needs": "",
                "environment": env,
                "purpose": purpose
            }
            st.success("AI parsing complete! Please review the recommendation below.")

# Recommendation Editing and Software Selection
if recommendation:
    st.markdown("---")
    st.header("Review and Customize Your Recommendation")

    editable_fields = {
        "compute": {"label": "vCPUs", "min": 1, "max": 128, "step": 1},
        "storage": {"label": "Storage (GB)", "min": 10, "max": 20000, "step": 10},
        "budget": {"label": "Budget (USD)", "min": 0, "max": 100000, "step": 100},
    }
    if "editable_rec" not in st.session_state:
        st.session_state.editable_rec = recommendation.copy()
    if "removed_fields" not in st.session_state:
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

    # Editable text and date fields
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

    # Compute Engine Suggestion
    st.subheader("Recommended Compute Engine Type")
    comp = st.session_state.editable_rec.get("compute", 4)
    gpu = st.session_state.editable_rec.get("gpu", "None")
    suggestion = suggest_compute_engine(comp, gpu)
    st.info(suggestion)

    st.markdown("---")

    # Display final config JSON for review
    st.subheader("Final Configuration")
    st.json(st.session_state.editable_rec)

    # Approval workflow explanation
    st.subheader("Approval Workflow")
    if env == "Production":
        st.info("""
            For the **Production** environment, a **Change Request (CR)** will be raised in ServiceNow. 
            You must follow your organization's change approval process prior to provisioning.
        """)
    else:
        st.info("""
            For non-production environments, the system will submit an approval request to ServiceNow 
            which follows a hierarchical approval workflow based on environment and purpose.
        """)

    if st.button("Submit for Approval & Start Procurement"):
        payload = st.session_state.editable_rec.copy()

        if env == "Production":
            cr_response = create_change_request(payload)
            if cr_response:
                cr_num = cr_response.get("result", {}).get("number", "N/A")
                st.success(f"Change Request created in ServiceNow: {cr_num}")
                st.info("Track this Change Request in ServiceNow for approval status.")
                # TODO: Optionally save CR number linked to user request.
            else:
                st.error("Failed to create Change Request in ServiceNow.")
        else:
            approval_response = create_approval_request(payload)
            if approval_response:
                approval_id = approval_response.get("result", {}).get("sys_id", "N/A")
                st.success(f"Approval request submitted: {approval_id}")
                st.info("Track approval status in ServiceNow dashboard.")
                # TODO: Optionally save Approval ID to track request
            else:
                st.error("Failed to submit approval request in ServiceNow.")

        # Optionally disable button or reset after success
        # Here, you might also trigger notification or provisioning pipelines post-approval.

