import json

# Load category tree
with open('categories_tree.json', 'r') as f:
    tree = json.load(f)

questions = tree["Questions"]
categories = tree["Categories"]

# Traverse decision tree
print('Enter 1 for YES, 0 for NO')
node = questions
while not isinstance(node, str):
    answer = input(node["Question"] + " (0/1): ").strip().lower()
    if answer == '1':
        node = node["YES"]
    elif answer == '0':
        node = node["NO"]
    else:
        print("Invalid input. Please enter 1 for YES or 0 for NO.")
        continue

selected_category = node
print(f"\nSelected Category: {selected_category}")
print(f"# of Options: {len(categories[selected_category])}")

# Load noun property data
with open("noun_property_ratings.jsonl", "r") as file:
    raw_data = [json.loads(line) for line in file]

# Filter data by selected category
filtered_data = [entry for entry in raw_data if entry["category"] == selected_category]

# Organize data: noun -> {property: rating}
noun_data = {}
property_types = {}
for entry in filtered_data:
    noun = entry["noun"]
    prop = entry["property"]
    rating = entry["rating"]
    ptype = entry["property_type"]

    if noun not in noun_data:
        noun_data[noun] = {}
    noun_data[noun][prop] = rating
    property_types[prop] = ptype

# Extract all properties
properties = set(property_types.keys())

# Greedy algorithm to select best question
def best_question(noun_data, remaining_nouns, asked_properties):
    best_property = None
    best_split_score = float("inf")
    best_threshold = None
    best_type = None
    best_reference = None

    for prop in properties:
        if prop in asked_properties:
            continue

        values = [(noun, noun_data[noun][prop]) for noun in remaining_nouns if prop in noun_data[noun]]

        if property_types[prop] == "boolean":
            yes = [v for _, v in values if v == 1]
            no = [v for _, v in values if v == 0]
            split_score = abs(len(yes) - len(no))

            if split_score < best_split_score:
                best_property = prop
                best_split_score = split_score
                best_type = "binary"

        elif property_types[prop] == "scale":
            sorted_values = sorted(values, key=lambda x: x[1])
            for i in range(1, len(sorted_values)):
                threshold = sorted_values[i][1]
                yes = [v for _, v in values if v > threshold]
                no = [v for _, v in values if v <= threshold]
                split_score = abs(len(yes) - len(no))

                if 0 < len(yes) < len(values) and split_score < best_split_score:
                    best_property = prop
                    best_split_score = split_score
                    best_threshold = threshold
                    best_type = "continuous"
                    best_reference = sorted_values[i][0]

    return best_property, best_type, best_threshold, best_reference

# Game logic
def play_game(noun_data):
    remaining_nouns = set(noun_data.keys())
    asked_properties = set()
    question_count = 0

    while question_count < 19 and len(remaining_nouns) > 1:
        best_prop, prop_type, threshold, reference_noun = best_question(noun_data, remaining_nouns, asked_properties)

        if best_prop is None:
            break

        if prop_type == "binary":
            print(f"\nQ{question_count+1}: Is it {best_prop}?")
            answer = int(input("Press 1 for yes, 2 for no: "))

        elif prop_type == "continuous":
            if reference_noun:
                print(f"\nQ{question_count+1}: Is its {best_prop} greater than the {best_prop} of a {reference_noun}?")
            else:
                print(f"\nQ{question_count+1}: Is its {best_prop} greater than {threshold}?")
            answer = int(input("Press 1 for yes, 2 for no: "))

        # Filter remaining nouns
        if prop_type == "binary":
            remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop) == (1 if answer == 1 else 0)}
        elif prop_type == "continuous":
            if answer == 1:
                remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop, 0) > threshold}
            else:
                remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop, 0) <= threshold}

        asked_properties.add(best_prop)
        question_count += 1
        print(f"{len(remaining_nouns)} nouns remaining.")

    guess = list(remaining_nouns)[0] if remaining_nouns else "unknown"
    print(f"\nFinal Guess: Are you thinking of '{guess}'?")
    return guess

# Start the game
play_game(noun_data)