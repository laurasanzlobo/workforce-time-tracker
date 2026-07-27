"""
File: run.py

Main entry point for running the web application.
Imports the application factory and starts the development server.

Author: Laura Sanz Lobo
"""

from app import create_app

# Initialize the application using the default configuration (DevelopmentConfig)
app = create_app()

if __name__ == '__main__':
    # Run the Flask development server
    app.run(host="0.0.0.0", port=5500, debug=True)