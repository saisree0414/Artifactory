import requests

# Artifactory API endpoint and credentials
artifactory_url = "https://your-artifactory-url/artifactory"
username = "your-username"
password = "your-password"

# User and repository details
jfrog_user = "jfrog-username"
repository_key = "your-repo-key"

# Construct the API endpoint URL
api_url = f"{artifactory_url}/api/v2/security/permissions"

# Prepare the request headers and payload
headers = {
    "Content-Type": "application/json"
}
payload = {
    "principals": {
        "users": [jfrog_user]
    },
    "repositories": [repository_key],
    "actions": ["read"]
}

# Make the API request to grant read permissions
response = requests.post(api_url, auth=(username, password), headers=headers, json=payload)

# Check the response
if response.status_code == 201:
    print(f"Read access granted to {jfrog_user} for repository {repository_key}.")
else:
    print("Error granting permissions:", response.text)
