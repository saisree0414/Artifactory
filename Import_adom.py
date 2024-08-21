#pip install ldap3
import subprocess
from ldap3 import Server, Connection, ALL, NTLM, SUBTREE

def search_ldap_group(server_url, ldap_user, ldap_password, search_base, group_name):
    """
    Search for an ADOM group in the LDAP server.
    
    :param server_url: URL of the LDAP server.
    :param ldap_user: LDAP username (e.g., DOMAIN\\username).
    :param ldap_password: LDAP user password.
    :param search_base: The base DN for the search.
    :param group_name: The name of the group to search for.
    :return: The distinguished name (DN) of the group if found, otherwise None.
    """
    try:
        # Connect to the LDAP server
        server = Server(server_url, get_info=ALL)
        conn = Connection(server, user=ldap_user, password=ldap_password, authentication=NTLM, auto_bind=True)
        
        # Search for the group
        conn.search(search_base, f'(cn={group_name})', search_scope=SUBTREE, attributes=['cn', 'distinguishedName'])
        
        if conn.entries:
            # If the group is found, return the distinguished name (DN)
            return conn.entries[0].distinguishedName.value
        else:
            print(f"Group '{group_name}' not found in LDAP server.")
            return None
    
    except Exception as e:
        print(f"An error occurred while searching LDAP: {str(e)}")
        return None
    finally:
        conn.unbind()

def import_group_to_artifactory(group_name, ldap_settings_key):
    """
    Imports an LDAP group into JFrog Artifactory.
    
    :param group_name: The name of the LDAP group to import.
    :param ldap_settings_key: The key of the LDAP settings configured in Artifactory.
    """
    try:
        # Construct the JFrog CLI command to add the LDAP group
        cmd = [
            "jfrog", "rt", "ldap-groups-create", 
            group_name, 
            "--ldap-setting-key", ldap_settings_key
        ]
        
        # Execute the command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check if the command was successful
        if result.returncode == 0:
            print(f"LDAP group '{group_name}' was successfully imported into Artifactory.")
        else:
            print(f"Failed to import LDAP group '{group_name}'. Error:\n{result.stderr}")
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    # LDAP server configuration
    ldap_server_url = "ldap://your_ldap_server"
    ldap_username = "DOMAIN\\your_username"
    ldap_password = "your_password"
    ldap_search_base = "DC=your_domain,DC=com"
    
    # Artifactory configuration
    ldap_settings_key = "your_ldap_settings_key"
    
    # Input ADOM group name
    adom_group_name = input("Enter the ADOM group name to import: ")
    
    # Search for the ADOM group in the LDAP server
    group_dn = search_ldap_group(ldap_server_url, ldap_username, ldap_password, ldap_search_base, adom_group_name)
    
    if group_dn:
        # Import the group to JFrog Artifactory if found in LDAP
        import_group_to_artifactory(adom_group_name, ldap_settings_key)
