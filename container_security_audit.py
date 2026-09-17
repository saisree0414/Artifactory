import os
import requests
import time
import smtplib
import html
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
from psycopg2.extras import execute_values
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import threading

# ==============================================================================
# PRODUCTION CONFIGURATION
# ==============================================================================
JFROG_URL = os.getenv("JFROG_URL", "https://JFROG.IO.com")
JFROG_TOKEN = os.getenv("JFROG_TOKEN", "<>TOKEN>")

SMTP_SERVER = os.getenv("SMTP_SERVER", "<smtp>>.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "25"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "BOBBY@gmail.com")
SUMMARY_RECIPIENT = "hero@gmail.com"
BCC_EMAIL = "test@gmail.com"

# PostgreSQL Database Configuration
DB_HOST = os.getenv("DB_HOST", "<DB-endpoint>>")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "container_security")
DB_USER = os.getenv("DB_USER", "<user>>")
DB_PASS = os.getenv("DB_PASS", "<add>>")

# Configure HTTP Session with Retries & Connection Pooling
session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=100, max_retries=retries)
session.mount('https://', adapter)
session.headers.update({
    "Authorization": f"Bearer {JFROG_TOKEN}",
    "Content-Type": "application/json"
})

USER_EMAIL_MAP = {}
REPO_EMAIL_MAP = defaultdict(set)
map_lock = threading.Lock()

# Global variables to capture statistics for summary email
TOTAL_REPOS_WITH_DEPLOYMENTS = 0
TOTAL_ACTIVE_MANIFESTS = 0
TOTAL_NON_COMPLIANT_REPOS = 0
TOTAL_NON_COMPLIANT_IMAGES = 0

