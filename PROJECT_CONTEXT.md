# Contexte technique du projet UlySearch

## 1. Objet de ce document

Ce document fournit un contexte autonome pour une nouvelle conversation technique,
une revue de code, un diagnostic ou une prise en main du projet.

Il décrit l'état du dépôt au 22 octobre 2026 :

- objectif métier et périmètre fonctionnel ;
- architecture et flux de traitement ;
- stack technique ;
- arborescence backend et frontend ;
- modèle de données ;
- sécurité et isolation multi-tenant ;
- processus de scoring et de collecte ;
- exécution locale et déploiement ;
- tests et limites connues.

Les secrets, mots de passe, valeurs de `.env` et données clients ne doivent pas
être ajoutés à ce document.

---

## 2. Résumé du produit

Sotradies / UlySearch est une plateforme SaaS multi-tenant de veille des appels
d'offres.

La plateforme :

1. collecte des avis depuis des sources dédiées ou des sites configurés ;
2. normalise les données collectées ;
3. déduplique les appels d'offres ;
4. calcule la pertinence de chaque offre pour chaque entreprise ;
5. affecte les offres aux commerciaux ;
6. enrichit certaines offres avec une IA locale ;
7. envoie des alertes, digests et rapports ;
8. permet le suivi commercial : statut, feedback, offres rejetées et exports.

Le principe métier est :

> L'IA aide à configurer et à résoudre les cas ambigus ; les règles déterministes
> exécutent la production quotidienne.

---

## 3. Utilisateurs et isolation

### Profils

- `superadmin` : administration globale de la plateforme, entreprises, utilisateurs,
  sources globales, audit et système ;
- `admin` : administration de sa propre entreprise, configuration, commerciaux,
  sources et acheteurs ;
- `commercial` : consultation et mise à jour des offres qui lui sont affectées ;
- autres profils de consultation selon les règles présentes dans les dépendances API.

### Isolation

Les données client sont généralement filtrées par `company_id`.

Les objets sensibles sont contrôlés par des requêtes cloisonnées :

- `CompanyTender` est filtré par entreprise ;
- un commercial ne voit que ses propres affectations ;
- les acheteurs connus sont filtrés par entreprise ;
- les identifiants de sources sont liés à `CompanySource` ;
- le superadministrateur dispose d'une vue globale explicite.

Le fichier central des offres brutes (`sotradies`) est global ; les résultats
client et le suivi commercial sont portés par `company_tenders`.

---

## 4. Architecture générale

```text
Navigateur React
       |
       | HTTP JSON + cookie JWT httpOnly
       v
FastAPI / Uvicorn
       |
       +--> PostgreSQL
       +--> Redis broker / verrous / rate limiting
       +--> Redis cache
       +--> SMTP
       |
       +--> Celery worker
       |       +--> pipeline de scraping et scoring
       |       +--> notifications
       |       +--> rapports et nettoyage
       |
       +--> Celery Beat
               +--> planification des tâches

Sources externes
       ^
       |
       +-- httpx / Scrapling
       +-- Playwright pour les sites nécessitant un navigateur
       +-- connecteurs dédiés ONMP et TUNEPS

IA locale optionnelle
       ^
       |
       +-- Ollama via le client local
```

Le frontend construit par Vite est copié dans l'image Docker et servi par FastAPI
en production.

---

## 5. Stack technique

### Backend

- Python 3.12 ;
- FastAPI ;
- Uvicorn ;
- Pydantic 2 et `pydantic-settings` ;
- SQLAlchemy 2 ;
- PostgreSQL avec `psycopg` ;
- Alembic ;
- Celery ;
- Redis ;
- SlowAPI pour le rate limiting ;
- httpx ;
- Scrapling ;
- Playwright ;
- BeautifulSoup et lxml ;
- pandas et openpyxl ;
- PyMuPDF, pdf2image, Tesseract et Pillow pour l'OCR ;
- bcrypt pour les mots de passe ;
- PyJWT pour les sessions ;
- cryptography / Fernet pour les identifiants de sources privées ;
- reportlab pour les exports PDF ;
- Ollama optionnel pour l'IA locale.

### Frontend

- React 19 ;
- Vite ;
- React Router ;
- TanStack React Query ;
- Axios ;
- Recharts ;
- Lucide React ;
- Tailwind CSS ;
- ESLint ;
- polices IBM Plex et Space Grotesk auto-hébergées.

### Infrastructure

- Docker multi-stage ;
- image frontend Node 22 ;
- image runtime Playwright Python ;
- PostgreSQL Render ;
- deux services Redis Render :
  - broker Celery sans éviction ;
  - cache applicatif avec éviction LRU ;
- services Render :
  - web ;
  - worker Celery ;
  - scheduler Celery Beat.

---

## 6. Processus technique complet

### 6.1 Inscription

