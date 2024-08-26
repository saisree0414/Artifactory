from ldap3 import Server, Connection, ALL, NTLM, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError

# LDAP server configuration
LDAP_SERVER = 'ldap://your_ldap_server_address'
LDAP_USER = 'your_username'
LDAP_PASSWORD = 'your_password'
BASE_DN = 'dc=example,dc=com'  # Replace with your base DN
ADOM_GROUP = 'CN=your_adom_group,OU=Groups,DC=example,DC=com'  # Replace with your ADOM group DN

def check_adom_group_exists(server, user, password, base_dn, adom_group):
    try:
        # Connect to the LDAP server
        ldap_server = Server(server, get_info=ALL)
        connection = Connection(ldap_server, user=user, password=password, authentication=NTLM, auto_bind=True)

        # Search for the ADOM group
        search_filter = f'(distinguishedName={adom_group})'
        connection.search(base_dn, search_filter, search_scope=SUBTREE, attributes=['cn'])

        # Check if the ADOM group was found
        if connection.entries:
            print(f"The ADOM group '{adom_group}' exists in LDAP.")
            return True
        else:
            print(f"The ADOM group '{adom_group}' does not exist in LDAP.")
            return False

    except LDAPBindError as e:
        print("LDAP bind error:", e)
    except LDAPException as e:
        print("LDAP exception:", e)
    finally:
        # Close the connection
        connection.unbind()

# Example usage
check_adom_group_exists(LDAP_SERVER, LDAP_USER, LDAP_PASSWORD, BASE_DN, ADOM_GROUP)
