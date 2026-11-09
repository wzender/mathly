# syntax=docker/dockerfile:1
# mathly2. mathly1 is Dockerfile.mathly1 (and the tag mathly1-final).
# CPU image; runs on Hugging Face Spaces (Docker SDK), Render, Fly, or any VM.
FROM python:3.11-slim

# Spaces runs the container as uid 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY mathly2/requirements.txt mathly2/requirements.txt
RUN pip install --no-cache-dir -r mathly2/requirements.txt

USER user
COPY --chown=user mathly2 ./mathly2

EXPOSE 7860
CMD ["sh", "-c", "uvicorn mathly2.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