Le parcours d'inscription est public :

1. validation du formulaire et normalisation des chaînes ;
2. création de `Company` ;
3. création du compte administrateur `User` ;
4. création des commerciaux initiaux ;
5. abonnement aux sources publiques sélectionnées ;
6. création des sources manuelles ;
7. création et chiffrement des identifiants privés dans `SourceAccount` ;
8. création de la configuration de l'entreprise ;
9. création de la réponse HTTP ;
10. lancement optionnel d'un pipeline différé si `RUN_PIPELINE_ON_REGISTER` est activé.

Les nouvelles sources manuelles ne doivent pas devenir des sources globales
activées par défaut. L'activation plateforme et l'abonnement de l'entreprise
sont deux notions distinctes.

### 6.2 Collecte

Le pipeline charge les sources actives à travers :

- `ScrapingSource` : définition globale de la source ;
- `CompanySource` : abonnement et activation côté entreprise ;
- `SourceAccount` : identifiants privés chiffrés.

Connecteurs dédiés :

- `OnmpScraper` ;
- `TunepsScraper`.

Scraper générique :

- `UniversalScraper` ;
- mode HTTP simple ;
- mode navigateur Playwright si nécessaire ;
- contrôle SSRF sur les requêtes et les ressources navigateur.

La collecte utilise un cache court pour limiter les appels répétés.

### 6.3 Normalisation et déduplication

Les données brutes sont converties vers le schéma `SotradiesRaw`, puis :

- normalisées ;
- nettoyées ;
- comparées aux offres existantes ;
- dédupliquées globalement ;
- enregistrées dans `sotradies`.

La relation entreprise/offre est enregistrée dans `company_tenders`.

### 6.4 Scoring

Le scoring client est orchestré dans
[scoring_orchestrator.py](backend/app/services/scoring_orchestrator.py).

Ordre de traitement :

1. scoring par règles dynamiques ;
2. ajout de la méthode `regles` dans les détails ;
3. détection des cas ambigus ;
4. exclusion rapide des sujets manifestement hors secteur ;
5. appel IA uniquement si nécessaire ;
6. plafonnement du score issu uniquement de l'IA à 60 ;
7. remplacement ciblé du résultat d'une catégorie si l'IA est suffisamment certaine ;
8. conservation de la méthode (`regles` ou `ia`) dans `score_details` ;
9. mise en cache mémoire de la réponse IA.

Le score IA seul ne doit pas déclencher une alerte instantanée au-dessus du seuil
de confiance métier.

### 6.5 Enrichissement

Selon la configuration, le pipeline peut :

- récupérer le détail d'une annonce ;
- extraire ou nettoyer le texte ;
- utiliser l'IA locale pour structurer certaines données ;
- reconnaître un acheteur connu ;
- ajouter les informations dans les journaux de pipeline.

L'enrichissement détaillé est désactivé dans Render par défaut avec
`UNIVERSAL_ENRICH_DETAIL=false`.

### 6.6 Affectation et notifications

Après scoring :

- les catégories déterminent les règles d'affectation ;
- l'offre est reliée à un commercial ;
- les notifications instantanées, digests et rappels sont générées ;
- `sent_log` assure l'idempotence des notifications ;
- les emails sont rendus par les templates Jinja.

### 6.7 Nettoyage

Les tâches de nettoyage suppriment périodiquement :

- anciens logs de pipeline ;
- dumps bruts périmés ;
- anciens journaux de notification ;
- anciennes données selon les règles de rétention.

---

## 7. Arborescence principale

```text
SotradiesV2/
├── .github/
│   └── workflows/ci.yml
├── .vscode/
│   └── settings.json
├── backend/
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── certs/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── templates/
│   │   └── workers/
│   ├── data/
│   │   └── clients_sotradies_modele.xlsx
│   └── scripts/
├── docs/
│   └── TUNEPS_CONFIGURATION.md
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── public/
│   └── src/
│       ├── api/
│       ├── assets/
│       ├── components/
│       ├── context/
│       ├── hooks/
│       ├── pages/
│       └── utils/
├── Dockerfile
├── render.yaml
└── PROJECT_CONTEXT.md
```

---

## 8. Arborescence backend détaillée

### `backend/app/api/`

- `auth.py` : connexion, session et déconnexion ;
- `registration.py` : inscription et onboarding initial ;
- `tenders.py` : liste, détail, filtres, statut, feedback, exports et rejetées ;
- `buyers.py` : acheteurs connus, import Excel et OCR ;
- `admin_config.py` : configuration client ;
- `config_public.py` : configuration publique ;
- `admin_sources.py` : gestion des sources ;
- `admin_companies.py` : gestion des entreprises ;
- `admin_commercials.py` : gestion des commerciaux ;
- `admin_users.py` : gestion des utilisateurs ;
- `admin_system.py` : état et contrôle des processus locaux ;
- `admin_ai_suggest.py` : suggestions d'onboarding par IA ;
- `audit.py` : consultation et export de l'audit.

