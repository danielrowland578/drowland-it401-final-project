# IT401 Project Template

A Flask project template with a clean separation of concerns: routes, services, and models
are kept in their own files/directories so the codebase stays organized as it grows.

## Project Structure

```
project/
├── app.py                 # App factory, entry point
├── config.py               # Environment-based configuration
├── routes/                  # View functions
├── requirements.txt
├── services/                # Business logic and external integrations
│   ├── api_service.py       # Generic outbound HTTP client
│   ├── search_service.py    # Search logic
│   └── ai_service.py        # AI/LLM integration
├── models/                  # Data models
├── templates/                # Jinja2 HTML templates
├── static/                   # CSS, JS, images
├── data/                      # Local data files
└── tests/                      # Test suite
```

## Prerequisites

- Python 3.10+
- Git

## Setup

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd project
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv

   # macOS / Linux
   source .venv/bin/activate

   # Windows (Command Prompt / PowerShell)
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the App

With the virtual environment activated:

```bash
python app.py
```

The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000).

By default it runs in development mode. Set `FLASK_ENV=production` to use the production config.

## Configuration

Configuration lives in `config.py` and reads from environment variables:

| Variable            | Description                          |
|---------------------|---------------------------------------|
| `SECRET_KEY`         | Flask secret key                      |
| `API_KEY`             | Key for external API service          |
| `AI_SERVICE_API_KEY`   | Key for AI service integration        |
| `FLASK_ENV`             | `development` or `production`         |

## Testing

With the virtual environment activated:

```bash
python -m pytest tests/
```
READEME Documentation:
ThreatPulse
Daniel Rowland
IT401 - Web Intelligence Assignment A1

The Purpose of this Application is to server the Cyber Security Analysts by simplifying the threats they need to assess in one app. This addresses the problem of too much information when doing a cyber security job and simplyfying everything into one app.

I plan to make this a full app that pulls data in a simulated enviroment and simplifies that data. I hope to be able to pull simulated data and make it easier to read the information, as well as the assets page. Currently, we have a main page that shows the information, a intellegence page, where you can view JSON pulled data, and an about page, about ThreatPulse

This will eventually manage plenty of assets, information on intelligence from JSON pulled data, and other threat viewing such as critical alerts and active threats

Some major directories and files include: 
Flask entry point and configuration
Routes and services directories
JSON threat data store (intelligence.html)
Shared and page-specific templates
CSS styling (style.css)
Tests and dependencies (app.py, test_app.py)
Current Threat Pulse application purpose

![alt text](image.png)
![alt text](image-1.png)
![alt text](image-2.png)
![alt text](image-3.png)
![alt text](image-4.png)

I plan to include multiple assets and include web pages for critical alerts and active threats, and many more.