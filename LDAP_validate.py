from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError

# Configuration for LDAP connection
LDAP_SERVER = 'ldap://your_ldap_server_address'
LDAP_USER = 'cn=your_username,dc=example,dc=com'  # Use the distinguished name of your user
LDAP_PASSWORD = 'your_password'
BASE_DN = 'dc=example,dc=com'  # Replace with your LDAP base DN
GROUP_NAME = 'your_adom_group_name'  # Name of the ADOM group to check

def check_adom_group_exists(server_address, user_dn, password, base_dn, group_name):
    try:
        # Define the server and the connection
        server = Server(server_address, get_info=ALL)
        connection = Connection(server, user=user_dn, password=password, auto_bind=True)

        # Search filter to find the group by its name
        search_filter = f'(&(objectClass=group)(cn={group_name}))'
        
        # Perform the search operation
        connection.search(search_base=base_dn, search_filter=search_filter, search_scope=SUBTREE, attributes=['cn'])

        # Check if the ADOM group was found
        if connection.entries:
            print(f"The ADOM group '{group_name}' exists in LDAP.")
            return True
        else:
            print(f"The ADOM group '{group_name}' does not exist in LDAP.")
            return False

    except LDAPBindError as e:
        print("LDAP bind error:", e)
        return False
    except LDAPException as e:
        print("LDAP exception:", e)
        return False
    finally:
        # Ensure the connection is closed
        if connection:
            connection.unbind()

# Example usage
if __name__ == "__main__":
    group_exists = check_adom_group_exists(LDAP_SERVER, LDAP_USER, LDAP_PASSWORD, BASE_DN, GROUP_NAME)
    if group_exists:
        print("Validation successful: The ADOM group exists.")
    else:
        print("Validation failed: The ADOM group does not exist.")