### `backend/app/core/`

- `config.py` : variables d'environnement et paramètres ;
- `database.py` : moteur SQLAlchemy, sessions et transaction scope ;
- `security.py` : bcrypt, JWT et sécurité de session ;
- `rate_limiter.py` : limitation de débit ;
- `celery_app.py` : application Celery ;
- `scheduler.py` : planification ;
- `init_config.py` : configuration par défaut ;
- `cache.py` : cache Redis ;
- `keywords.py` : valeurs et catégories initiales ;
- `onboarding_sources.py` : catalogue d'onboarding ;
- `paths.py` : chemins applicatifs ;
- `templates.py` : configuration des templates ;
- `time_utils.py` : utilitaires temporels.

### `backend/app/models/`

- `user.py`
- `company.py`
- `commercial.py`
- `configuration.py`
- `scraping_source.py`
- `company_source.py`
- `source_account.py`
- `sotradies.py`
- `company_tender.py`
- `known_buyer.py`
- `sent_log.py`
- `audit_log.py`
- `pipeline_log.py`
- `system_action_log.py`

### `backend/app/schemas/`

Contient les contrats Pydantic des utilisateurs, acheteurs, inscriptions,
offres, audit et données brutes.

### `backend/app/services/`

- `pipeline.py` : orchestration de la collecte et du traitement ;
- `scoring_orchestrator.py` : règles puis fallback IA ;
- `keyword_classifier.py` / `keyword_scorer.py` : scoring déterministe ;
- `ai_scorer.py` : scoring IA ;
- `ai_filter_and_extract.py` : filtrage et extraction IA ;
- `local_llm_client.py` : client Ollama ;
- `buyer_matcher.py` / `buyer_rematcher.py` : rapprochement acheteurs ;
- `buyer_importer.py` : import Excel ;
- `buyer_ocr_importer.py` : OCR et import scanné ;
- `detail_fetcher.py` : récupération sécurisée des détails ;
- `export_service.py` : exports Excel/PDF ;
- `notifier.py` : notifications ;
- `mailer.py` : SMTP ;
- `reporting.py` : rapports ;
- `pipeline_logger.py` : logs fonctionnels ;
- `raw_dump.py` : dumps bruts optionnels ;
- `source_catalog_service.py` : catalogue et abonnements ;
- `source_credentials.py` : chiffrement/déchiffrement ;
- `process_manager.py` : contrôle local worker/beat ;
- `config_service.py` : services de configuration.

### `backend/app/services/scrapers/`

- `base_scraper.py` : contrat de scraper ;
- `onmp_scraper.py` : connecteur ONMP ;
- `tuneps_scraper.py` : connecteur TUNEPS ;
- `universal_scraper.py` : scraper générique HTTP/Playwright.

### `backend/app/workers/`

- `tasks.py` : tâches Celery de pipeline, alertes, rapports et tâches différées ;
- `cleanup_tasks.py` : purges et nettoyage.

---

## 9. Arborescence frontend

### `frontend/src/api/`

Modules Axios par domaine :

- authentification et client HTTP ;
- tenders ;
- acheteurs ;
- inscription ;
- configuration ;
- sources ;
- commerciaux ;
- entreprises ;
- utilisateurs ;
- audit ;
- administration système ;
- suggestions IA.

### `frontend/src/pages/`

- `LoginPage.jsx`
- `RegisterPage.jsx`
- `DashboardPage.jsx`
- `TendersPage.jsx`
- `TenderDetailPage.jsx`
- `RejectedTendersPage.jsx`
- `BuyersPage.jsx`
- `SettingsPage.jsx`
- `AdminPage.jsx`
- `AiOnboardingPage.jsx`

### `frontend/src/components/`

- composants de layout ;
- composants d'offres ;
- composants acheteurs ;
- composants UI génériques ;
- boutons d'export ;
- badges de score et statut.

### `frontend/src/hooks/`

Hooks React Query pour :

- tenders ;
- acheteurs ;
- dashboard ;
- données serveur et invalidation de cache.

### `frontend/src/context/`

`AuthContext.jsx` gère la session utilisateur et le contexte d'authentification.

Le JWT reste dans un cookie httpOnly côté navigateur et n'est pas stocké dans
le local storage JavaScript.

### `frontend/src/utils/`

Formatage, téléchargement, catégories, couleurs de score et détails d'affichage.

---

## 10. Base de données et migrations

Alembic est utilisé pour versionner le schéma.

Commandes importantes depuis `backend` :

```powershell
alembic heads
alembic check
alembic upgrade head
alembic downgrade base
```

Tables métier principales :

