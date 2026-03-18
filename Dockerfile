FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml README.md /app/
RUN uv pip install --system -e .

COPY . .

CMD ["python", "-m", "bot.main"]
