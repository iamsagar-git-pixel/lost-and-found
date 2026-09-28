# Campus Lost & Found

A small Flask and SQLite web app for posting and browsing lost or found items on campus.

## Run in VS Code

1. Install Python 3.10 or newer.
2. Open this folder in VS Code and open Terminal > New Terminal.
3. Create and activate a virtual environment:

   **Windows PowerShell**

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   **macOS/Linux**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

4. Install the dependency and start the app:

   ```bash
   pip install -r requirements.txt
   python app.py
   ```

5. Open http://127.0.0.1:5000 in your browser.

## Admin page

Open http://127.0.0.1:5000/admin and sign in with the local demo password `campusadmin`. Admins can review listings and student ID card submissions, approve or reject student registrations, and mark listings open or resolved.

## Student verification

1. A student registers at http://127.0.0.1:5000/register with their name, campus email, password, and a photo of their campus ID.
2. The account remains pending, so the student cannot sign in or post yet.
3. An admin signs in at `/admin`, reviews the ID card from the Student verification queue, and approves or rejects the application.
4. Approved students sign in at http://127.0.0.1:5000/login and reach their account page at `/student`. Only approved accounts can post listings.

ID photos are stored in `private/student_ids/`, outside the public static folder, and the image route requires an admin session. Student email addresses are used as contact details on listings they create, and the registration page tells students this before signup. Use synthetic accounts and sample ID images for classroom demos.

If the college has a known email domain, set it to restrict registration to that domain. Also replace the demo admin password and session key before sharing the app:

```powershell
$env:CAMPUS_ADMIN_PASSWORD = "your-own-password"
$env:CAMPUS_SECRET_KEY = "a-long-random-secret"
$env:CAMPUS_EMAIL_DOMAIN = "college.edu"
python app.py
```

These environment variables apply to the current terminal session. The email-domain setting is optional; when omitted, admins verify campus status from the uploaded ID photo. This single-admin-password setup is for a local student project demo, not a production campus service.

The SQLite database is created automatically as `campus_items.db`, with sample listings the first time the app runs. Listing photos are stored in `static/uploads/`; student ID images stay in `private/student_ids/`.

## Features

- Browse open lost and found listings
- Search title, description, and campus location
- Filter by listing type and category
- Register and submit a campus ID for admin approval
- Sign in to a verified student account and post listings
- Contact the listing owner by email
- Track your listings and resolve your own reports

This is a student project starter. It uses manual ID review and a shared admin password; add institutional email verification and stronger deployment controls before using it with real student data.
