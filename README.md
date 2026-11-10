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

## Deploying on Vercel

The app is configured for Vercel's Flask runtime. Its build script copies
`static/` assets into `public/static/`, where Vercel serves them from its CDN.
For a Vercel deployment:

1. Add a managed PostgreSQL database to the Vercel project using the Vercel
   Marketplace (for example, Neon). Configure its pooled connection string as
   the `DATABASE_URL` environment variable for Production. Use a separate
   database for Preview deployments so test edits cannot change production data.
2. Add a strong, random `SECRET_KEY` and set `SESSION_COOKIE_SECURE=true` in
   the Vercel Production environment variables. Redeploy after changing them.
3. Deploy the branch containing these changes. The app creates its database
   tables and starter content on first startup.
4. Link this local project with `vercel link`, then create the production admin
   account from PowerShell:

   ```powershell
   vercel env run --environment production -- py -3.12 -m flask --app app admin create-admin
   ```

   The command prompts for the username and password without adding either to
   source control. Open `https://your-domain/admin` to sign in.

Never commit database URLs, passwords, or session secrets. Admin accounts,
content, and analytics are stored in PostgreSQL when `DATABASE_URL` is set;
the Vercel filesystem is not used for persistent database storage. Data already
saved in a local SQLite database is not copied automatically to PostgreSQL.
Export or back up any local edits you need before switching production over.

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
