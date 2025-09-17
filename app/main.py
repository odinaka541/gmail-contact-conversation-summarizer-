from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response, RedirectResponse
import pandas as pd
import os, uuid, json
from typing import List, Dict
from datetime import datetime
from gmail_client import GmailClient

app = FastAPI(title="AI Contact Automation", version="1.0.0")

# mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# in-memory storage for demo * db later
jobs = {}
results = {}
gmail_client = GmailClient()


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Contact Automation</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .upload-area { border: 2px dashed #ccc; padding: 40px; text-align: center; margin: 20px 0; }
            .status { padding: 10px; margin: 10px 0; border-radius: 5px; }
            .processing { background: #fff3cd; color: #856404; }
            .complete { background: #d4edda; color: #155724; }
            .error { background: #f8d7da; color: #721c24; }
            button { padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }
            button:hover { background: #0056b3; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f8f9fa; }
        </style>
    </head>
    <body>
        <h1>AI Contact Automation Tool</h1>
        <p>Upload a CSV with contact names and emails to get AI-powered summaries of your last interactions.</p>

        <div class="upload-area">
            <form id="uploadForm" enctype="multipart/form-data">
                <input type="file" id="csvFile" accept=".csv" required>
                <br><br>
                <button type="submit">Upload & Process</button>
            </form>
        </div>

        <div id="status" style="display: none;"></div>
        <div id="results" style="display: none;"></div>

        <script>
            let currentJobId = null;

            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const formData = new FormData();
                const fileInput = document.getElementById('csvFile');
                formData.append('file', fileInput.files[0]);

                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();

                    if (response.ok) {
                        currentJobId = data.job_id;
                        showStatus('Processing started...', 'processing');
                        checkProgress();
                    } else {
                        showStatus(data.detail, 'error');
                    }
                } catch (error) {
                    showStatus('Upload failed: ' + error.message, 'error');
                }
            });

            function showStatus(message, type) {
                const statusDiv = document.getElementById('status');
                statusDiv.innerHTML = `<div class="status ${type}">${message}</div>`;
                statusDiv.style.display = 'block';
            }

            async function checkProgress() {
                if (!currentJobId) return;

                try {
                    const response = await fetch(`/status/${currentJobId}`);
                    const data = await response.json();

                    if (data.status === 'processing') {
                        showStatus(`Processing... ${data.progress}/${data.total} contacts completed`, 'processing');
                        setTimeout(checkProgress, 2000);
                    } else if (data.status === 'complete') {
                        showStatus('Processing complete!', 'complete');
                        loadResults();
                    } else if (data.status === 'error') {
                        showStatus('Error: ' + data.error, 'error');
                    }
                } catch (error) {
                    showStatus('Status check failed: ' + error.message, 'error');
                }
            }

            async function loadResults() {
                if (!currentJobId) return;

                try {
                    const response = await fetch(`/results/${currentJobId}`);
                    const data = await response.json();

                    let html = '<h2>Results</h2>';
                    html += '<button onclick="exportResults()">Export CSV</button>';
                    html += '<table><tr><th>Name</th><th>Email</th><th>Last Contact</th><th>Summary</th><th>Services Used</th></tr>';

                    data.results.forEach(result => {
                        html += `<tr>
                            <td>${result.name}</td>
                            <td>${result.email}</td>
                            <td>${result.last_contact || 'No contact found'}</td>
                            <td>${result.summary || 'No summary available'}</td>
                            <td>${result.services || 'None identified'}</td>
                        </tr>`;
                    });

                    html += '</table>';
                    document.getElementById('results').innerHTML = html;
                    document.getElementById('results').style.display = 'block';
                } catch (error) {
                    showStatus('Failed to load results: ' + error.message, 'error');
                }
            }

            async function exportResults() {
                if (!currentJobId) return;

                const link = document.createElement('a');
                link.href = `/export/${currentJobId}`;
                link.download = 'contact_summaries.csv';
                link.click();
            }
        </script>
    </body>
    </html>
    """


@app.post("/upload")
async def upload_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    # generate job ID
    job_id = str(uuid.uuid4())

    # save uploaded file
    file_path = f"uploads/{job_id}.csv"
    os.makedirs("uploads", exist_ok=True)

    try:
        # read and validate CSV
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # parse CSV to validate structure
        df = pd.read_csv(file_path)
        required_columns = ['name', 'email']

        # check for required columns (case insensitive)
        df.columns = df.columns.str.lower().str.strip()
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise HTTPException(
                status_code=400,
                detail=f"CSV must contain columns: {', '.join(required_columns)}. Missing: {', '.join(missing_columns)}"
            )

        # initialize job
        jobs[job_id] = {
            "status": "processing",
            "progress": 0,
            "total": len(df),
            "started_at": datetime.now().isoformat()
        }

        # start background processing
        background_tasks.add_task(process_contacts, job_id, file_path)

        return {"job_id": job_id, "message": "Processing started", "total_contacts": len(df)}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs[job_id]


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    if job_id not in results:
        raise HTTPException(status_code=404, detail="Results not found")

    return {"results": results[job_id]}


@app.get("/export/{job_id}")
async def export_results(job_id: str):
    if job_id not in results:
        raise HTTPException(status_code=404, detail="Results not found")

    # convert results to DataFrame and return as CSV
    df = pd.DataFrame(results[job_id])
    csv_content = df.to_csv(index=False)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contact_summaries_{job_id}.csv"}
    )


async def process_contacts(job_id: str, file_path: str):
    """ bakground task to process contacts"""
    try:
        df = pd.read_csv(file_path)
        df.columns = df.columns.str.lower().str.strip()

        contact_results = []

        for index, row in df.iterrows():
            try:
                # For now, just create dummy results
                # We'll replace this with real Gmail + AI processing
                result = {
                    "name": row['name'],
                    "email": row['email'],
                    "last_contact": "2024-01-15",
                    "summary": "Placeholder summary - Gmail integration coming next",
                    "services": "Placeholder services"
                }

                contact_results.append(result)

                # update progress
                jobs[job_id]["progress"] = index + 1

            except Exception as e:
                # dad error result for this contact
                contact_results.append({
                    "name": row.get('name', 'Unknown'),
                    "email": row.get('email', 'Unknown'),
                    "last_contact": None,
                    "summary": f"Error: {str(e)}",
                    "services": None
                })

        # store results and mark complete
        results[job_id] = contact_results
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)