FROM python:3.11-slim

WORKDIR /workspace

# Copy requirements from mcp_server directory relative to root build context
COPY mcp_server/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire repository so app, services, and evals are accessible
COPY . .

ENV PYTHONPATH=/workspace/app:/workspace

EXPOSE 8001
CMD ["uvicorn", "mcp_server.server:app", "--host", "0.0.0.0", "--port", "8001"]
