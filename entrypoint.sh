#!/bin/sh

# This script is the entrypoint for the Docker container.
# It starts the application using Gunicorn, a production-ready process manager,
# which in turn manages Uvicorn workers for asynchronous performance.

# -w 3: Spawns 3 worker processes. A common rule of thumb is (2 * number of CPU cores) + 1.
# -k uvicorn.workers.UvicornWorker: Specifies that Uvicorn should be used to run the workers, which is necessary for ASGI applications like FastAPI.
# main:app: Tells Gunicorn where to find the FastAPI app instance (the 'app' object in the 'main.py' file). This is the part we updated for the new structure.
# --bind 0.0.0.0:5000: Binds to all network interfaces on port 5000 inside the container, making it accessible for port mapping.

# This script now starts Gunicorn using the configuration file,
# which contains all our settings and the post_fork hook.

echo "Starting Gunicorn server with config file..."
exec gunicorn -c gunicorn_config.py main:app