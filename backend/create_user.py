# create_user.py
from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)

email = input("E-mail du compte : ").strip()
full_name = input("Nom complet : ").strip()
password = input("Mot de passe : ").strip()

db = SessionLocal()
existing = db.query(User).filter(User.email == email).first()
if existing:
    print("Un compte avec cet e-mail existe déjà.")
else:
    user = User(email=email, full_name=full_name, hashed_password=hash_password(password))
    db.add(user)
    db.commit()
    print(f"Compte créé pour {email}.")
db.close()