- `companies`
- `users`
- `commercials`
- `configuration`
- `scraping_sources`
- `company_sources`
- `source_accounts`
- `sotradies`
- `company_tenders`
- `known_buyers`
- `sent_log`
- `audit_log`
- `pipeline_log`
- `system_action_log`

Les migrations historiques ne doivent pas être supprimées, même lorsqu'une
migration contient un `pass`, car elles font partie de la chaîne Alembic.

---

## 11. Sécurité

Contrôles présents :

- mots de passe hashés avec bcrypt ;
- JWT signé ;
- cookie httpOnly et SameSite ;
- invalidation de session via `token_version` ;
- contrôle du profil et de l'entreprise ;
- isolation `company_id` ;
- contrôles par affectation commercial ;
- headers de sécurité HTTP ;
- CORS configurable ;
- rate limiting ;
- protections SSRF HTTP et navigateur ;
- vérification TLS TUNEPS activée par défaut ;
- identifiants de sources chiffrés ;
- prévention de l'injection de formules dans les exports ;
- image Docker exécutée en utilisateur non-root ;
- secrets fournis par variables d'environnement.

À ne jamais commiter :

- `.env` ;
- mots de passe ;
- clés JWT ;
- clés de chiffrement ;
- dump Redis ;
- logs de production ;
- exports contenant des données clients.

---

## 12. Configuration TUNEPS

La configuration de production attendue est :

```text
TUNEPS_SSL_VERIFY=true
TUNEPS_CA_BUNDLE=/app/backend/app/certs/tuneps_chain.pem
```

Le certificat est stocké dans :

```text
backend/app/certs/tuneps_chain.pem
```

Les identifiants TUNEPS ne doivent être transmis que lorsque TLS est vérifié.
La documentation opérationnelle associée est
[TUNEPS_CONFIGURATION.md](docs/TUNEPS_CONFIGURATION.md).

---

## 13. Déploiement Render

`render.yaml` définit :

- PostgreSQL ;
- Redis broker Celery ;
- Redis cache ;
- service web ;
- worker Celery ;
- scheduler Celery Beat.

Le service web :

1. construit l'image Docker ;
2. exécute `alembic upgrade head` ;
3. exécute `python -m scripts.bootstrap` ;
4. expose l'API et le frontend ;
5. utilise `/health` comme liveness check.

Commandes worker :

```text
celery -A app.core.celery_app worker --loglevel=INFO --concurrency=2
```

Commande scheduler :

```text
celery -A app.core.celery_app beat --loglevel=INFO --schedule=/tmp/celerybeat-schedule
```

Variables sensibles attendues par Render :

- `DATABASE_URL`
- `REDIS_URL`
- `CACHE_REDIS_URL`
- `JWT_SECRET_KEY`
- `SOURCE_CREDENTIALS_KEY`
- `INITIAL_ADMIN_EMAIL`
- `INITIAL_ADMIN_PASSWORD`
- paramètres SMTP.

Les valeurs réelles ne doivent pas figurer dans ce document.

---

## 14. Développement local

### Backend

Depuis la racine du projet :

```powershell
.\.venv\Scripts\Activate.ps1
Set-Location backend
$env:PYTHONPATH = "."
python -m pytest scripts -q
python -m compileall -q app scripts
python -c "import app.main; print('Import OK')"
```

### Frontend

```powershell
Set-Location frontend
npm ci
npm run build
npx eslint src
```

### Vérification Docker

Depuis la racine :

```powershell
docker build --tag sotradies-audit .
```

---

## 15. État de validation connu

La dernière validation locale connue a obtenu :

- 87 tests backend réussis ;
- compilation Python réussie ;
- import FastAPI réussi ;
- une tête Alembic ;
- aucune dérive détectée par `alembic check` ;
- build frontend réussi ;
- ESLint réussi ;
- build Docker réussi.

Les validations qui nécessitent des services externes ou une infrastructure
réelle doivent être exécutées séparément :

- cycle complet Alembic `upgrade / downgrade / upgrade` sur PostgreSQL temporaire ;
- Redis et Celery ;
- SMTP ;
- pipeline de scraping complet ;
- sauvegarde et restauration PostgreSQL ;
- tests de charge et mémoire OCR ;
- configuration Render réelle.

---

## 16. Règles pour une nouvelle intervention technique

Avant de modifier le code :

1. vérifier `git status` ;
2. activer `.venv` ;
3. lire le module concerné et ses tests ;
4. rechercher les usages du symbole avant de supprimer un fichier ;
5. ne jamais supprimer une migration historique ;
6. ne jamais exposer de secret ;
7. utiliser les tests ciblés puis la suite complète ;
8. vérifier backend, frontend et documentation lorsqu'un contrat API change ;
9. distinguer une dette technique d'une erreur fonctionnelle confirmée ;
10. conserver l'isolation multi-tenant sur chaque endpoint par identifiant.
