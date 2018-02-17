#!/bin/env python
import os

if not os.environ["ZEEGUU_API_CONFIG"]:
    os.environ["ZEEGUU_API_CONFIG"] = os.path.expanduser('~/.config/zeeguu/api.cfg')
    print (os.environ["ZEEGUU_API_CONFIG"])

if not os.environ["DASHBOARD_CONFIG"]:
    os.environ["DASHBOARD_CONFIG"] = os.path.expanduser('~/.config/zeeguu/dashboard.cfg')
    print (os.environ["DASHBOARD_CONFIG"])

if not os.environ["DASHBOARD_LOG_DIR"]:
    os.environ["DASHBOARD_LOG_DIR"]= os.path.expanduser('~/.logs/')
    print (os.environ["DASHBOARD_LOG_DIR"])


from zeeguu_api.app import app as application
application.logger.debug ( application.instance_path)

# Uncomment following lines if you want to try this out w/o wsgi
# application.run(
#     host=application.config.get("HOST", "localhost"),
#     port=application.config.get("PORT", 9000)
# )


