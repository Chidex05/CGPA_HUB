# CGPA Hub

A GPA and CGPA calculator with academic resources for Nigerian university students.

## Run locally

Install dependencies, create an administrator, then start the app:

```powershell
py -3.12 -m pip install -r requirements.txt
py -3.12 -m flask --app app admin create-admin
py -3.12 app.py
```

The admin command asks for a username and a password (minimum 12 characters);
the password is hidden while you type. Open `http://127.0.0.1:5000/admin` to
sign in; this page is intentionally not linked from the public site. There is
no default password or public admin registration page.

The admin sign-in form's **Remember me for 30 days** option keeps the signed
session cookie persistent for 30 days. Leave it unchecked to end the session
when the browser closes. The password itself is never stored in the session.

Without `DATABASE_URL`, the app uses local SQLite at
`instance/cgpa_hub.sqlite3` and creates a local session key automatically.

## Deploying PostgreSQL on Vercel

The app is configured for Vercel's Flask runtime. Its build script copies
`static/` assets into `public/static/`, where Vercel serves them from its CDN.
The app connects to PostgreSQL through `psycopg`, so it can use Supabase,
Neon, or another PostgreSQL provider. It does not require a provider-specific
SDK or authentication API.

1. Connect a managed PostgreSQL database to your Vercel project. For Neon, you
   can use the Vercel Marketplace integration and its pooled connection string.
   For Supabase, open **Connect** and choose the **Transaction pooler** URI;
   keep `sslmode=require`. URL-encode special characters in the password.
2. In Vercel **Project Settings → Environment Variables**, configure:
   - `DATABASE_URL`: the complete pooled PostgreSQL connection URI.
   - `SECRET_KEY`: a strong, randomly generated secret.
   - `SESSION_COOKIE_SECURE`: `true`.

   Set these for Production. If you deploy Preview builds, connect a separate
   database or database branch and use its own `DATABASE_URL` so previews cannot
   change production data.
3. Deploy the project. On startup, the app creates its tables and starter
   content. Initialization is serialized across concurrent PostgreSQL function
   starts; local SQLite initialization also waits for concurrent writers.
4. Link this local project with `vercel link`, then create the production admin
   account from PowerShell:

   ```powershell
   vercel env run --environment production -- py -3.12 -m flask --app app admin create-admin
   ```

   The command prompts for the username and password without adding either to
   source control. Open `https://your-domain/admin` to sign in.

### Temporary Vercel error diagnostics

The app temporarily writes sanitized startup and unhandled-request error details
to standard error, which Vercel captures in function logs. Each entry includes
an incident ID, exception type, redacted message, and source locations. Request
failures return a generic 500 with the incident ID in the `X-Error-ID` response
header. Request bodies, headers, query strings, and stack-frame locals are not
logged. Remove the diagnostic logger, error handler, and startup logging wrapper
from `app.py` after identifying and fixing the production error.

The app disables Psycopg's automatic prepared statements for compatibility
with transaction poolers, including Supabase's. Never commit database URLs,
passwords, or session secrets. Admin accounts, content, and analytics are
stored in PostgreSQL when `DATABASE_URL` is set; the Vercel filesystem is not
used for persistent database storage. Data already saved in a local SQLite
database is not copied automatically to PostgreSQL. Export or back up any
local edits you need before switching production over.

## Admin workspace

The admin panel includes:

- An overview of published articles, drafts, and page views.
- Blog post creation, editing, featuring, draft/publish controls, and deletion.
- Editable home-page and blog copy, site announcements, branding, footer text,
  and the footer Bible verse and reference. Open **Website settings** in the
  admin dashboard to edit the verse and reference or toggle its visibility.
- 30-day page-view totals and popular pages.

The first run seeds the blog with six original guides and five student resource
articles. Existing databases receive the five new articles once, without
overwriting posts already in the CMS. The editor supports Academic Guides,
CGPA Problem Solving, Student Corner, Study & Productivity, and CGPA Hub
Updates categories, as well as an optional privacy-enhanced YouTube embed.
Locally, posts and settings are stored in `instance/cgpa_hub.sqlite3`, which is
intentionally excluded from Git. Back up this file to preserve local admin
accounts, posts, settings, and analytics.

Analytics are aggregate page counts only. The app does not store visitor names,
accounts, IP addresses, or individual browsing histories.
