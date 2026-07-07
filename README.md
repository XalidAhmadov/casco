Current Status
Component	Status	Notes
Frame extraction from video	✅ Working	OpenCV, configurable interval
NVIDIA VLM inference	✅ Working	Llama 3.2 11B Vision via API
Hard hat violation detection	✅ Working	violation / compliant / uncertain
Temporal incident confirmation	✅ Working	configurable consecutive-frame threshold
Evidence capture (frames + JSON)	✅ Working	saved to outputs/
Live stream input	🔧 In progress	RTSP / webcam
Notifications	🔧 In progress	Telegram bot
LLM interpretation layer	🔧 In progress	Gemma 4 via Ollama
General PPE classes	📋 Planned	vests, gloves, goggles
Multi-person tracking	📋 Planned	stable person IDs
Backend API	📋 Planned	incident endpoints
Monitoring dashboard	📋 Planned	supervisor UI
Quick Start
# 1. Clone the repository
git clone https://github.com/area42-ai/AREA-42-Final-project.git
cd AREA-42-Final-project

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Open .env and add your NVIDIA_API_KEY

# 5. Run the pipeline on a video file
python scripts/video_frame_pipeline.py --video path/to/your/video.mp4
Output is saved to outputs/<video_name>/:

outputs/your_video/
├── frames/          # sampled JPEG frames
├── evidence/        # incident start and end frames
├── frame_results.json
├── raw_responses.json
└── incident.json
Pipeline A — Quick Start
Pipeline A analyzes a whole video with Nemotron (plain-text temporal summary) and then converts that text into a normalized incident JSON with Gemma. One command runs both stages end-to-end.

Never run this before? Do these three things first:

Activate the project virtual environment (it already has OpenCV, the OpenAI SDK, and the Google GenAI SDK installed):

.\.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate         # macOS/Linux
Create your .env from the template and add your API keys:

copy .env.example .env              # Windows  (cp .env.example .env on macOS/Linux)
Then open .env and set at least these two values:

NVIDIA_API_KEY=your_nvidia_api_key_here     # used by Stage 1 (Nemotron)
GOOGLE_API_KEY=your_google_api_key_here     # used by Stage 2 (Gemma)
Put your video in data/test/ (e.g. data/test/worker_removes_helmet.mp4).

Run it (one line):

python scripts/run_pipeline_a.py --video-name worker_removes_helmet.mp4 --output-dir outputs/pipeline_a
Optional flags: --ppe-items hard_hat,safety_vest,safety_glasses,gloves (defaults to all four) and --model <gemma-model> (Stage 2 Gemma model; the Stage 1 Nemotron model comes from NVIDIA_NEMOTRON_MODEL).

What you get: on success the command prints exactly one line — the path to the final normalized incident JSON — e.g.:

outputs/pipeline_a/worker_removes_helmet_pipeline_a_incident.json
That file follows the shared incident contract:

{
  "schema_version": "1.0",
  "video_id": "worker_removes_helmet",
  "source_pipeline": "nemotron_gemma",
  "models": ["nemotron", "gemma-4-26b-a4b-it"],
  "analysis_scope": ["hard_hat", "safety_vest", "safety_glasses", "gloves"],
  "incident_detected": true,
  "incidents": [ /* one entry per confirmed missing PPE item */ ],
  "summary": "...",
  "quality": { "parse_success": true, "warnings": [] }
}
Alongside it, the intermediate Nemotron summary is saved as outputs/pipeline_a/nemotron_<video_stem>_summary.json.

If ffmpeg is not on your PATH, videos over 5 MB are sent uncompressed (slower and more costly) — the run still works. Errors (missing key, missing video, wrong environment) print a plain-language message and stop before any API call.

Pipeline Architecture
Video file / live stream
        │
        ▼
 Frame Extraction (OpenCV)
        │
        ▼
 NVIDIA VLM API  ──►  violation / compliant / uncertain
        │
        ▼
 Temporal Incident Logic
        │
        ▼
 Evidence Capture ──► Notifications
The full architecture, API-first design decisions, and component boundaries are documented in docs/ARCHITECTURE.md.

Evaluation Dataset
A manually annotated PPE video evaluation set (10 scenarios) is maintained externally in Google Drive, covering:

Always compliant / always violating
Worker removes and re-wears hard hat mid-video
Two workers with mixed compliance
Occlusion, low light, and difficult angles
Dataset access: data/README.md

Documentation
Document	Purpose
docs/ARCHITECTURE.md	Pipeline design and component boundaries
docs/PROJECT_CONTEXT.md	Product scope, confirmed vs. proposed decisions
docs/DECISIONS.md	Official decision log
docs/MEETING_LOG.md	Meeting summaries
docs/TEAM_WORKFLOW.md	Git workflow and task management
docs/AI_WORKFLOW.md	How AI tools are used in this project
AGENTS.md	Instructions for AI coding agents
Plan.md	Dynamic roadmap and task tracker
Team
AREA-42 · Data & AI Cohort 2026

Elvin Nəsirov
Roya Nasirova
Adil Hasanov
Aysu Mammadova Anar
GitHub Organization · Project Board

License
This project is licensed under the MIT License.
