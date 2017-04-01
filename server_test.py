#!/bin/env python

import os

os.environ["ZEEGUU_API_CONFIG"] = os.path.expanduser('~/.config/zeeguu/api.cfg')

from zeeguu_api.app import app as application
application.logger.debug ( application.instance_path)

# a basic server to test
application.run(
    host=application.config.get("HOST", "localhost"),
    port=application.config.get("PORT", 9000)
)
