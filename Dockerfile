FROM python:3.13

# Instalar Poetry
RUN pip install poetry

# Configurar el entorno de trabajo
WORKDIR /app

# Copiar archivos del proyecto
COPY . .

# Instalar dependencias usando Poetry, incluyendo Gunicorn
RUN poetry add gunicorn && poetry install

# Comando para ejecutar la aplicación con Gunicorn
CMD ["poetry", "run", "gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "tomi_metrics.app:app"]
