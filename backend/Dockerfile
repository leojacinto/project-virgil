FROM python:3.9-slim

# Install Java and build tools (required for ServiceNow JDBC and Python packages)
RUN apt-get update && \
    apt-get install -y openjdk-21-jre-headless wget curl build-essential g++ && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME (auto-detect architecture)
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-arm64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for JDBC driver
RUN mkdir -p /app/jdbc

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
