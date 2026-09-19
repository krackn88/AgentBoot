#!/usr/bin/env python3
"""Run the license activation API + vendor dashboard."""

import os

from license_server.app import app

if __name__ == "__main__":
    host = os.environ.get("LICENSE_HOST", "0.0.0.0")
    port = int(os.environ.get("LICENSE_PORT", "8082"))
    app.run(host=host, port=port, debug=False)
