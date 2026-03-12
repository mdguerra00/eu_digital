FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
RUN pip install flask

# Copiar app e templates (paths relativos a raiz do repo)
COPY hermes_demo/app.py .
COPY hermes_demo/templates/ templates/

# Copiar skills
COPY hermes_demo/skills/ skills/

EXPOSE 8080

ENV FLASK_ENV=production
ENV PORT=8080

CMD ["python", "app.py"]
