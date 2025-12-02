# syntax=docker/dockerfile:1

FROM cgr.dev/chainguard/python:latest-dev as dev

# Use nonroot's home directory instead of /app
WORKDIR /home/nonroot/app

# Create virtual environment
RUN python -m venv venv
ENV PATH="/home/nonroot/app/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Stage 2: Minimal runtime
FROM cgr.dev/chainguard/python:latest

WORKDIR /home/nonroot/app

# Copy application files
COPY bot.py bot.py
COPY data.py data.py

# Copy virtual environment from dev stage
COPY --from=dev /home/nonroot/app/venv /home/nonroot/app/venv

# Set PATH to use venv
ENV PATH="/home/nonroot/app/venv/bin:$PATH"

# Set timezone to Israel
ENV TZ=Asia/Jerusalem

# Run the bot
ENTRYPOINT ["python", "bot.py"]