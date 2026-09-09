# forge/gui/helpers.py
def handle_drop(event, var):
    """Handle drag‑and‑drop for tkinterdnd2."""
    raw = event.data
    if raw.startswith('{') and raw.endswith('}'):
        raw = raw[1:-1]
    paths = [p.strip('{}') for p in raw.split() if p.strip()]
    if paths:
        var.set(paths[0])
