# ML Monitor API

ML Model monitoring system built on top of FastAPI for your machine learning models, tracking predictions, performance metrics, and data drift.

## Features

- User authentication and authorization
- ML model registration and management
- Prediction logging and monitoring
- Accurate performance metrics tracking
- Instant data drift detection
- Fast alert system

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in your values
6. Run the application: `uvicorn app.main:app --reload`

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## Testing

Run tests with: `pytest`
