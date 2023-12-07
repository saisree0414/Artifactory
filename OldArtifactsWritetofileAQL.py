import requests
import os
from datetime import datetime, timedelta

def get_old_artifacts(repo, path, duration, exclude_artifact):
    # Calculate the date 6 months ago from today
    six_months_ago = datetime.now() - timedelta(days=180)
    
    # Format the date in the required format for AQL
    six_months_ago_str = six_months_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    # Artifactory AQL query
    aql_query = f"items.find({{'repo':'{repo}','path':'{path}','created':'< {six_months_ago_str}','name':{{'$nmatch':'{exclude_artifact}'}}}}).include('name','repo','path','created')"
    
    # Artifactory API endpoint
    artifactory_url = "https://your-artifactory-instance/artifactory/api/search/aql"

    # Make a POST request to Artifactory AQL API
    response = requests.post(artifactory_url, auth=("your-username", "your-password"), data=aql_query)

    if response.status_code == 200:
        # Process the response, e.g., extract artifact details
        artifacts = response.json()["results"]
        return artifacts
    else:
        print(f"Failed to query Artifactory. Status code: {response.status_code}\nError: {response.text}")
        return None

def write_artifacts_to_file(artifacts, output_file):
    with open(output_file, 'w') as file:
        for artifact in artifacts:
            file.write(f"Repo: {artifact['repo']}, Path: {artifact['path']}, Name: {artifact['name']}, Created: {artifact['created']}\n")

def main():
    # Inputs from Jenkins parameters or user input
    repo = "your-repo"
    path = "your/path/to/artifacts"
    duration = "6months"
    exclude_artifact = "exclude_this_artifact"
    output_file = "artifacts_report.txt"

    # Get old artifacts based on parameters
    artifacts = get_old_artifacts(repo, path, duration, exclude_artifact)

    if artifacts:
        # Write artifacts to a file
        write_artifacts_to_file(artifacts, output_file)
        print("Artifacts report written to file successfully.")
    else:
        print("Failed to retrieve artifacts.")

if __name__ == "__main__":
    main()
