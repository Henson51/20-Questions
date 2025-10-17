
import json

# Load the JSONL file
with open("noun_property_ratings.jsonl", "r") as file:
    raw_data = [json.loads(line) for line in file]

# Convert list of entries into a dictionary: noun -> properties
noun_data = {
    entry["noun"]: {k: v for k, v in entry.items() if k != "noun"}
    for entry in raw_data
}


# Greedy question selector
def select_best_question(noun_data, remaining_nouns, asked_properties):
    best_property = None
    best_split_score = float('inf')
    best_threshold = None
    best_type = None

    for prop in noun_data[next(iter(noun_data))]:
        if prop in asked_properties:
            continue

        values = [noun_data[noun][prop] for noun in remaining_nouns if prop in noun_data[noun]]
        if not values:
            continue

        if all(isinstance(v, bool) for v in values):
            yes = [v for v in values if v]
            no = [v for v in values if not v]
            split_score = abs(len(yes) - len(no))

            if split_score < best_split_score:
                best_property = prop
                best_split_score = split_score
                best_type = "binary"
        
        elif all(isinstance(v, (int, float)) for v in values):
            for threshold in range(2, 9):
                yes = [v for v in values if v > threshold]
                no = [v for v in values if v <= threshold]
                split_score = abs(len(yes) - len(no))

                if 0 < len(yes) < len(values) and split_score < best_split_score:
                    best_property = prop
                    best_split_score = split_score
                    best_threshold = threshold
                    best_type = "continuous"
    return best_property, best_type, best_threshold

def play_game(noun_data):
    remaining_nouns = set(noun_data.keys())
    asked_properties = set()
    question_count = 0

    while question_count < 19 and len(remaining_nouns) > 1:
        best_prop, prop_type, threshold = select_best_question(noun_data, remaining_nouns, asked_properties)

        if not best_prop:
            print("No useful question found")
            break

        if prop_type == "binary":
            print(f" Is it {best_prop} ?")
            answer = int(input("Press 1 for yes, 2 for no"))

        elif prop_type == "continuous":
    # Find a noun with the property value == threshold
            reference_noun = next(
                (noun for noun in remaining_nouns if noun_data[noun].get(best_prop) == threshold),
        None
    )

            if reference_noun:
                print(f"Is its {best_prop} greater than the {reference_noun}'s {best_prop}?")
            else:
                print(f"Is its {best_prop} greater than {threshold}?")

            answer = int(input("Press 1 for yes, 2 for no"))
        
        if prop_type == "binary":
            remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop) is answer}
        elif prop_type == "continuous":
            if answer == 1:
                remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop, 0) > threshold}
            else:
                remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop, 0) <= threshold}

        asked_properties.add(best_prop)
        question_count += 1

    guess = list(remaining_nouns)[0] if remaining_nouns else "unknown"
    print(f" Are you thinking of {guess}?")
    return guess


play_game(noun_data)