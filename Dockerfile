# Stage 1: Build environment with pip
FROM cgr.dev/chainguard/python:latest-dev AS build

WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt .

# Install dependencies to a specific location
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Minimal runtime environment
FROM cgr.dev/chainguard/python:latest AS runtime

WORKDIR /app

# Copy Python packages from build stage
# The --user flag installs to ~/.local, so we copy that
COPY --from=build /home/nonroot/.local /home/nonroot/.local

# Copy application code
COPY . .

# Make sure Python can find the installed packages
ENV PATH=/home/nonroot/.local/bin:$PATH
ENV PYTHONPATH=/home/nonroot/.local/lib/python3.12/site-packages:$PYTHONPATH

# Run the bot
CMD ["python", "/app/bot.py"]