#!/bin/env python
import os

os.environ["ZEEGUU_API_CONFIG"] = os.path.expanduser('~/.config/zeeguu/api.cfg')

from zeeguu_api.app import app as application
application.logger.debug ( application.instance_path)

# Uncomment following lines if you want to try this out w/o wsgi
# application.run(
#     host=application.config.get("HOST", "localhost"),
#     port=application.config.get("PORT", 9000)
# )
