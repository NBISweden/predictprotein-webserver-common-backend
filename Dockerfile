# Stage 1: create key 
FROM alpine:latest as builder

# Generate the secret key and write it to a file
RUN apk --no-cache add openssl
RUN openssl rand -base64 40 > /tmp/django_pro_secret_key.txt

# Stage 2: build image for the server 
FROM python:3.9

COPY --from=builder /tmp/django_pro_secret_key.txt /etc/django_pro_secret_key.txt

# Set environment variables
ENV DJANGO_SECRET_KEY_FILE=/etc/django_pro_secret_key.txt

# Set the working directory in the container
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/
COPY ./proj/dev_settings.py /app/proj/settings.py

# Expose the port that the Django app will run on
EXPOSE 8000

# Run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

