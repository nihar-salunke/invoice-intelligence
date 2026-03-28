# Invoice Intelligence

An agentic AI system that automates tractor invoice verification for loan processing. Upload an invoice image and a 5-agent pipeline extracts fields, detects language and state, verifies dealer and HP specs via web search, validates business rules, and produces an authenticity score -- all with a full audit trail.

## Architecture

Five agents run in sequence per invoice:

| # | Agent | Type | What it does |
|---|-------|------|-------------|
| 1 | **Intake** | Python + OpenCV | Validates image, strips EXIF, denoises, enhances contrast, resizes (e.g. 5.8MB PNG to 0.3MB JPEG) |
| 2 | **Extraction** | Gemini 2.5 Flash | Extracts dealer name, model, HP, cost, signature/stamp bboxes, language, state, document type |
| 3 | **Research** | Gemini + Google Search | Verifies tractor HP from manufacturer specs and dealer legitimacy via web search |
| 4 | **Validation** | Python | Cross-checks HP match, field completeness, cost range, signature/stamp presence |
| 5 | **Scoring** | Python | Computes 0-100 authenticity score with breakdown, sets PASS/REVIEW/FAIL status, generates summary |

See [docs/architecture.md](docs/architecture.md) for the full architecture document.

## Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **Google Cloud project** with Vertex AI API enabled and a service account key

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/nihar-salunke/invoice-intelligence.git
cd invoice-intelligence
```

### 2. Google Cloud / Vertex AI Setup

You need a GCP project with Vertex AI enabled and a service account. For a video walkthrough of this setup, see: https://www.youtube.com/watch?v=I8W-4oq1onY

**a) Enable the Vertex AI API:**

Go to [Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com) in your GCP project and click **Enable**.

**b) Create a service account:**

Go to [IAM > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts), create a new service account, and grant it the **Vertex AI User** role.

**c) Download the JSON key:**

From the service account page, go to **Keys > Add Key > Create new key > JSON**. Save the downloaded file as `credentials.json` in the project root.

**d) Ensure billing is enabled:**

Vertex AI requires an active billing account on the project. Check at [Billing](https://console.cloud.google.com/billing).

### 3. Backend Setup

```bash
cd backend
python3 -m venv ../venv
source ../venv/bin/activate
pip install -r requirements.txt
```

The backend dependencies are:

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework for the API |
| `uvicorn[standard]` | ASGI server |
| `python-multipart` | File upload handling |
| `google-genai` | Google Gen AI SDK (Gemini on Vertex AI) |
| `google-auth` | Service account authentication |
| `opencv-python-headless` | Image preprocessing (denoise, enhance, resize) |
| `Pillow` | Image format handling and EXIF stripping |

Install all at once:

```bash
pip install fastapi uvicorn[standard] python-multipart google-genai google-auth opencv-python-headless Pillow
```

### 4. Frontend Setup

```bash
cd frontend
npm install
```

### 5. Run

Open two terminals:

**Terminal 1 -- Backend (port 8000):**

```bash
source venv/bin/activate
cd backend
uvicorn app:app --reload --port 8000
```

**Terminal 2 -- Frontend (port 5173):**

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

### 6. Usage

1. Upload a tractor invoice image (PNG, JPG -- even large phone photos are auto-preprocessed)
2. Wait ~15-30 seconds for the 5-agent pipeline to complete
3. View the verification report: extracted fields, web verification, authenticity score, and agent trail

## Project Structure

```
idfc-hack-submission/
  backend/
    app.py              # FastAPI endpoints
    agents.py           # 5 agent classes (Intake, Extraction, Research, Validation, Scoring)
    orchestrator.py     # Pipeline runner with audit trail
    requirements.txt    # Python dependencies
  frontend/
    src/
      App.jsx           # Main layout
      components/
        ImageUpload.jsx   # Drag-and-drop upload
        ImagePreview.jsx  # Original vs preprocessed comparison
        ResultCard.jsx    # Score gauge, fields, research, breakdown
        AgentTrail.jsx    # Agent pipeline timeline
        History.jsx       # Past results sidebar
  docs/
    architecture.md     # Architecture document
    impact-model.md     # Business impact analysis
  credentials.json      # (not committed) Your GCP service account key
```

## Submission Artifacts

| Artifact | Location |
|----------|----------|
| Source code | This repository |
| Architecture document | [docs/architecture.md](docs/architecture.md) |
| Impact model | [docs/impact-model.md](docs/impact-model.md) |
