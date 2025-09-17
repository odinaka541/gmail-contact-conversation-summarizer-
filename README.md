# AI Contact Automation Tool

A FastAPI-powered application that analyzes contact relationships using AI-generated summaries of email interactions.

## what it does

- upload a csv file with contact names and emails
- generates realistic conversation histories (demo mode)
- uses google gemini ai to analyze interactions
- provides summaries, service history, and next action recommendations
- exports results as csv

## technical stack

- **backend:** fastapi + python 3.11+
- **ai processing:** google gemini api
- **frontend:** vanilla html/javascript
- **deployment:** railway
- **data processing:** pandas + async background tasks

## features

- real-time processing progress tracking
- background job management
- error handling and validation
- csv export functionality
- responsive web interface

## setup

1. install dependencies:
```bash
pip install -r requirements.txt
```
2. create .env file
```bash
GEMINI_API_KEY=xxxxxxxxxxxxx
```
3. run locally (optional)
```bash
python main.py

# and visit http://localhost:8000
```
4. or just access via: https://gmail-contact-conversation-summarizer-production.up.railway.app/
5. note: csv format must be "name, email"
