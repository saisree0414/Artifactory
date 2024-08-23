import psycopg2
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import os
import datetime

# Database connection details
DB_HOST = 'your_db_host'
DB_NAME = 'your_db_name'
DB_USER = 'your_db_user'
DB_PASS = 'your_db_password'

# Email configuration
EMAIL_FROM = 'your_email@example.com'
EMAIL_SUBJECT = 'Weekly Repository Size Report'
SMTP_SERVER = 'your_smtp_server'
SMTP_PORT = 587  # or 465 for SSL
SMTP_USER = 'your_smtp_user'
SMTP_PASS = 'your_smtp_password'

# File to store the list of oversized repos
OVERSIZED_REPOS_FILE = 'oversized_repos.txt'

# Function to fetch data from the database
def fetch_repo_data():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    cursor = conn.cursor()
    query = """
    SELECT r.repo_name, r.size_gb, e.email
    FROM repository r
    JOIN email_table e ON r.repo_name = e.repo_name
    WHERE r.size_gb > 1000;
    """
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result

# Function to send email
def send_email(to_emails, repo_data, email_subject):
    # Create a DataFrame and save as CSV
    df = pd.DataFrame(repo_data, columns=['Repo Name', 'Size (GB)', 'Email'])
    csv_filename = 'oversized_repos.csv'
    df.to_csv(csv_filename, index=False)

    # Compose the email
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = ', '.join(to_emails)
    msg['Subject'] = email_subject

    body = 'Attached is the list of repositories exceeding 1000GB.'
    msg.attach(MIMEText(body, 'plain'))

    # Attach the CSV file
    with open(csv_filename, 'rb') as attachment:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={csv_filename}')
        msg.attach(part)

    # Send the email
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(EMAIL_FROM, to_emails, msg.as_string())

    # Clean up
    os.remove(csv_filename)

# Function to read oversized repos from file
def read_oversized_repos():
    if not os.path.exists(OVERSIZED_REPOS_FILE):
        return set()
    with open(OVERSIZED_REPOS_FILE, 'r') as file:
        repos = file.read().splitlines()
    return set(repos)

# Function to write oversized repos to file
def write_oversized_repos(repo_list):
    with open(OVERSIZED_REPOS_FILE, 'w') as file:
        for repo in repo_list:
            file.write(repo + '\n')

# Main function
def main():
    current_day = datetime.datetime.today().strftime('%A')
    repo_data = fetch_repo_data()
    oversized_repos = {row[0] for row in repo_data}  # Set of repo names
    email_subject = EMAIL_SUBJECT

    if current_day == 'Tuesday':
        # Write all oversized repos to the file
        write_oversized_repos(oversized_repos)
        if repo_data:
            to_emails = list(set([row[2] for row in repo_data]))
            send_email(to_emails, repo_data, email_subject)
        else:
            print('No repositories exceeding 1000GB found on Tuesday.')

    elif current_day == 'Thursday':
        # Read repos from file and check against current oversized repos
        previous_oversized_repos = read_oversized_repos()
        relevant_repos = [row for row in repo_data if row[0] in previous_oversized_repos]

        if relevant_repos:
            to_emails = list(set([row[2] for row in relevant_repos]))
            email_subject = 'Follow-up: ' + EMAIL_SUBJECT
            send_email(to_emails, relevant_repos, email_subject)
        else:
            print('No repositories need notification on Thursday.')

if __name__ == '__main__':
    main()
