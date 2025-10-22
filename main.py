import json

with open("noun_property_ratings.jsonl", "r") as file:
    raw_data = [json.loads(line) for line in file]

noun_data = {
    entry["noun"]: {k: v for k, v in entry.items() if k!= "noun"}
    for entry in raw_data
}


properties = set()
for prop in noun_data.values():
    properties.update(prop.keys())



################################################################################ Greedy Algorithm
def best_question(noun_data, remaining_nouns, asked_properties):
    best_property = None
    best_split_score = float("inf")
    best_threshold = None
    best_type = None

    for prop in properties: 
        if prop in asked_properties:
            continue

        values = [noun_data[noun][prop] for noun in remaining_nouns if prop in noun_data[noun]]

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

                if 0 < len(yes) <len(values) and split_score < best_split_score:
                    best_property = prop
                    best_split_score = split_score
                    best_threshold = threshold
                    best_type = "continuous"
    return best_property, best_type, best_threshold
##########################################################################################################Game       
def play_game(noun_data):
    remaining_nouns = set(noun_data.keys())
    asked_properties = set()
    question_count = 0

    while question_count < 19 and len(remaining_nouns) > 1:
        best_prop, prop_type, threshold = best_question(noun_data, remaining_nouns, asked_properties)

        if prop_type == "binary":
            print(f" Is it {best_prop}?")
            answer = int(input("Press 1 for yes, 2 for no"))

        elif prop_type == "continuous":
            reference_noun = next(
                (noun for noun in remaining_nouns if noun_data[noun].get(best_prop) == threshold), None)
            
            if reference_noun:
                print(f"Is its {best_prop} greater than the {best_prop} of a {reference_noun}?")
            else:
                print(f"is its {best_prop} greater than {threshold}?")
            answer = int(input("press 1 for yes, 2 for no"))

        if prop_type == "binary":
            remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop) is answer}
        elif prop_type == "continuous":
            if answer == 1:
                remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop, 0) > threshold}
            else:
                remaining_nouns = {noun for noun in remaining_nouns if noun_data[noun].get(best_prop, 0) <= threshold}

        asked_properties.add(best_prop)
        question_count += 1
        print(len(remaining_nouns))
        
            
    guess = list(remaining_nouns)[0] if remaining_nouns else "unkown"
    print(f"are you thinking of {guess} ?")
    return guess

play_game(noun_data)