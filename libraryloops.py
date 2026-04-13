letter = input("Enter a starting letter: ").strip().upper()
     

match_count = 0
     

print(f"Books starting with {letter} that are Available:")
     

for title, status in library.items():
    if title.upper().startswith(letter) and status == "Available:
        print(title)
        match_count += 1
     

print("Total matching books: {match_count}")