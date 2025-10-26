import json

print('Enter 1 for YES, 0 for NO')

with open('categories_tree.json', 'r') as f:
    tree = json.load(f)

questions = tree["Questions"]
categories = tree["Categories"]

node = questions
while not isinstance(node, str):
    answer = input(node["Question"] + " (0/1): ").strip().lower()
    if (answer == '1'):
        node = node["YES"]
    elif (answer == '0'):
        node = node["NO"]
    else:
        print("Invalid input. Please enter 1 for YES or 0 for NO.")
        continue

category = node

print(f"Category: {category}")
print(f"# of Options: {len(categories[category])}")
