"""
Configuration for Smart Parking Management System.
Reads settings from the .env file via python-dotenv.
This file is intentionally kept separate from app.py so that
database.py can import Config without creating a circular import.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY   = os.getenv('SECRET_KEY', 'default-dev-secret-key-change-in-prod')
    DEBUG        = os.getenv('FLASK_DEBUG', '1') == '1'
    PORT         = int(os.getenv('PORT', 5000))

    # Database
    DB_ENGINE    = os.getenv('DB_ENGINE', 'mysql').lower()
    DB_HOST      = os.getenv('DB_HOST', 'localhost')
    DB_PORT      = int(os.getenv('DB_PORT', 3306))
    DB_USER      = os.getenv('DB_USER', 'root')
    DB_PASSWORD  = os.getenv('DB_PASSWORD', '')
    DB_NAME      = os.getenv('DB_NAME', 'smart_parking_db')

    # SQLite fallback path (used automatically when MySQL is unavailable)
    SQLITE_PATH = "/tmp/smart_parking.db"
    APP_TIMEZONE = os.getenv('APP_TIMEZONE', 'UTC')
