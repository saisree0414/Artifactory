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
EMAIL_SUBJECT = 'Repository Size Notification'
SMTP_SERVER = 'your_smtp_server'
SMTP_PORT = 587  # or 465 for SSL
SMTP_USER = 'your_smtp_user'
SMTP_PASS = 'your_smtp_password'

# Connect to the PostgreSQL database
def connect_db():
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

# Fetch oversized repositories from the repodata table
def fetch_oversized_repos(conn):
    cursor = conn.cursor()
    query = "SELECT repo_name, size_gb FROM repodata WHERE size_gb > 1000;"
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return result

# Update the notification table based on oversized repos
def update_notification_table(conn, oversized_repos):
    cursor = conn.cursor()
    today = datetime.date.today()
    for repo_name, size_gb in oversized_repos:
        cursor.execute("SELECT * FROM notification WHERE repo_name = %s;", (repo_name,))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(
                "INSERT INTO notification (repo_name, size_gb, last_notified) VALUES (%s, %s, %s);",
                (repo_name, size_gb, today)
            )
        else:
            cursor.execute(
                "UPDATE notification SET size_gb = %s, last_notified = %s WHERE repo_name = %s;",
                (size_gb, today, repo_name)
            )
    conn.commit()
    cursor.close()

# Get email addresses for oversized repositories
def get_email_addresses(conn, oversized_repos):
    cursor = conn.cursor()
    repo_names = tuple(repo[0] for repo in oversized_repos)
    query = f"SELECT email FROM emails WHERE repo_name IN {repo_names};"
    cursor.execute(query)
    result = cursor.fetchall()
    cursor.close()
    return [email[0] for email in result]

# Send email with notification table data as attachment
def send_email(to_emails, notification_data, email_subject):
    # Create a DataFrame and save as CSV
    df = pd.DataFrame(notification_data, columns=['Repo Name', 'Size (GB)'])
    csv_filename = 'notification.csv'
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

# Main function to control the workflow
def main():
    conn = connect_db()
    current_day = datetime.datetime.today().strftime('%A')
    oversized_repos = fetch_oversized_repos(conn)

    if current_day == 'Tuesday':
        update_notification_table(conn, oversized_repos)
        to_emails = get_email_addresses(conn, oversized_repos)
        if to_emails:
            send_email(to_emails, oversized_repos, EMAIL_SUBJECT)
        else:
            print('No email addresses found for oversized repositories on Tuesday.')

    elif current_day == 'Thursday':
        cursor = conn.cursor()
        cursor.execute("SELECT repo_name, size_gb FROM notification;")
        previous_notification = cursor.fetchall()
        cursor.close()

        relevant_repos = [repo for repo in oversized_repos if repo in previous_notification]
        update_notification_table(conn, relevant_repos)
        to_emails = get_email_addresses(conn, relevant_repos)
        if to_emails:
            send_email(to_emails, relevant_repos, 'Follow-up: ' + EMAIL_SUBJECT)
        else:
            print('No relevant oversized repositories found for Thursday check.')

    elif current_day == 'Monday' or current_day == 'Wednesday':
        cursor = conn.cursor()
        cursor.execute("SELECT repo_name, size_gb FROM notification;")
        previous_notification = cursor.fetchall()
        cursor.close()

        relevant_repos = [repo for repo in oversized_repos if repo in previous_notification]
        update_notification_table(conn, relevant_repos)
        to_emails = get_email_addresses(conn, relevant_repos)
        if to_emails:
            send_email(to_emails, relevant_repos, 'Follow-up: ' + EMAIL_SUBJECT)
        else:
            print('No relevant oversized repositories found for {} check.'.format(current_day))

    conn.close()

if __name__ == '__main__':
    main()
