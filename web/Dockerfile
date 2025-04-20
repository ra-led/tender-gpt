# 1. Base Python image
FROM python:3.9-slim

# 2. Ensure we can install packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# 3. Set working dir
WORKDIR /app

# 4. Copy & install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy our Flask app
COPY . .

# 6. Expose the port Flask will run on
EXPOSE 3333

# 7. Tell Flask how to run
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 8. Run the app on 0.0.0.0 so nginx can reach it
CMD ["flask", "run", "--host=0.0.0.0", "--port=3333"]