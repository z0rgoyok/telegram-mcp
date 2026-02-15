FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -e .
CMD ["python", "-m", "telegram_mcp"]
