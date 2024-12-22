FROM python:3.9-slim

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 80

ENV NAME World

CMD ["python", "bot.py"]