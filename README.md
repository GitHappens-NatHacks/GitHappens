# GitHappens

> _One-line pitch: what we built and who it helps._

<!-- Badges / links: replace or delete -->
**Demo:** _link_ · **Slides:** _link_ · **Video:** _link_ · **Devpost:** _link_

---

## The Problem

_What pain point are we solving? Who has it? Why does it matter? (2–3 sentences)_

## Our Solution

_What does GitHappens do, and how does it solve the problem? (2–3 sentences)_

### Key Features

- **Feature 1**: _short description_
- **Feature 2**: _short description_
- **Feature 3**: _short description_

<!-- Add a screenshot or GIF: ![screenshot](docs/screenshot.png) -->

## Tech Stack

| Layer    | Tools                  |
| -------- | ---------------------- |
| Frontend | React                  |
| Backend  | Python (_framework_)   |
| Database | _TBD_                  |
| APIs/AI  | _TBD_                  |
| Hosting  | _TBD_                  |

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.10+

### 1. Clone

```bash
git clone <repo-url>
cd GitHappens
```

### 2. Environment variables

```bash
cp .env.example .env
# then fill in the values in .env (never commit this file)
```

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
# run command, e.g. python app.py
```

### 4. Frontend

```bash
cd frontend
npm install
npm start                       # or: npm run dev
```

## Project Structure

```
GitHappens/
├── frontend/      # React app
├── backend/       # Python API
├── docs/          # screenshots, diagrams, pitch assets
├── .env.example   # template for environment variables
└── README.md
```

## Team Workflow

- `main` is always demo-ready. Don't push broken code to it.
- Create a branch per feature: `git checkout -b feature/<name>`
- Pull often (`git pull origin main`) to avoid big merge conflicts.
- Open a PR and get one teammate to review before merging.
- Never commit secrets. Put keys in `.env` and add the variable name to `.env.example`.

## Team

| Name         | Role   |
| ------------ | ------ |
| Adnan        | _role_ |
| Avneet Kaur  | _role_ | 
| Dipta        | _role_ | 
| Elizabeth    | _role_ | 
| Pragati Puri | _role_ |
| Yee          | _role_ | 

## What's Next

- _What we'd build with more time_
- _Known limitations_

## Acknowledgments

_Hackathon name, sponsors, mentors, libraries, or APIs we used._
