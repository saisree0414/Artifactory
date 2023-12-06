import os
import requests
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def fetch_artifacts(repo, duration, path):
    artifactory_url = "https://your-artifactory-instance"
    username = "your_artifactory_username"
    password = "your_artifactory_password"

    base_url = artifactory_url + "/artifactory/api/search/aql"
    headers = {'Content-Type': 'text/plain'}

    # Calculate the date based on the provided duration
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(duration))
    formatted_start_date = start_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    formatted_end_date = end_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    # AQL query to find artifacts within the specified duration and path
    aql_query = f'''items.find(
        {{
            "repo": "{repo}",
            "path": {{"\$match": "{path}"}},
            "created": {{"\$lt": "{formatted_start_date}"}}
        }}
    ).include("name", "repo", "path")'''

    response = requests.post(base_url, headers=headers, auth=(username, password), data=aql_query, verify=False)

    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to fetch artifacts. Status code: {response.status_code}")
        return None

def write_to_file(content):
    with open('artifacts_list.txt', 'w') as file:
        file.write(content)

def send_email(to_email, subject, body):
    smtp_server = 'your_smtp_server'
    smtp_port = 587
    smtp_username = 'your_smtp_username'
    smtp_password = 'your_smtp_password'

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(smtp_username, [to_email], msg.as_string())

if __name__ == "__main__":
    repo = os.environ.get('repo', 'default_repo')
    duration = os.environ.get('duration', '30')  # Default to 30 days
    path = os.environ.get('path', '/default/path')

    artifacts = fetch_artifacts(repo, duration, path)

    if artifacts:
        write_to_file(artifacts)
        build_user_email = os.environ.get('BUILD_USER_EMAIL', 'default_email@example.com')
        send_email(build_user_email, "Artifacts List - Older than Specified Duration", "Please find attached the list of artifacts older than the specified duration.", "artifacts_list.txt")
        print("Email sent successfully.")
    else:
        print("Script execution failed.")
