import os
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from smtplib import SMTP

def get_artifacts(repo, path, duration):
    # Artifactory API endpoint
    artifactory_url = "https://your-artifactory-instance/artifactory/api/search/aql"

    # Construct AQL query based on input parameters
    aql_query = f"items.find({{\"repo\":\"{repo}\",\"path\":\"{path}\",\"created\":\"<{duration}\"}}).include(\"name\",\"repo\",\"path\",\"created\")"

    # Make a POST request to Artifactory AQL API
    response = requests.post(artifactory_url, auth=("your-username", "your-password"), data=aql_query)

    if response.status_code == 200:
        # Process the response, e.g., extract artifact details
        artifacts = response.json()["results"]
        return artifacts
    else:
        print(f"Failed to query Artifactory. Status code: {response.status_code}\nError: {response.text}")
        return None

def write_artifacts_to_file(artifacts, output_file):
    with open(output_file, 'w') as file:
        for artifact in artifacts:
            file.write(f"Repo: {artifact['repo']}, Path: {artifact['path']}, Name: {artifact['name']}, Created: {artifact['created']}\n")

def send_email_with_artifacts(output_file, to_email):
    subject = "Artifacts Report"
    body = "Please find the attached artifacts report."

    message = MIMEMultipart()
    message.attach(MIMEText(body, 'plain'))

    # Attach the artifacts file
    with open(output_file, 'rb') as file:
        attach = MIMEApplication(file.read(), _subtype="txt")
        attach.add_header('Content-Disposition', 'attachment', filename=os.path.basename(output_file))
        message.attach(attach)

    message['Subject'] = subject
    message['From'] = "your-email@gmail.com"  # Update with your email
    message['To'] = to_email

    # SMTP configuration for Gmail. Update for your email provider if needed.
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    smtp_username = "your-email@gmail.com"  # Update with your email
    smtp_password = "your-email-password"  # Update with your email password

    with SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.sendmail(message['From'], message['To'], message.as_string())

def main():
    # Extract parameters from Jenkins job environment
    repo = os.environ.get("REPO")
    path = os.environ.get("PATH")
    duration = os.environ.get("DURATION")
    email_recipient = os.environ.get("EMAIL_RECIPIENT")

    # Define the output file for artifact details
    output_file = "artifacts_report.txt"

    # Get artifacts based on parameters
    artifacts = get_artifacts(repo, path, duration)

    if artifacts:
        # Write artifacts to a file
        write_artifacts_to_file(artifacts, output_file)

        # Send email with artifacts attached
        send_email_with_artifacts(output_file, email_recipient)
        print("Artifacts report sent successfully.")
    else:
        print("Failed to retrieve artifacts.")

if __name__ == "__main__":
    main()
