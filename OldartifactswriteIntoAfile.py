#python script_name.py --repo your_repository --modified-duration 6M --path your_artifact_path --output-file output.txt --username your_username --password your_password --artifactory-url https://your-artifactory-instance/artifactory

import requests
import argparse
from requests.auth import HTTPBasicAuth

# Function to execute AQL query and retrieve artifacts
def get_artifacts_from_artifactory(repo, modified_duration, path, output_file, username, password, artifactory_url):
    # Artifactory API endpoint for AQL search
    endpoint = f'{artifactory_url}/search/aql'

    # AQL query to search for artifacts based on input parameters
    aql_query = f'items.find({{"repo":"{repo}","$or":{{"$and":{{"created":{{"$before":"{modified_duration}"}}}},"$and":{{"modified":{{"$before":"{modified_duration}"}}}}}},"path":"{path}"}})'

    # Prepare the request payload
    data = {"aql": aql_query}

    # Prepare the authentication credentials
    auth = HTTPBasicAuth(username, password)

    try:
        # Execute the AQL query
        response = requests.post(endpoint, auth=auth, json=data)
        response.raise_for_status()

        # Parse the response and write the results to a text file
        artifacts = response.json()["results"]
        with open(output_file, "w") as file:
            for artifact in artifacts:
                file.write(f'{artifact["repo"]}/{artifact["path"]}/{artifact["name"]}\n')

        print(f"Artifacts list written to {output_file}")

    except requests.exceptions.RequestException as e:
        print(f"Error retrieving artifacts: {e}")

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Get list of artifacts from JFrog Artifactory using AQL.")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--modified-duration", required=True, help="Modified duration (e.g., 1d, 2w)")
    parser.add_argument("--path", required=True, help="Artifact path")
    parser.add_argument("--output-file", required=True, help="Output text file for artifacts list")
    parser.add_argument("--username", required=True, help="Artifactory username")
    parser.add_argument("--password", required=True, help="Artifactory password")
    parser.add_argument("--artifactory-url", required=True, help="Artifactory base URL")
    args = parser.parse_args()

    # Call the function with provided input parameters
    get_artifacts_from_artifactory(args.repo, args.modified_duration, args.path, args.output_file, args.username, args.password, args.artifactory_url)
