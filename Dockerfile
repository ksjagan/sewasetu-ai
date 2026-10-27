FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install PostgreSQL, Python, pip, sudo, and utilities
RUN apt-get update && apt-get install -y \
    postgresql postgresql-contrib \
    python3 python3-pip python3-dev \
    curl sudo git \
    && rm -rf /var/lib/apt/lists/*

# Setup user 1000 for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user && \
    echo "user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

WORKDIR /app

# Copy project files
COPY . /app

# Install Python requirements
RUN pip3 install --no-cache-dir \
    flask \
    psycopg2-binary \
    requests \
    starlette>=0.30.0 \
    uvicorn>=0.22.0 \
    pydantic>=2.0.0 \
    pyjwt>=2.8.0 \
    cryptography>=41.0.0 \
    fpdf2>=2.7.0

# Set directories and permissions
RUN mkdir -p /var/sewasetu/uploads /var/log/sewasetu /var/run/postgresql && \
    chown -R user:user /app /var/sewasetu /var/log/sewasetu /var/run/postgresql && \
    chmod +x /app/start.sh

USER user
EXPOSE 7860

CMD ["/bin/bash", "/app/start.sh"]
