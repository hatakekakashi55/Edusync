import bcrypt
try:
    password = "password123"
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    print(f"Hashed: {hashed}")
    matches = bcrypt.checkpw(password.encode('utf-8'), hashed)
    print(f"Matches: {matches}")
except Exception as e:
    print(f"Error: {e}")
