# zeeguu.cl = Zeeguu Command Line
# Package that creates an app and pushes its context such that tools can be run
# The alternative would be to have run the three lines below every time one wanted to
# run a tool or interact with the zeeguu from the REPL

from zeeguu.api.app import create_app

app = create_app()
app.app_context().push()
