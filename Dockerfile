# syntax=docker/dockerfile:1

FROM cgr.dev/chainguard/python:latest-dev as dev

WORKDIR /app

# Create virtual environment
RUN python -m venv venv
ENV PATH="/app/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Stage 2: Minimal runtime
FROM cgr.dev/chainguard/python:latest

WORKDIR /app

# Copy ALL Python application files
COPY *.py ./
COPY .env .env

# Copy virtual environment from dev stage
COPY --from=dev /app/venv /app/venv

# Set PATH to use venv
ENV PATH="/app/venv/bin:$PATH"

# Set timezone to Israel
ENV TZ=Asia/Jerusalem

# Run the bot
ENTRYPOINT ["python", "bot.py"]