FROM python:3.12-slim

WORKDIR /app

RUN adduser --disabled-password --no-create-home botuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY weather.py chat.py main.py ./

USER botuser

CMD ["python", "main.py"]
