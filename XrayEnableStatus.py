import requests
from requests.auth import HTTPBasicAuth

# JFrog Artifactory details
base_url = 'https://your_jfrog_instance/artifactory'
username = 'your_username'
api_token = 'your_api_token'

# Endpoint to get repositories
repos_endpoint = f'{base_url}/api/repositories'

# Function to get the list of repositories
def get_repos():
    response = requests.get(repos_endpoint, auth=HTTPBasicAuth(username, api_token))
    response.raise_for_status()
    return response.json()

# Function to check if Xray is enabled for a repository
def is_xray_enabled(repo_key):
    repo_config_endpoint = f'{base_url}/api/repositories/{repo_key}'
    response = requests.get(repo_config_endpoint, auth=HTTPBasicAuth(username, api_token))
    response.raise_for_status()
    repo_config = response.json()
    return repo_config.get('xrayIndex', False)

def main():
    repos = get_repos()
    xray_enabled_repos = []

    for repo in repos:
        repo_key = repo['key']
        if is_xray_enabled(repo_key):
            xray_enabled_repos.append(repo_key)
    
    print("Repositories with Xray enabled:")
    for repo in xray_enabled_repos:
        print(repo)

if __name__ == "__main__":
    main()



###############################

import requests
from requests.auth import HTTPBasicAuth

# JFrog Artifactory details
base_url = 'https://your_jfrog_instance/artifactory'
username = 'your_username'
api_token = 'your_api_token'
output_file = 'repos_with_xray_disabled.txt'

# Endpoint to get repositories
repos_endpoint = f'{base_url}/api/repositories'

# Function to get the list of repositories
def get_repos():
    response = requests.get(repos_endpoint, auth=HTTPBasicAuth(username, api_token))
    response.raise_for_status()
    return response.json()

# Function to check if Xray is enabled for a repository
def is_xray_enabled(repo_key):
    repo_config_endpoint = f'{base_url}/api/repositories/{repo_key}'
    response = requests.get(repo_config_endpoint, auth=HTTPBasicAuth(username, api_token))
    response.raise_for_status()
    repo_config = response.json()
    # Check if Xray indexing is enabled for the repository
    return repo_config.get('xrayIndex', False)

def main():
    repos = get_repos()
    xray_disabled_repos = []

    for repo in repos:
        repo_key = repo['key']
        if not is_xray_enabled(repo_key):
            xray_disabled_repos.append(repo_key)
    
    with open(output_file, 'w') as f:
        f.write("Repositories with Xray disabled:\n")
        for repo in xray_disabled_repos:
            f.write(f"{repo}\n")
    
    print(f"List of repositories with Xray disabled has been written to {output_file}")

if __name__ == "__main__":
    main()
