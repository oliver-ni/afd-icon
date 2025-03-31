FROM python:3.8

WORKDIR /app
RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev

COPY . .
CMD ["uvicorn", "main:app", "--host", "::", "--port", "8000"]
