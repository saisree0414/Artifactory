import requests
import json

def get_virtual_repo_configurations(base_url, api_key):
    headers = {'X-JFrog-Art-Api': api_key}
    response = requests.get(f"{base_url}/artifactory/api/repositories?type=virtual", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch virtual repo configurations. Status code: {response.status_code}")
        return None

def compare_virtual_repo_configurations(config1, config2):
    differences = []
    for repo1 in config1:
        found = False
        for repo2 in config2:
            if repo1['key'] == repo2['key']:
                if repo1 != repo2:
                    differences.append(repo1)
                found = True
                break
        if not found:
            differences.append(repo1)
    return differences

def write_to_file(data, filename):
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)

if __name__ == "__main__":
    base_url_1 = "https://artifactory_instance1"
    base_url_2 = "https://artifactory_instance2"
    api_key_1 = "your_api_key1"
    api_key_2 = "your_api_key2"

    config1 = get_virtual_repo_configurations(base_url_1, api_key_1)
    config2 = get_virtual_repo_configurations(base_url_2, api_key_2)

    if config1 and config2:
        differences = compare_virtual_repo_configurations(config1, config2)
        if differences:
            write_to_file(differences, 'virtual_repo_differences.json')
            print("Virtual repository configuration differences found and written to virtual_repo_differences.json.")
        else:
            print("No differences found in virtual repository configurations.")
    else:
        print("Script execution failed.")
