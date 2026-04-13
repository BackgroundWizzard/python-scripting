text = input("Enter a string: ")

def is_palindrome(text):
    cleaned = text.lower().replace(" ", "")
    reversed_text = cleaned[::-1]
    return cleaned == reversed_text

result = is_palindrome(text)
print(result)