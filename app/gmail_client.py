# 541

# imports
import os, pickle, base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import re
from email.mime.text import MIMEText

# gmail api scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    def __init__(self):
        self.service = None
        self.credentials = None

    def authenticate(self, credentials_file: str = "credentials.json") -> str:
        """
        authenticate with gmail api
        returns authorization url if user needs to authorize
        """
        creds = None

        # check if we have stored credentials
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        # if no valid credentials, start oauth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_file):
                    raise Exception(f"credentials file {credentials_file} not found")

                flow = Flow.from_client_secrets_file(
                    credentials_file, SCOPES)
                flow.redirect_uri = 'http://localhost:8000/auth/callback'

                auth_url, _ = flow.authorization_url(prompt='consent')
                return auth_url

            # save credentials for next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        self.credentials = creds
        self.service = build('gmail', 'v1', credentials=creds)
        return None

    def complete_auth(self, authorization_code: str, credentials_file: str = "credentials.json"):
        """
        complete oauth flow with authorization code
        """
        flow = Flow.from_client_secrets_file(
            credentials_file, SCOPES)
        flow.redirect_uri = 'http://localhost:8000/auth/callback'

        flow.fetch_token(code=authorization_code)
        creds = flow.credentials

        # save credentials
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

        self.credentials = creds
        self.service = build('gmail', 'v1', credentials=creds)

    def search_conversations(self, email_address: str, months_back: int = 6) -> List[Dict]:
        """
        search for email conversations with specific contact
        returns list of email data
        """
        if not self.service:
            raise Exception("not authenticated with gmail")

        # calculate date range
        since_date = datetime.now() - timedelta(days=months_back * 30)
        since_str = since_date.strftime("%Y/%m/%d")

        # search query for emails to/from this contact
        query = f"(from:{email_address} OR to:{email_address}) after:{since_str}"

        try:
            # get message list
            result = self.service.users().messages().list(
                userId='me', q=query, maxResults=50).execute()

            messages = result.get('messages', [])

            conversations = []
            for msg in messages:
                try:
                    # get full message details
                    message = self.service.users().messages().get(
                        userId='me', id=msg['id']).execute()

                    email_data = self._parse_message(message)
                    if email_data:
                        conversations.append(email_data)

                except Exception as e:
                    print(f"error parsing message {msg['id']}: {e}")
                    continue

            # sort by date (newest first)
            conversations.sort(key=lambda x: x['timestamp'], reverse=True)
            return conversations

        except Exception as e:
            print(f"error searching conversations for {email_address}: {e}")
            return []

    def _parse_message(self, message: Dict) -> Optional[Dict]:
        """
        parse gmail message into structured data
        """
        try:
            payload = message['payload']
            headers = payload.get('headers', [])

            # extract headers
            subject = ""
            from_email = ""
            to_email = ""
            date_str = ""

            for header in headers:
                name = header['name'].lower()
                if name == 'subject':
                    subject = header['value']
                elif name == 'from':
                    from_email = header['value']
                elif name == 'to':
                    to_email = header['value']
                elif name == 'date':
                    date_str = header['value']

            # extract body
            body = self._extract_body(payload)

            # parse timestamp
            timestamp = self._parse_date(date_str)

            return {
                'message_id': message['id'],
                'subject': subject,
                'from': from_email,
                'to': to_email,
                'body': body,
                'timestamp': timestamp,
                'date_str': date_str
            }

        except Exception as e:
            print(f"error parsing message: {e}")
            return None

    def _extract_body(self, payload: Dict) -> str:
        """
        extract text body from email payload
        """
        body = ""

        if 'parts' in payload:
            # multipart message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        break
        else:
            # single part message
            if payload['mimeType'] == 'text/plain':
                data = payload['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        # clean up body text
        body = self._clean_email_body(body)
        return body

    def _clean_email_body(self, body: str) -> str:
        """
        clean email body text
        """
        # remove excessive whitespace
        body = re.sub(r'\n{3,}', '\n\n', body)
        body = re.sub(r' {2,}', ' ', body)

        # remove common email artifacts
        body = re.sub(r'On .* wrote:', '', body)
        body = re.sub(r'From: .*', '', body)
        body = re.sub(r'Sent: .*', '', body)
        body = re.sub(r'To: .*', '', body)
        body = re.sub(r'Subject: .*', '', body)

        return body.strip()

    def _parse_date(self, date_str: str) -> float:
        """
        parse email date string to timestamp
        """
        try:
            # gmail dates are in rfc2822 format
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.timestamp()
        except Exception:
            return 0.0

    def get_recent_conversations_summary(self, email_address: str) -> Dict:
        """
        get summary of recent conversations with contact
        """
        conversations = self.search_conversations(email_address)

        if not conversations:
            return {
                'contact_email': email_address,
                'last_contact_date': None,
                'total_messages': 0,
                'recent_messages': []
            }

        # get last contact date
        last_contact = datetime.fromtimestamp(conversations[0]['timestamp'])

        # get most recent 5 messages for summarization
        recent_messages = conversations[:5]

        return {
            'contact_email': email_address,
            'last_contact_date': last_contact.strftime('%Y-%m-%d'),
            'total_messages': len(conversations),
            'recent_messages': recent_messages
        }