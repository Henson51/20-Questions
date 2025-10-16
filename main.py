import json


with open(".vscode/nouns.jsonl", "r") as file:
    animals = [json.loads(line) for line in file]
        
################################################################################################################### Question 1

print("Is the animal faster than an eagle?") 
answer1 = int(input("Press 1 for yes, 2 for no"))

if answer1 == 1:
    remainingAnimals = [animal for animal in animals if animal["properties"]["speed"]["rating"] > 5]

else:
    remainingAnimals = [animal for animal in animals if animal["properties"]["speed"]["rating"] <= 5]

for animal in remainingAnimals:
    print(animal["noun"])

################################################################################################################### Question 2

print("is the animal stronger than a pig?")
answer2 = int(input("Press 1 for yes, 2 for no"))

if answer2 == 1:
    remainingAnimals = [animal for animal in remainingAnimals if animal["properties"]["strength"]["rating"] > 5]

else:
    remainingAnimals = [animal for animal in remainingAnimals if animal["properties"]["strength"]["rating"] <= 5]

for animal in remainingAnimals:
    print(animal["noun"])

################################################################################################################### Question 3
        
print("Is it smarter than a chimpanzee?")
answer3 = int(input("Press 1 for yes, 2 for no"))

if answer3 == 1:
    remainingAnimals = [animal for animal in remainingAnimals if animal["properties"]["intelligence"]["rating"] > 5]

else:
    remainingAnimals = [animal for animal in remainingAnimals if animal["properties"]["intelligence"]["rating"] <= 5]

for animal in remainingAnimals:
    print(animal["noun"])

#################################################################################################################### Question 4