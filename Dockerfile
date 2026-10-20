FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY services ./services
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home appuser
USER 10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "services.app:from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
