# Deploy To Streamlit Community Cloud

## Repo Settings

If you deploy from the existing `vnstock` repository, use these values:

| Field | Value |
|---|---|
| Repository | `tintinheo/vnstock` or your fork |
| Branch | `main` or your active deployment branch |
| Main file path | `TradingOSGPTPlus/streamlit_app.py` |
| Python version | `3.11` or `3.12` |

If you split `TradingOSGPTPlus` into its own repository, use `streamlit_app.py` as the main file path.

The project-level `streamlit_app.py` delegates to `app/ui/streamlit_app.py` so the deployment path is short and stable in either layout.

## Before Deploying

1. Push this folder to GitHub.
2. Confirm these files are in the repository root:
   - for the existing monorepo: `TradingOSGPTPlus/streamlit_app.py`
   - for a standalone repo: `streamlit_app.py`
   - `requirements.txt` in the same directory as the entrypoint
3. Do not commit `.env`, `data_cache/`, `audit_logs/`, or generated reports.

Note: Streamlit Community Cloud only reads `.streamlit/config.toml` from the GitHub repository root. The included `TradingOSGPTPlus/.streamlit/config.toml` is used automatically when this folder is deployed as its own repository. In the existing monorepo, the app will still run without the theme config unless you copy that config to the repo root.

## Streamlit Cloud Steps

1. Go to `https://share.streamlit.io`.
2. Click `Create app`.
3. Choose `Yup, I have an app`.
4. Select the GitHub repo and branch.
5. Set `Main file path` to `TradingOSGPTPlus/streamlit_app.py` for the existing `vnstock` repo.
6. Open `Advanced settings`.
7. Select Python `3.11` or `3.12`.
8. Optional: paste settings from `.streamlit/secrets.toml.example`.
9. Click `Deploy`.

## Important Runtime Notes

- Streamlit Community Cloud storage is ephemeral. Cache and audit files can be written while the app runs, but they are not a durable database.
- The app uses KBS/CafeF public data at runtime. If those sources block cloud traffic or change schema, the app will show a data-unavailable error instead of fabricating prices.
- No paid API key is required for the MVP.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: app` | Wrong entrypoint or repo root | In the monorepo use `TradingOSGPTPlus/streamlit_app.py`; in a standalone repo use `streamlit_app.py` |
| Dependency install failure | Cloud cannot build one package | Check app logs; keep only `requirements.txt` as dependency file |
| Data unavailable | KBS/CafeF failed and no valid cache exists | Try another ticker, retry later, or add validated backup adapters |
| App works locally but not cloud | Path or Python version mismatch | Run locally from repo root: `streamlit run streamlit_app.py` |
| Local `python.exe` launcher/session error | Windows Microsoft Store Python alias, not a real runtime | Install Python 3.11+ and disable App Execution Alias for Python |
