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
