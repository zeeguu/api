from zeeguu.core.model import User, Session
import requests
import json

from zeeguu.api.app import create_app
from zeeguu.core.model import db

app = create_app()
app.app_context().push()


user = User.find_by_id(4607)

session = Session.create_for_user(user)
db.session.add(session)
db.session.commit()

# Prepare the request
# Prepare the request
url = f"http://localhost:9001/generate_daily_lesson?session={session.uuid}"
headers = {"Content-Type": "application/json"}

print(f"Session UUID: {session.uuid}")

try:
    # Make the API call
    print(f"Making POST request to: {url}")
    response = requests.post(url, headers=headers, json={})

    print(f"Response status: {response.status_code}")
    print(f"Response headers: {dict(response.headers)}")

    if response.status_code == 200:
        result = response.json()
        print("✅ Success! Audio lesson generated:")
        print(json.dumps(result, indent=2))
    else:
        print("❌ Error response:")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print(response.text)

except requests.exceptions.ConnectionError:
    print("❌ Connection error. Make sure the API server is running on localhost:9001")
except Exception as e:
    print(f"❌ Unexpected error: {str(e)}")

finally:
    # Clean up the session
    db.session.delete(session)
    db.session.commit()
