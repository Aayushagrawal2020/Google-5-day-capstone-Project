# MockMentor: Agentic AI Interview Coach

MockMentor is an agentic AI Interview Coach that evaluates mock interviews based on a Job Description (JD) and Resume of any field, stores the candidate's performance/weakness metrics locally using SQLite (via an MCP Server), and adaptively updates future interviews to drill down on past weak spots.

This directory represents the **Developer 3** deliverables, including the FastAPI application server, single-page application frontend dashboard, and Docker configurations.

## Architecture

* **Frontend**: Responsive Single Page App (SPA) styled with custom Glassmorphism and CSS variables for dark-mode aesthetic styling. Uses **Chart.js** for interactive capability evaluation radar charts.
* **Backend**: FastAPI server hosting REST APIs for session startup, PDF resume upload parsing (via `pypdf`), conversational loops, and historical analytics querying.

## Project Structure

```
MockMentor/
├── Dockerfile                  # Application container builder
├── docker-compose.yml          # Local container orchestration and SQLite volume mapping
├── pyproject.toml              # Project dependencies configuration
├── README.md                   # Setup and usage guidelines
└── frontend/
    ├── main.py                 # FastAPI endpoints & mock interview controllers
    └── static/
        ├── index.html          # SPA structure (Setup, Chat, Dashboard)
        ├── style.css           # Glassmorphism aesthetics stylesheet
        └── app.js              # State logic, API integrations, and Chart graphics
```

## Running the Application

### Option 1: Docker Compose (Recommended)

To run the application in a containerized environment:

1. Build and run:
   ```bash
   docker-compose up --build
   ```
2. Open your browser and navigate to `http://localhost:8000`.

### Option 2: Local Python Run

To run locally without Docker:

1. Install dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
2. Run the server:
   ```bash
   uvicorn frontend.main:app --reload
   ```
3. Open your browser and navigate to `http://localhost:8000`.
