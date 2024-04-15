import requests

def check_artifact_in_trashcan(artifact_path, artifactory_url, username, password):
    # Construct the AQL query to check if the artifact exists in the trashcan
    aql_query = f"items.find({{'repo':'trash', 'path':'{artifact_path}'}})"
    
    # Construct the URL for executing AQL query
    aql_api_endpoint = f"{artifactory_url}/api/search/aql"
    
    # Make a POST request to execute the AQL query
    response = requests.post(aql_api_endpoint, auth=(username, password), data=aql_query)
    
    # Check if the request was successful and if the artifact exists in the trashcan
    if response.status_code == 200:
        # Parse the response to check if any items were returned
        items = response.json()["results"]
        return len(items) > 0
    else:
        # Handle other response codes if needed
        return False

def restore_artifact_from_trashcan(artifact_path, artifactory_url, username, password):
    # Construct the URL for restoring the artifact from the trashcan
    restore_api_endpoint = f"{artifactory_url}/api/trash/restore/{artifact_path}"
    
    # Make a POST request to restore the artifact from the trashcan
    response = requests.post(restore_api_endpoint, auth=(username, password))
    
    # Check if the request was successful
    if response.status_code == 200:
        print("Artifact restored successfully!")
    else:
        print("Failed to restore artifact.")

# Example usage
artifact_path = "path/to/your/artifact"
artifactory_url = "https://your.artifactory.url"
username = "your_username"
password = "your_password"

# Check if the artifact exists in the trashcan
if check_artifact_in_trashcan(artifact_path, artifactory_url, username, password):
    # Restore the artifact from the trashcan
    restore_artifact_from_trashcan(artifact_path, artifactory_url, username, password)
else:
    print("Artifact not found in the trashcan.")
