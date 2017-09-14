# Trials w/ py3.4
# FROM python:3
FROM python:2.7-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "python", "./app.py" ]
