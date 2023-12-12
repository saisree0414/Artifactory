#python script_name.py --repo your_repository --modified-duration 6M --path your_artifact_path --output-file output.txt


import requests
import argparse

# Function to execute AQL query and retrieve artifacts
def get_artifacts_from_artifactory(repo, modified_duration, path, output_file):
    # JFrog Artifactory base URL
    artifactory_url = "https://your-artifactory-instance/artifactory/api"

    # Set your Artifactory API key or username/password for authentication
    headers = {"Authorization": "Bearer YOUR_ACCESS_TOKEN"}

    # AQL query to search for artifacts based on input parameters
    aql_query = f'items.find({{"repo":"{repo}","$or":{{"$and":{{"created":{{"$before":"{modified_duration}"}}}},"$and":{{"modified":{{"$before":"{modified_duration}"}}}}}},"path":"{path}"}})'

    # Artifactory API endpoint for AQL search
    endpoint = f'{artifactory_url}/search/aql'

    # Prepare the request payload
    data = {"aql": aql_query}

    try:
        # Execute the AQL query
        response = requests.post(endpoint, headers=headers, json=data)
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
    args = parser.parse_args()

    # Call the function with provided input parameters
    get_artifacts_from_artifactory(args.repo, args.modified_duration, args.path, args.output_file)
