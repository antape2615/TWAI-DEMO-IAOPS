FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash

# Install Terraform
RUN curl -O https://releases.hashicorp.com/terraform/1.7.4/terraform_1.7.4_linux_amd64.zip && \
    unzip terraform_1.7.4_linux_amd64.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform_1.7.4_linux_amd64.zip

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create logs directory
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
