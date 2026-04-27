#!/usr/bin/env python3
import os
import sys
from google.api_core.client_options import ClientOptions
from google.cloud import discoveryengine

def setup_viral_knowledge_base(project_id, location="global", data_store_id="viral-knowledge-base"):
    client_options = (
        ClientOptions(api_endpoint=f"{location}-discoveryengine.googleapis.com")
        if location != "global" else None
    )

    client = discoveryengine.DataStoreServiceClient(client_options=client_options)
    parent = client.collection_path(project=project_id, location=location, collection="default_collection")

    data_store = discoveryengine.DataStore(
        display_name="Viral Script Patterns",
        industry_vertical=discoveryengine.IndustryVertical.GENERIC,
        solution_types=[discoveryengine.SolutionType.SOLUTION_TYPE_SEARCH],
        content_config=discoveryengine.DataStore.ContentConfig.CONTENT_REQUIRED,
    )

    print(f"🚀 Creating Data Store: {data_store_id} in {project_id}...")
    try:
        operation = client.create_data_store(
            discoveryengine.CreateDataStoreRequest(
                parent=parent,
                data_store_id=data_store_id,
                data_store=data_store,
            )
        )
        print("Waiting for creation to complete...")
        operation.result()
        print(f"✅ SUCCESS! Data Store ID: {data_store_id}")
        return data_store_id
    except Exception as e:
        if "already exists" in str(e):
            print(f"ℹ️ Data Store {data_store_id} already exists. Using it.")
            return data_store_id
        else:
            print(f"❌ Error: {e}")
            return None

if __name__ == "__main__":
    pid = os.environ.get("DEVSHELL_PROJECT_ID")
    if not pid:
        print("❌ Please run in Cloud Shell or set DEVSHELL_PROJECT_ID.")
        sys.exit(1)
    
    setup_viral_knowledge_base(pid)