# ==============================================================================
# POSTGRESQL PERSISTENCE
# ==============================================================================

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def save_records_to_postgres(records):
    """Batch updates/inserts image compliance records into PostgreSQL and prunes data older than 30 days."""
    if not records:
        print("[DB] No image records to insert.")
        return

    unique_records_map = {}
    for rec in records:
        key = (rec[0], rec[1], rec[5])  # (repo, image_path, created_time)
        unique_records_map[key] = rec

    deduped_records = list(unique_records_map.values())
    print(f"[DB] Deduplicated {len(records)} raw record(s) down to {len(deduped_records)} unique row(s).")

    insert_query = """
    INSERT INTO ci_west_image_compliance_audit (
        repository, image_path, is_compliant, has_vsad, has_build_user_email, deployed_time
    ) VALUES %s
    ON CONFLICT (repository, image_path, deployed_time)
    DO UPDATE SET
        is_compliant = EXCLUDED.is_compliant,
        has_vsad = EXCLUDED.has_vsad,
        has_build_user_email = EXCLUDED.has_build_user_email,
        scan_timestamp = CURRENT_TIMESTAMP;
    """

    # Cleanup query to remove records older than 30 days
    cleanup_query = """
    DELETE FROM ci_west_image_compliance_audit
    WHERE scan_timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days';
    """

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Execute Upsert
        execute_values(cursor, insert_query, deduped_records, page_size=1000)
        print(f"[DB SUCCESS] Upserted {len(deduped_records)} record(s) into 'ci_west_image_compliance_audit'.")

        # 2. Execute Retention Purge
        cursor.execute(cleanup_query)
        deleted_count = cursor.rowcount
        conn.commit()
        print(f"[DB CLEANUP] Successfully purged {deleted_count} record(s) older than 30 days.")

    except Exception as e:
        print(f"[DB ERROR] Insertion/Cleanup failed: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            cursor.close()
            conn.close()

# ==============================================================================
# DOCKER REPO SEARCH & AQL SCANNING
# ==============================================================================

def get_docker_repositories():
    """Fetch only federated repositories of package type 'docker'."""
    global TOTAL_DOCKER_REPOS
    print("[1/4] Fetching Docker-type FEDERATED repositories list from Artifactory...")
    
    # Filter by packageType=docker and type=federated
    url = f"{JFROG_URL}/artifactory/api/repositories?packageType=docker&type=federated"
    res = session.get(url)
    
    if res.status_code == 200:
        repos = [r["key"] for r in res.json()]
        TOTAL_DOCKER_REPOS = len(repos)
        print(f"      Identified {TOTAL_DOCKER_REPOS} Federated Docker repositories.")
        return repos
    else:
        print(f"[ERROR] Failed to fetch repositories: {res.text}")
        return []

def scan_docker_images(docker_repos, chunk_size=25):
    """Executes AQL scans in small chunks using valid $or syntax."""
    global TOTAL_ACTIVE_MANIFESTS, TOTAL_REPOS_WITH_DEPLOYMENTS
    print(f"[2/4] Executing AQL scan in chunks of {chunk_size} repositories...")
    aql_url = f"{JFROG_URL}/artifactory/api/search/aql"
    headers_aql = {"Authorization": f"Bearer {JFROG_TOKEN}", "Content-Type": "text/plain"}

    results = []

    for i in range(0, len(docker_repos), chunk_size):
        chunk = docker_repos[i:i + chunk_size]
        or_conditions = ", ".join([f'{{"repo": "{r}"}}' for r in chunk])
        aql_query = f'items.find({{"name": "manifest.json", "$or": [{or_conditions}], "created": {{"$last": "1d"}}}}).include("repo", "path", "created", "property.key")'

        response = session.post(aql_url, headers=headers_aql, data=aql_query)
        if response.status_code != 200:
            print(f"[AQL ERROR] Query failed ({response.status_code}) for chunk starting at index {i}: {response.text}")
            continue

        chunk_results = response.json().get("results", [])
        results.extend(chunk_results)

    TOTAL_ACTIVE_MANIFESTS = len(results)
    print(f"      Discovered {TOTAL_ACTIVE_MANIFESTS} active manifest deployment(s) across all chunks.")

    db_records = []
    non_compliant_map = defaultdict(list)

    for item in results:
        repo = item.get("repo")
        image_path = item.get("path")
        created_time = item.get("created")

        properties_data = item.get("properties", [])
        raw_keys = [p["key"] for p in properties_data if isinstance(p, dict) and "key" in p]

        normalized_keys = []
        for k in raw_keys:
            clean_k = k.lower()
            for prefix in ["docker.label.", "docker.property.", "docker.manifest.label.", "label."]:
                if clean_k.startswith(prefix):
                    clean_k = clean_k[len(prefix):]
            clean_k = clean_k.replace("-", "").replace(".", "").replace("_", "").replace(" ", "")
            normalized_keys.append(clean_k)

        has_vsad = "vsad" in normalized_keys
        has_email = "builduseremail" in normalized_keys
        is_compliant = has_vsad and has_email

        db_records.append((
            repo,
            image_path,
            is_compliant,
            has_vsad,
            has_email,
            created_time
        ))

        if not is_compliant:
            non_compliant_map[repo].append({
                "image_path": image_path,
                "created_time": created_time,
                "has_vsad": has_vsad,
                "has_email": has_email
            })
            
    # Count unique repositories that actually had manifest deployments
    TOTAL_REPOS_WITH_DEPLOYMENTS = len(set(r[0] for r in db_records))
    print(f"      Identified {TOTAL_REPOS_WITH_DEPLOYMENTS} repository/repositories with active deployments.")

    return db_records, non_compliant_map

# ==============================================================================
# ENHANCED OWNER PERMISSION RESOLUTION
# ==============================================================================

def preload_users_in_bulk():
    """Bulk loads all user emails into memory in 1 REST call."""
    print("      Bulk pre-loading platform user emails...")
    res = session.get(f"{JFROG_URL}/access/api/v2/users?limit=20000")
    if res.status_code == 200:
        users = res.json().get("users", [])
        for u in users:
            username = u.get("username")
            email = u.get("email")
            if username and email:
                USER_EMAIL_MAP[username] = email
        print(f"      Cached {len(USER_EMAIL_MAP)} user email records.")

def get_user_email_direct(username):
    """Direct REST fallback for user email if not found in cache."""
    if username in USER_EMAIL_MAP:
        return USER_EMAIL_MAP[username]
    try:
        res = session.get(f"{JFROG_URL}/access/api/v2/users/{username}")
        if res.status_code == 200:
            email = res.json().get("email")
            if email:
                with map_lock:
                    USER_EMAIL_MAP[username] = email
                return email
    except Exception:
        pass
    return None

def resolve_target_owners_for_non_compliant_repos(non_compliant_repos):
    """High-speed permission target resolution strictly for direct users."""
    if not non_compliant_repos:
        return

    print(f"[3/4] Resolving direct user permissions for {len(non_compliant_repos)} non-compliant repository/repositories...")
    preload_users_in_bulk()

    perm_url = f"{JFROG_URL}/artifactory/api/v2/security/permissions"
    res = session.get(perm_url)
    if res.status_code != 200:
        print(f"[ERROR] Failed to fetch permission targets: {res.text}")
        return

    perm_list = res.json().get("permissions", []) if isinstance(res.json(), dict) else res.json()

    def process_perm(perm):
        perm_name = perm.get("name") if isinstance(perm, dict) else perm
        d_res = session.get(f"{perm_url}/{perm_name}")
        if d_res.status_code != 200:
            return

        perm_detail = d_res.json()

        repo_sec = perm_detail.get("repo", {})
        repos = repo_sec.get("repositories", []) or perm_detail.get("repositories", []) or perm_detail.get("targets", [])

        explicit_repos = [r for r in repos if r not in ["ANY", "ANY LOCAL", "ANY REMOTE", "*"]]
        matched_repos = [r for r in explicit_repos if r in non_compliant_repos]

        if not matched_repos:
            return

        actions = repo_sec.get("actions", {}) or perm_detail.get("actions", {})
        users = list(actions.get("users", {}).keys())

        resolved_emails = set()

        for u in users:
            email = get_user_email_direct(u)
            if email:
                resolved_emails.add(email)

        with map_lock:
            for r in matched_repos:
                REPO_EMAIL_MAP[r].update(resolved_emails)

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(process_perm, perm_list)

# ==============================================================================
# EMAIL NOTIFICATIONS FUNCTION (STEP 4)
# ==============================================================================

def send_aggregated_email(repo, image_details_list, recipients):
    """Sends a styled HTML summary email per repository to associated users."""
    if not recipients or not image_details_list:
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = SENDER_EMAIL
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = f"Action Required: Tag Compliance Deficit in [{repo}]"

    text_body = f"Compliance Alert for Repository: {repo}\n\n"
    text_body += "The following Docker image(s) uploaded recently are missing required compliance tags:\n\n"
    for item in image_details_list:
        vsad_txt = "PRESENT" if item["has_vsad"] else "MISSING"
        email_txt = "PRESENT" if item["has_email"] else "MISSING"
        text_body += f"- Image: {item['image_path']}\n  Uploaded: {item['created_time']}\n  VSAD: {vsad_txt} | Build User Email: {email_txt}\n\n"
    text_body += "Please ensure required tags (VSAD and Build User Email) are attached via your CI/CD pipelines."

    image_rows_html = ""
    for item in image_details_list:
        path = item["image_path"]
        uploaded = item["created_time"]

        vsad_badge = '<span style="background-color: #DCFCE7; color: #166534; font-weight: 600; padding: 2px 8px; border-radius: 4px; font-size: 11px;">✓ Present</span>' if item["has_vsad"] else '<span style="background-color: #FEE2E2; color: #991B1B; font-weight: 600; padding: 2px 8px; border-radius: 4px; font-size: 11px;">✗ Missing</span>'
        email_badge = '<span style="background-color: #DCFCE7; color: #166534; font-weight: 600; padding: 2px 8px; border-radius: 4px; font-size: 11px;">✓ Present</span>' if item["has_email"] else '<span style="background-color: #FEE2E2; color: #991B1B; font-weight: 600; padding: 2px 8px; border-radius: 4px; font-size: 11px;">✗ Missing</span>'

        image_rows_html += f"""
        <tr>
            <td style="padding: 12px 15px; border-bottom: 1px solid #E2E8F0; font-family: monospace; font-size: 13px; color: #0F172A;">
                <strong>{path}</strong>
                <div style="font-size: 11px; color: #64748B; margin-top: 4px;">Uploaded: {uploaded}</div>
            </td>
            <td style="padding: 12px 15px; border-bottom: 1px solid #E2E8F0; text-align: center; white-space: nowrap;">
                {vsad_badge}
            </td>
            <td style="padding: 12px 15px; border-bottom: 1px solid #E2E8F0; text-align: center; white-space: nowrap;">
                {email_badge}
            </td>
        </tr>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 30px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="650" cellspacing="0" cellpadding="0" style="background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow: hidden;">
                        <tr>
                            <td style="background-color: #0F172A; padding: 24px 30px; text-align: left;">
                                <span style="background-color: #EF4444; color: #FFFFFF; font-size: 11px; font-weight: 700; padding: 4px 8px; border-radius: 4px; text-transform: uppercase;">Policy Violation</span>
                                <h2 style="color: #FFFFFF; font-size: 20px; margin: 12px 0 0 0; font-weight: 600;">Container Image Tagging Non-Compliance Alert</h2>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 30px;">
                                <p style="margin: 0 0 16px 0; color: #334155; font-size: 15px;">Hello Team,</p>
                                <p style="margin: 0 0 20px 0; color: #334155; font-size: 15px;">
                                    To maintain container security standards, images deployed to <strong>{repo}</strong> must include mandatory compliance labels. The following image(s) currently lack these labels and require remediation:
                                </p>
                                <table width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse; border: 1px solid #E2E8F0; border-radius: 6px; overflow: hidden; margin-bottom: 24px;">
                                    <thead>
                                        <tr style="background-color: #F1F5F9;">
                                            <th align="left" style="padding: 10px 15px; font-size: 12px; font-weight: 600; color: #475569; text-transform: uppercase;">Image Path</th>
                                            <th align="center" style="padding: 10px 15px; font-size: 12px; font-weight: 600; color: #475569; text-transform: uppercase;">VSAD Tag</th>
                                            <th align="center" style="padding: 10px 15px; font-size: 12px; font-weight: 600; color: #475569; text-transform: uppercase;">Build User Email</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {image_rows_html}
                                    </tbody>
                                </table>
                                <table width="100%" cellspacing="0" cellpadding="0">
                                    <tr>
                                        <td align="center" style="padding: 10px 0 20px 0;">
                                            <a href="{JFROG_URL}/ui/repos/tree/General/{repo}" target="_blank" style="background-color: #2563EB; color: #FFFFFF; font-size: 14px; font-weight: 600; text-decoration: none; padding: 12px 24px; border-radius: 6px; display: inline-block;">
                                                View Repository in Artifactory &rarr;
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                <p style="margin: 0; color: #64748B; font-size: 13px;">
                                    For more details refer: <a href="https://confluence/pages/1887916167/Container+Security+Policy" target="_blank" style="color: #2563EB; text-decoration: underline;">Container Security Policy Documentation</a>
                                </p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #F1F5F9; padding: 16px 30px; text-align: center; border-top: 1px solid #E2E8F0;">
                                <p style="margin: 0; font-size: 12px; color: #64748B;">
                                    Automated Governance Notification • <strong>JFrog Platform Administration</strong>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())
        print(f"-> Sent HTML notification for repo '{repo}' to {len(recipients)} user(s) (BCC: {BCC_EMAIL}): {recipients}")
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send email for repo '{repo}': {str(e)}")

# ==============================================================================
# COMPLETION SUMMARY EMAIL FUNCTION (STEP 5)
# ==============================================================================

def send_execution_summary_email():
    """Sends 4-statistic execution summary to designated recipient."""
    print("[5/5] Sending execution summary email...")
    
    today_date = datetime.now().strftime("%B %d, %Y")

    summary_text = (
        f"[1/4] Total Docker Repositories Identified: {TOTAL_DOCKER_REPOS}\n"
        f"[2/4] Total Active Manifest Deployments Scanned: {TOTAL_ACTIVE_MANIFESTS}\n"
        f"[3/4] Total Non-Compliant Repositories Identified: {TOTAL_NON_COMPLIANT_REPOS}\n"
        f"[3/4] Total Non-Compliant Container Images Identified: {TOTAL_NON_COMPLIANT_IMAGES}"
    )

    msg = MIMEMultipart('alternative')
    msg['From'] = SENDER_EMAIL
    msg['To'] = SUMMARY_RECIPIENT
    msg['Bcc'] = BCC_EMAIL
    msg['Subject'] = "Container Compliance Summary Report"

    text_body = f"Hello,\n\nThe Container Compliance Audit Scan has completed execution.\n\nExecution Statistics:\n{summary_text}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #F8FAFC; padding: 30px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="680" cellspacing="0" cellpadding="0" style="background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow: hidden;">
                        <tr>
                            <td style="background-color: #0F172A; padding: 24px 30px; text-align: left;">
                                <h2 style="color: #FFFFFF; font-size: 20px; margin: 12px 0 0 0; font-weight: 600;">Container Compliance Summary Report as on <strong>{today_date}</strong></h2>
                                <pre style="background-color: #0F172A; color: #38BDF8; padding: 18px; border-radius: 6px; font-family: 'Courier New', Courier, monospace; font-size: 16px; line-height: 1.6; overflow-x: auto; white-space: pre-wrap;">Total Repositories with Image Deployments: {TOTAL_REPOS_WITH_DEPLOYMENTS}
Total Images Deployed: {TOTAL_ACTIVE_MANIFESTS}
Total Non-Compliant Images: {TOTAL_NON_COMPLIANT_IMAGES}
Total Non-Compliant Repositories: {TOTAL_NON_COMPLIANT_REPOS}</pre>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    all_recipients = [SUMMARY_RECIPIENT, BCC_EMAIL]

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.sendmail(SENDER_EMAIL, all_recipients, msg.as_string())
        print(f"-> Sent completion summary email to {all_recipients}")
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send completion email: {str(e)}")

# ==============================================================================
# MAIN EXECUTION CONTROL
# ==============================================================================

def main():
    global TOTAL_NON_COMPLIANT_REPOS, TOTAL_NON_COMPLIANT_IMAGES

    print("==========================================================")
    print(" STARTING ENTERPRISE CONTAINER COMPLIANCE SCAN")
    print("=========================================================="  )

    # 1. Fetch Docker repos list
    docker_repos = get_docker_repositories()
    if not docker_repos:
        print("No Docker repositories found. Exiting.")
        send_execution_summary_email()
        return

    # 2. AQL Scan strictly for Docker repositories using small chunk size (25)
    db_records, non_compliant_map = scan_docker_images(docker_repos, chunk_size=25)

    # Calculate non-compliance statistics
    TOTAL_NON_COMPLIANT_REPOS = len(non_compliant_map)
    TOTAL_NON_COMPLIANT_IMAGES = sum(len(imgs) for imgs in non_compliant_map.values())

    # 3. Batch Write all evaluated records to PostgreSQL
    save_records_to_postgres(db_records)

    # 4. Resolve Target Owners ONLY for repositories with non-compliant images & send notifications
    if non_compliant_map:
        non_compliant_repos = set(non_compliant_map.keys())
        resolve_target_owners_for_non_compliant_repos(non_compliant_repos)

        print(f"[4/4] Dispatching notification emails across {TOTAL_NON_COMPLIANT_REPOS} repository/repositories...")
        for repo, image_details_list in non_compliant_map.items():
            recipients = list(REPO_EMAIL_MAP.get(repo, []))
            if not recipients:
                print(f"Skipping notification for repo '{repo}': No valid target user emails found in permission mappings.")
                continue

            send_aggregated_email(repo, image_details_list, recipients)
            time.sleep(1)
    else:
        print("[4/4] All scanned Docker images are compliant! No emails required.")

    print("==========================================================")
    print(" AUDIT SCAN COMPLETED SUCCESSFULLY")
    print("==========================================================")

    # 5. Send exact 4-statistic summary email
    send_execution_summary_email()

if __name__ == "__main__":
    main()
