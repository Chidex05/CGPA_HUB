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

Without `DATABASE_URL`, the app uses local SQLite at
`instance/cgpa_hub.sqlite3` and creates a local session key automatically.

## Deploying with Supabase on Vercel

The app is configured for Vercel's Flask runtime. Its build script copies
`static/` assets into `public/static/`, where Vercel serves them from its CDN.
The app connects to Supabase through PostgreSQL; it does not use Supabase
Auth or the Supabase API keys.

1. Create a Supabase project. In its dashboard, open **Connect** and choose
   the **Transaction pooler** connection string. Use the URI format and keep
   its SSL option (`sslmode=require`). Replace the password placeholder with
   your database password; URL-encode special characters in the password.
2. In Vercel **Project Settings → Environment Variables**, add:
   - `DATABASE_URL`: the complete Supabase transaction-pooler URI.
   - `SECRET_KEY`: a strong, randomly generated secret.
   - `SESSION_COOKIE_SECURE`: `true`.

   Add them to Production. If you deploy Preview builds, use a separate
   Supabase project for Preview and configure its own `DATABASE_URL` there.
3. Deploy the project. On startup, the app creates its tables and starter
   content in the Supabase database.
4. Link this local project with `vercel link`, then create the production admin
   account from PowerShell:

   ```powershell
   vercel env run --environment production -- py -3.12 -m flask --app app admin create-admin
   ```

   The command prompts for the username and password without adding either to
   source control. Open `https://your-domain/admin` to sign in.

The app disables automatic prepared statements so it can use Supabase's
transaction pooler reliably. Never commit database URLs, passwords, or session
secrets. Admin accounts, content, and analytics are stored in Supabase when
`DATABASE_URL` is set; the Vercel filesystem is not used for persistent
database storage. Data already saved in a local SQLite database is not copied
automatically to Supabase. Export or back up any local edits you need before
switching production over.

## Admin workspace

The admin panel includes:

- An overview of published articles, drafts, and page views.
- Blog post creation, editing, featuring, draft/publish controls, and deletion.
- Editable home-page and blog copy, site announcements, branding, and footer text.
- 30-day page-view totals and popular pages.

The first run seeds the blog with the existing six guides. Locally, posts and
settings are stored in `instance/cgpa_hub.sqlite3`, which is intentionally
excluded from Git. Back up this file to preserve local admin accounts, posts,
settings, and analytics.

Analytics are aggregate page counts only. The app does not store visitor names,
accounts, IP addresses, or individual browsing histories.
