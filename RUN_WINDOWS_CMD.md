# Run on Windows 11 Command Prompt

1. Extract this ZIP and open `AiHealth-main`, the folder containing `requirements.txt`.
2. In File Explorer, click the address bar, type `cmd`, press Enter. Commands below run in that folder.

```cmd
py --version
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
python -m backend.manage init
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. Press Ctrl+C to stop. To restart, open CMD in the same folder, activate the environment, and rerun the uvicorn command. Do not run database initialization against production without a backup. For `requirements.txt not found`, verify you opened `AiHealth-main`, not its parent. For an occupied port, use `--port 8001` and open that URL. For a failed database connection, inspect `DATABASE_URL` in `.env`. Use Ctrl+F5 for stale assets. Do not copy `.env` or real medical records into a shared ZIP.
