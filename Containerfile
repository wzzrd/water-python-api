# Containerfile for Red Hat UBI
FROM registry.redhat.io/ubi10/ubi:latest

# Set metadata labels (good practice for Red Hat containers)
LABEL name="water-meter-daemon" \
      version="1.0" \
      description="Water meter data collection daemon for TimescaleDB" \
      maintainer="your-email@example.com" \
      vendor="Your Organization"

# Install Python libraries
RUN dnf update -y && \
    dnf install -y \
        python3-psycopg2 \
        python3-requests \
        && dnf clean all

# Set working directory
WORKDIR /app

# Copy application code
COPY water-python-api.py .

# Create non-root user (following Red Hat security best practices)
RUN useradd -r -s /sbin/nologin -u 1001 watermeter && \
    chown -R watermeter:watermeter /app

# Switch to non-root user
USER 1001

# Expose any ports if needed (none required for this daemon)
# EXPOSE 8080

# Set environment variables defaults
ENV COLLECTION_INTERVAL=300 \
    METER_API_TIMEOUT=10 \
    DB_PORT=5432

# Health check (optional but recommended)
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import requests; requests.get('${METER_API_URL}', timeout=5)" || exit 1

# Run the daemon
CMD ["python3", "water-python-api.py"]
