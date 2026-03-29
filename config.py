import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MySQL Configuration
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = os.getenv('MYSQL_PORT', '3306')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB')

# Flask Configuration
FLASK_ENV = os.getenv('FLASK_ENV', 'production')
SECRET_KEY = os.getenv('FLASK_SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Validation - Ensure critical environment variables are set
def validate_config():
    """Validate that all required environment variables are set."""
    required_vars = ['MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DB', 'FLASK_SECRET_KEY']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_vars)}. "
            "Please create a .env file with proper configuration."
        )

# Call validation on import
validate_config()