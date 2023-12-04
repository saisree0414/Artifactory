import requests
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def fetch_artifacts(repository, duration, artifactory_url, username, password):
    base_url = f"{artifactory_url}/artifactory/api/search/aql"
    headers = {'Content-Type': 'text/plain'}

    # Calculate the date 6 months ago
    six_months_ago = datetime.now() - timedelta(days=180)
    formatted_date = six_months_ago.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # AQL query to find artifacts older than 6 months
    aql_query = f"""items.find(
        {{
            "repo": "{repository}",
            "created": {{"\$lt": "{formatted_date}"}}
        }}
    ).include("name", "repo", "path")"""

    response = requests.post(base_url, headers=headers, auth=(username, password), data=aql_query, verify=False)

    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch artifacts. Status code: {response.status_code}")
        return None

def write_to_file(file_path, content):
    with open(file_path, 'w') as file:
        file.write(content)

def send_email(to_email, subject, body, attachment_path=None):
    smtp_server = 'your_smtp_server'
    smtp_port = 587
    smtp_username = 'your_smtp_username'
    smtp_password = 'your_smtp_password'

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    if attachment_path:
        with open(attachment_path, 'rb') as attachment:
            part = MIMEApplication(attachment.read(), Name="artifacts_list.txt")
            part['Content-Disposition'] = f'attachment; filename="artifacts_list.txt"'
            msg.attach(part)

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, to_email, msg.as_string())

if __name__ == "__main__":
    repository_name = "your_repository"
    duration = "P6M"
    artifactory_url = "https://your-artifactory-instance"
    artifactory_username = "your_artifactory_username"
    artifactory_password = "your_artifactory_password"
    email_to = "recipient@example.com"

    artifacts = fetch_artifacts(repository_name, duration, artifactory_url, artifactory_username, artifactory_password)

    if artifacts:
        file_path = "artifacts_list.txt"
        write_to_file(file_path, artifacts)
        send_email(email_to, "Artifacts List - Older than 6 Months", "Please find attached the list of artifacts older than 6 months.", file_path)
        print("Email sent successfully.")
    else:
        print("Script execution failed.")
