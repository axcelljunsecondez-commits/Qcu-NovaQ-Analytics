FROM python:3.11-slim

WORKDIR /app

# Cache dependencies separately from source code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY legacy_streamlit/ legacy_streamlit/
COPY frontend/public/locales/ frontend/public/locales/

EXPOSE 8501

CMD ["streamlit", "run", "legacy_streamlit/streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
