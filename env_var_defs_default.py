import os

os.environ["ZEEGUU_API_CONFIG"] = os.path.expanduser('<path-to-/api.cfg')
print (os.environ["ZEEGUU_API_CONFIG"])

os.environ["DASHBOARD_CONFIG"] = os.path.expanduser('<path-to-/dashboard.cfg')
print (os.environ["DASHBOARD_CONFIG"])

os.environ["DASHBOARD_LOG_DIR"]= os.path.expanduser('<path-to-/.logs/')
print (os.environ["DASHBOARD_LOG_DIR"])

