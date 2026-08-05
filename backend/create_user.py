# create_user.py
from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.core.security import hash_password

Base.metadata.create_all(bind=engine)

email = input("E-mail du compte : ").strip()
nom = input("Nom complet : ").strip()
password = input("Mot de passe : ").strip()
profil = input("Profil (admin / user) [admin] : ").strip() or "admin"

if profil not in ("admin", "user"):
    raise SystemExit("Profil invalide : utilisez admin ou user.")

db = SessionLocal()
existing = db.query(User).filter(User.email == email).first()
if existing:
    print("Un compte avec cet e-mail existe déjà.")
else:
    user = User(email=email, nom=nom, password_hash=hash_password(password), profil=profil)
    db.add(user)
    db.commit()
    print(f"Compte créé pour {email}.")
db.close()
