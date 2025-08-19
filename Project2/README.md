
# Online Quiz Maker - Simple Flask App

## Quick setup (Linux / macOS / Windows with Python 3.8+)

1. Create a virtual environment:
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate    # Windows PowerShell

2. Install requirements:
   pip install -r requirements.txt

3. Run the app:
   python app.py

4. Open http://127.0.0.1:5000/ in your browser.

Notes:
- Default secret_key in app.py should be changed for production.
- Database (data.db) will be created automatically on first run.
