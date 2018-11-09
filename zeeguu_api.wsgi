#!/bin/env python
import sys

# this is needed since when run as wsgi this script
# can't access the systems' env vars. so we load them
# in another local configuration file.  
try:
    print("found the env_var_defs file")
    import env_var_defs
except:
    print("didn't find env_var_defs. hopefully there's envvars defined")

from zeeguu_api.app import app as application

application.logger.debug(application.instance_path)

if len(sys.argv) > 1 and sys.argv[1] == "server":
    # Uncomment following lines if you want to try this out w/o wsgi
    application.run(
        host=application.config.get("HOST", "localhost"),
        port=application.config.get("PORT", 9001)
    )
