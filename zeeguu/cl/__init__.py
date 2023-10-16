# CL = Command Line
# Utility package that creates an app and pushes its context such that tools can be run

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()
