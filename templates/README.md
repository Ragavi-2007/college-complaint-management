# College Complaint Management App

A beginner-friendly Flask + SQLite web application for managing college complaints.

## Main roles

### Student
- Register and login
- Submit complaint
- Upload photo proof
- Choose anonymous option
- Select Low / Medium / High priority
- Track complaint status
- View admin remarks

### Admin
- Login
- View all complaints
- Assign complaints
- Update Pending / Assigned / Resolved status
- Add remarks
- View complaint records

## Technology
- Frontend: HTML, CSS, Bootstrap
- Backend: Python Flask
- Database: SQLite
- Image upload: Flask + Pillow-compatible image files

## Installation

Open the VS Code terminal inside this folder:

```text
py -m pip install -r requirements.txt
```

Run:

```text
py app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Admin demo account

Username:
```text
admin
```

Password:
```text
admin123
```

The database is created automatically the first time the application runs.

## Important
For a real deployment, change the Flask secret key and admin password.


## Phone-installable app (PWA)
This version is also configured as a Progressive Web App (PWA). On Android Chrome, open the deployed HTTPS address and use the **Install App** button when it appears, or Chrome menu -> **Install app** / **Add to Home screen**.

### Important for phone use
`http://127.0.0.1:5000` works only on the computer running Flask. To use the app from other phones, deploy the Flask application to a server with an HTTPS URL. The same PWA files will then allow users to install it on their phones.

The PWA does not replace the Flask backend or SQLite database; it installs the existing web interface as an app-like experience.
