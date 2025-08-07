from recommendation_ui import show_recommendation_ui

# Example recommendation dict from AI/backend
recommendation = {
    "project_name": "AI Project",
    "workload_type": "AI/ML",
    "compute": 16,
    "storage": 128,
    "gpu": "NVIDIA A100",
    "region": "us-central1",
    "start_date": "2025-08-01",
    "end_date": "2025-08-31",
    "budget": 2000,
    "special_needs": "None"
}

show_recommendation_ui(recommendation)
