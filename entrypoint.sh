#!/bin/sh
# this script is the entrypoint for the Docker container
# it starts the application using the Gunicorn configuration file

echo "Starting Gunicorn server with config file..."
exec gunicorn -c gunicorn_config.py app.main:app