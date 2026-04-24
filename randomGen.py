import secrets
import string

def generate_password(length=14):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ""
    for i in range(length):
        password += secrets.choice(characters)
    return password

print(generate_password())
print(generate_password(20))
