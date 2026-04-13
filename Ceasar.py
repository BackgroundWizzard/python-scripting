def caesar_cipher(text, shift):
    result = ""

    for char in text:
        if char.isalpha():
            if char.islower():
                new_char = chr((ord(char) - ord('a') + shift) % 26 + ord('a'))
            else:
                new_char = chr((ord(char) - ord('A') + shift) % 26 + ord('A'))
            
            result += new_char
        else:
            result += char

    return result


print(caesar_cipher("abc", 3))
print(caesar_cipher("xyz", 2))
print(caesar_cipher("Hello, World!", 5))