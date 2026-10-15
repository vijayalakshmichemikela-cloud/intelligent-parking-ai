"""
Admin initialization script for Smart Parking Management System.
Allows creating or updating admin user accounts securely with hashed passwords.
"""

import sys
import getpass
from werkzeug.security import generate_password_hash
from database import query_db

def create_admin(username, email, password, full_name="Administrator", role="admin"):
    """Create or update an admin user in the database."""
    if not username or not password or not email:
        print("Error: Username, email, and password are required.")
        return False
        
    password_hash = generate_password_hash(password)
    
    # Check if admin already exists
    existing = query_db("SELECT id, username FROM admins WHERE username = %s OR email = %s", (username, email), fetch_one=True)
    
    if existing:
        print(f"Updating existing admin account '{username}'...")
        query_db(
            "UPDATE admins SET password_hash = %s, full_name = %s, role = %s, email = %s WHERE id = %s",
            (password_hash, full_name, role, email, existing['id']),
            commit=True
        )
        print(f"Admin '{username}' updated successfully.")
    else:
        print(f"Creating new admin account '{username}'...")
        query_db(
            "INSERT INTO admins (username, email, password_hash, full_name, role) VALUES (%s, %s, %s, %s, %s)",
            (username, email, password_hash, full_name, role),
            commit=True
        )
        print(f"Admin '{username}' created successfully.")
    return True

if __name__ == '__main__':
    print("=" * 60)
    print("Smart Parking Management System - Admin Setup")
    print("=" * 60)
    
    if len(sys.argv) >= 4:
        username = sys.argv[1]
        email = sys.argv[2]
        password = sys.argv[3]
        full_name = sys.argv[4] if len(sys.argv) > 4 else "System Admin"
    else:
        username = input("Enter admin username [default: admin]: ").strip() or "admin"
        email = input("Enter admin email [default: admin@smartparking.local]: ").strip() or "admin@smartparking.local"
        full_name = input("Enter full name [default: System Administrator]: ").strip() or "System Administrator"
        password = getpass.getpass("Enter password [leave empty to keep/use Admin@12345]: ").strip() or "Admin@12345"
        
    create_admin(username, email, password, full_name)
