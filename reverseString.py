s = input()

def reverse_string(s):
    return s[::-1]

if s:
    print(reverse_string(s))
else:
    print("No string provided")
