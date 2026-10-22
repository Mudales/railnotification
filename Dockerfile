# syntax=docker/dockerfile:1

FROM cgr.dev/chainguard/python:latest-dev as dev

WORKDIR /home/nonroot

# Install packages directly (no venv needed)
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# The runtime stage has no shell, so the writable data directory is made here
# and copied across. The named volume mounted over it inherits this ownership.
RUN mkdir -p /home/nonroot/appdata && touch /home/nonroot/appdata/.keep

# Stage 2: Runtime
FROM cgr.dev/chainguard/python:latest

WORKDIR /home/nonroot/app

# Copy installed packages from nonroot's .local
COPY --from=dev /home/nonroot/.local /home/nonroot/.local

# Copy application files
COPY *.py ./
COPY .env .env

# Favourites live here, on a volume, so a rebuild does not wipe them.
COPY --from=dev --chown=65532:65532 /home/nonroot/appdata ./data

# Set PATH to include user packages
ENV PATH="/home/nonroot/.local/bin:$PATH"
ENV PYTHONPATH="/home/nonroot/.local/lib/python3.12/site-packages:$PYTHONPATH"
ENV TZ=Asia/Jerusalem

# Run the bot
ENTRYPOINT ["python", "bot.py"]