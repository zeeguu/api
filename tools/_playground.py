from zeeguu_core.model import User

user = User.find_by_id(534)
print(user.name)
