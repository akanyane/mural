import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Hashes "$2b$" gerados pelo passlib continuam válidos aqui.
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except ValueError:
        # Senha com mais de 72 bytes ou hash malformado.
        return False
