#!/usr/bin/env python
# -*- coding: utf8 -*-

from zeeguu_api import app

application = app.app

print("Instance folder:", application.instance_path)
application.run(
    host=application.config.get("HOST", "localhost"),
    port=application.config.get("API_PORT", 9001),
)
