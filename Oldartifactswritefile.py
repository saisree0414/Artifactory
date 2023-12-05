import requests
import os
from datetime import datetime, timedelta

def get_old_artifacts(repo, duration, path):
    # Calculate the date based on the provided duration
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=duration)

    # Format the date for AQL query
    start_date_str = start_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_date_str = end_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # JFrog Artifactory API endpoint and AQL query
    artifactory_url = 'https://your-artifactory-instance/artifactory/api/search/aql'
    aql_query = f'items.find({{"repo":"{repo}","path":"{path}","created":{{"$lt":"{end_date_str}","$gt":"{start_date_str}"}}}}).include("name","repo","path","created")'

    # Set up authentication details
    auth = ('your_username', 'your_api_key')

    # Make the API request
    response = requests.post(artifactory_url, auth=auth, data=aql_query)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response and write artifacts to a file
        artifacts = response.json()['results']
        with open('artifacts.txt', 'w') as file:
            for artifact in artifacts:
                file.write(f"Repo: {artifact['repo']}, Path: {artifact['path']}, Name: {artifact['name']}, Created: {artifact['created']}\n")
        print(f"Artifacts written to artifacts.txt")
    else:
        print(f"Error: {response.status_code}, {response.text}")

# Example usage
get_old_artifacts(repo='your-repo', duration=30, path='your-path')
