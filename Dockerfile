FROM python:3.13
# Instalar Poetry
RUN pip install poetry

# Configurar el entorno de trabajo
WORKDIR /app

# Copiar archivos del proyecto
COPY . .

# Instalar dependencias usando Poetry
RUN poetry install

# Comando para ejecutar la aplicación
CMD ["poetry", "run", "daemon"]
