# 541

#imports
import google.generativeai as genai
import os
from typing import List, Dict, Optional
import json, random
from datetime import datetime, timedelta


class AIProcessor:
    def __init__(self, api_key: str = None):
        """
        initialize ai processor with gemini
        """
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None
            print("warning: no gemini api key provided, using dummy mode")

    def generate_dummy_email_data(self, email: str, name: str) -> List[Dict]:
        """
        generate realistic dummy email conversations for demo
        """
        #realistic conversation templates
        templates = [
            {
                "subject": "project update needed",
                "from": email,
                "to": "me@company.com",
                "body": f"hi, just wanted to check on the status of our website project. when can we expect the next deliverable? thanks, {name}",
                "days_ago": random.randint(1, 30)
            },
            {
                "subject": "re: project update needed",
                "from": "me@company.com",
                "to": email,
                "body": f"hi {name}, thanks for checking in. the design phase is complete and we're moving into development. expect the next update by friday.",
                "days_ago": random.randint(1, 30)
            },
            {
                "subject": "consulting services inquiry",
                "from": email,
                "to": "me@company.com",
                "body": f"i'm interested in your ai automation services for our customer support. can we schedule a call to discuss pricing and timeline? best, {name}",
                "days_ago": random.randint(15, 60)
            },
            {
                "subject": "follow up - analytics dashboard",
                "from": email,
                "to": "me@company.com",
                "body": f"the analytics dashboard you built is working great. we're seeing 30% improvement in our reporting efficiency. would like to discuss adding more features.",
                "days_ago": random.randint(5, 45)
            },
            {
                "subject": "payment processed",
                "from": "me@company.com",
                "to": email,
                "body": f"hi {name}, confirming we received your payment for the database optimization project. work will begin monday.",
                "days_ago": random.randint(10, 40)
            }
        ]

        # randomly select 2-4 conversations
        selected = random.sample(templates, random.randint(2, 4))

        conversations = []
        for template in selected:
            timestamp = datetime.now() - timedelta(days=template["days_ago"])
            conversations.append({
                'message_id': f"dummy_{random.randint(1000, 9999)}",
                'subject': template["subject"],
                'from': template["from"],
                'to': template["to"],
                'body': template["body"],
                'timestamp': timestamp.timestamp(),
                'date_str': timestamp.strftime('%a, %d %b %Y %H:%M:%S %z')
            })

        # sort by timestamp (newest first)
        conversations.sort(key=lambda x: x['timestamp'], reverse=True)
        return conversations

    def summarize_conversations(self, conversations: List[Dict], contact_name: str, contact_email: str) -> Dict:
        """
        use ai to summarize email conversations
        """
        if not conversations:
            return {
                'last_contact_date': None,
                'summary': 'no email conversations found',
                'services_used': 'none',
                'next_action': 'reach out to establish contact'
            }

        # prepare conversation text for ai
        conversation_text = self._format_conversations_for_ai(conversations, contact_name)

        if self.model:
            try:
                return self._generate_ai_summary(conversation_text, contact_name, contact_email)
            except Exception as e:
                print(f"ai summarization failed for {contact_email}: {e}")
                return self._generate_fallback_summary(conversations, contact_name)
        else:
            # fallback to rule-based summary
            return self._generate_fallback_summary(conversations, contact_name)

    def _format_conversations_for_ai(self, conversations: List[Dict], contact_name: str) -> str:
        """
        format conversations for ai processing
        """
        text = f"email conversation history with {contact_name}:\n\n"

        for conv in conversations:
            date = datetime.fromtimestamp(conv['timestamp']).strftime('%y-%m-%d')
            direction = "from client" if conv['from'] != "me@company.com" else "to client"
            text += f"[{date}] ({direction}) subject: {conv['subject']}\n"
            text += f"message: {conv['body'][:300]}...\n\n"

        return text

    def _generate_ai_summary(self, conversation_text: str, contact_name: str, contact_email: str) -> Dict:
        """
        generate ai summary using gemini
        """
        prompt = f"""
analyze this email conversation history and provide a structured summary:

{conversation_text}

provide a json response with these fields:
- last_contact_date: date of most recent interaction (yyyy-mm-dd format)
- summary: brief summary of the relationship and recent interactions (2-3 sentences)
- services_used: list the services or projects mentioned (comma separated)
- next_action: suggested next step or follow-up action

respond only with valid json, no other text.
"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # clean up response - remove markdown if present
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()

            # parse json response
            summary_data = json.loads(result_text)

            # validate required fields
            required_fields = ['last_contact_date', 'summary', 'services_used', 'next_action']
            for field in required_fields:
                if field not in summary_data:
                    summary_data[field] = 'not specified'

            return summary_data

        except Exception as e:
            print(f"error generating ai summary: {e}")
            # fallback to rule-based summary
            return self._generate_fallback_summary_from_text(conversation_text, contact_name)

    def _generate_fallback_summary(self, conversations: List[Dict], contact_name: str) -> Dict:
        """
        generate rule-based summary when ai fails
        """
        last_contact = datetime.fromtimestamp(conversations[0]['timestamp'])

        # extract services mentioned
        services = []
        all_text = " ".join([conv['body'] + " " + conv['subject'] for conv in conversations])
        service_keywords = ['website', 'dashboard', 'analytics', 'automation', 'ai', 'database', 'consulting',
                            'development']

        for keyword in service_keywords:
            if keyword in all_text.lower():
                services.append(keyword)

        # generate summary based on patterns
        recent_subjects = [conv['subject'] for conv in conversations[:3]]

        if any('payment' in subject.lower() for subject in recent_subjects):
            summary = f"active client relationship with {contact_name}. recent payment processed, project in progress."
        elif any('inquiry' in subject.lower() for subject in recent_subjects):
            summary = f"potential client {contact_name} has made service inquiries. opportunity for new business."
        else:
            summary = f"ongoing communication with {contact_name}. project updates and collaboration."

        return {
            'last_contact_date': last_contact.strftime('%Y-%m-%d'),
            'summary': summary,
            'services_used': ', '.join(services) if services else 'general consulting',
            'next_action': 'follow up on current project status'
        }

    def _generate_fallback_summary_from_text(self, conversation_text: str, contact_name: str) -> Dict:
        """
        simple text analysis fallback
        """
        lines = conversation_text.split('\n')
        dates = []

        for line in lines:
            if '[' in line and ']' in line:
                try:
                    date_str = line.split('[')[1].split(']')[0]
                    dates.append(date_str)
                except:
                    pass

        last_date = dates[0] if dates else '2024-01-01'

        return {
            'last_contact_date': last_date,
            'summary': f"conversation history available with {contact_name}. contains project communication and updates.",
            'services_used': 'consulting services',
            'next_action': 'review conversation details and follow up'
        }