FROM python:3.9-slim


RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*


ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY . .


RUN mkdir -p /app/static /app/media /app/api/uploaded_logs


EXPOSE 8000


CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]