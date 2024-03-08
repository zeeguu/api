#!/bin/env python
import sys
import logging

# this is needed since when run as wsgi this script
# can't access the systems' env vars. so we load them
# in another local configuration file.
try:
    import env_var_defs

except:
    print("didn't find env_var_defs. hopefully there's envvars defined")

from zeeguu.api.app import create_app

application = create_app()

application.logger.debug(application.instance_path)

logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)

# try:
#     import flask_monitoringdashboard as dashboard
#     from .custom_fmd_graphs import daily_visitors

#     dashboard.config.init_from(envvar="FLASK_MONITORING_DASHBOARD_CONFIG")

#     from zeeguu.core.model import Session

#     dashboard.config.get_group_by = lambda: Session.find(request=flask.request).user_id
#     dashboard.bind(app=app)
#     daily_visitors(dashboard)
#     print("Started the Flask Monitoring Dashboard")

# except Exception as e:
#     import traceback

#     traceback.print_exc()
#     print("flask_monitornig_dashboard package is not present. Running w/o FMD.")


try:
    import flask_monitoringdashboard as fmd
    import flask
    from zeeguu.core.model import Session

    fmd.config.init_from(envvar="FLASK_MONITORING_DASHBOARD_CONFIG")
    fmd.config.get_group_by = lambda: Session.find(request=flask.request).user_id
    fmd.bind(application)
except Exception as e:
    import traceback

    traceback.print_exc()

if len(sys.argv) > 1 and sys.argv[1] == "run":
    # Make sure to keep this in sync with zeeguu_api_dev.wsgi
    application.run(
        host=application.config.get("HOST", "localhost"),
        port=application.config.get("PORT", 9001),
        debug=True,
    )
