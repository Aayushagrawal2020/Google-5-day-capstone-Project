# MockMentor - Agentic AI Interview Coach

MockMentor is an agentic AI Interview Coach that helps candidates prepare for technical and behavioral interviews. It parses your target Job Description (JD) and Resume, uses the Model Context Protocol (MCP) and an SQLite database to store your weakness profile, and adaptively targets those weaknesses in subsequent mock interview sessions.

---

## Prerequisites
Ensure you have **Docker** and **Docker Desktop** installed on your system.

---

## How to Run Locally (Method A - Docker Compose)

Follow these simple steps to run the application locally on your machine for free:

### Step 1: Configure your API Key
1. Copy the `.env.example` template to create a `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Open the `.env` file and replace `your_gemini_api_key_here` with your actual Gemini API Key from Google AI Studio (obtain a free key from [Google AI Studio](https://aistudio.google.com/)).
   ```env
   GEMINI_API_KEY=AIzaSyYourActualApiKeyHere
   MOCK_MODE=False
   ```

### Step 2: Build and Start the Application
Start the containers in detached mode:
```bash
docker compose up --build -d
```

### Step 3: Access MockMentor in Your Browser
Open your web browser and navigate to:
```
http://localhost:8000
```

---

## How it Works Under the Hood

1. **Agent Workflow (ADK 2.0)**: The coach is built using the Google Agent Development Kit (ADK) state graph, running steps dynamically:
   - **Profile Ingestion**: Matches your Resume against the target JD, identifying skill gaps.
   - **Adaptive Questioning**: Targets identified weaknesses first, adjusting question topics based on past performance.
   - **STAR Evaluation**: Grades behavioral responses strictly against the STAR (Situation, Task, Action, Result) methodology.
2. **Model Fallback**: Uses a `FallbackGemini` model layer. If the preferred `gemini-3.5-flash` model runs into API errors or quota limits, the agent automatically falls back to `gemini-2.5-flash` or `gemini-1.5-flash`.
3. **Local Database Persistence**: Exposes database operations as Stdio-based Model Context Protocol (MCP) tools. Session records, scores, and weakness stats are persisted locally inside the container volume mapping to `data/mockmentor.db`.

---

## Stopping the Application
To stop the local server and free up ports:
```bash
docker compose down
```
All your database history and progress will remain saved in the local `data/` folder for your next run!
