# syntax=docker/dockerfile:1
# CPU image; runs on Hugging Face Spaces (Docker SDK), Render, Fly, or any VM.
FROM python:3.11-slim

# Spaces runs the container as uid 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user HF_HOME=/home/user/.cache/huggingface PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER user
COPY --chown=user app ./app
COPY --chown=user static ./static

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
