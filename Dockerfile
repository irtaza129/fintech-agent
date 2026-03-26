FROM python:3.14

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app

EXPOSE 8000

# Run the app as a package module so relative imports in `backend` work
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
