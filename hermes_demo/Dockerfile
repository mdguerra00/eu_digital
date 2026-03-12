FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
RUN pip install flask

# Copiar app e templates
COPY app.py .
COPY templates/ templates/

# Copiar skills do hermes_deploy (lidas em runtime)
COPY skills/ skills/

EXPOSE 8080

ENV FLASK_ENV=production
ENV PORT=8080

CMD ["python", "app.py"]
