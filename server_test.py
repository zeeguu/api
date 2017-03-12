#!/bin/env python
from zeeguu_api.app import app as application
application.logger.debug ( application.instance_path)
application.logger.debug ( application.config.get("SQLALCHEMY_DATABASE_URI"))

# a basic server to test
application.run(
    host=application.config.get("HOST", "localhost"),
    port=application.config.get("PORT", 9000)
)
