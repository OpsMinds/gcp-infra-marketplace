import streamlit as st
from datetime import date

# Placeholder imports for backend integration, replace with your actual functions
# from backend.api_client import parse_chat_input, submit_request

st.set_page_config(page_title="GCP Infra Marketplace", layout='centered')

st.title("GCP Infra Marketplace")

# Step 1: Mode selection radio buttons
mode = st.radio("Choose input method:", ["Web Form (Structured)", "Chatbot (Free Text)"])

if mode == "Web Form (Structured)":
    with st.form("structured_form"):
        project_name = st.text_input("Project Name", help="Enter your project name")
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

        submitted = st.form_submit_button("Submit Request")

    if submitted:
        # Collect form data
        form_data = {
            "project_name": project_name,
            "description": description,
            "workload_type": workload_type,
            "compute": compute,
            "storage": storage,
            "gpu": gpu,
            "region": region,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "budget": budget,
            "special_needs": special_needs
        }

        st.success("Form submitted. Processing your request...")
        # TODO: Call backend submit_request API here and handle response
        # response = submit_request(form_data)
        # st.json(response)

elif mode == "Chatbot (Free Text)":
    st.write(
        "Please describe your infrastructure request in natural language.\n"
        "Example: \"I need 16 vCPUs, 128GB storage, 1 NVIDIA A100 GPU for an AI/ML workload "
        "in us-central1 from Aug 1 to Aug 31 with a budget of $2000.\""
    )
    user_input = st.text_area("Your message here:")

    if st.button("Analyze & Recommend"):
        if not user_input.strip():
            st.warning("Please enter your message before clicking Analyze.")
        else:
            st.info("Sending your message for AI parsing and recommendation...")
            # TODO: Call backend parse_chat_input API passing user_input, get structured response
            # parsed_response = parse_chat_input(user_input)
            # For demo, using a dummy placeholder response:
            parsed_response = {
                "project_name": "Example Project",
                "workload_type": "AI/ML",
                "compute": 16,
                "storage": 128,
                "gpu": "NVIDIA A100",
                "region": "us-central1",
                "start_date": "2025-08-01",
                "end_date": "2025-08-31",
                "budget": 2000,
                "special_needs": "None",
                "missing_fields": []
            }
            st.success("AI Parsing completed!")

            # Show parsed information
            st.subheader("Parsed Configuration")
            st.json(parsed_response)

            # If there are missing fields, alert the user
            if parsed_response.get("missing_fields"):
                st.warning(f"Missing fields detected: {parsed_response['missing_fields']}")

            # TODO: Optionally allow user to submit this parsed config as a request (button)
            if st.button("Submit Parsed Configuration"):
                st.success("Submitting your infrastructure request...")
                # response = submit_request(parsed_response)
                # st.json(response)