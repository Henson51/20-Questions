import json

# Load the JSONL file
with open("grouped_noun_property_ratings_wide.jsonl", "r") as file:
    raw_data = [json.loads(line) for line in file]

noun_data = {
    entry["noun"]: {k: v for k, v in entry.items() if k != "noun"}
    for entry in raw_data
}


# OPTIMAL LETTER QUESTIONS (based on analysis of your 1852 nouns)
# These are ordered by information gain - ask in this sequence

LETTER_STRATEGY = [
    # Phase 1: Best discriminators (closest to 50-50 splits)
    ('contains_r', 'Does it contain the letter R?', 
     lambda n: 'r' in n.lower()),
    
    ('contains_i', 'Does it contain the letter I?', 
     lambda n: 'i' in n.lower()),
    
    ('contains_o', 'Does it contain the letter O?', 
     lambda n: 'o' in n.lower()),
    
    ('contains_t', 'Does it contain the letter T?', 
     lambda n: 't' in n.lower()),
    
    ('contains_n', 'Does it contain the letter N?', 
     lambda n: 'n' in n.lower()),
    
    # Phase 2: Starting letter (narrows significantly)
    ('starts_s', 'Does it start with the letter S?',
     lambda n: n[0].lower() == 's'),
    
    ('starts_c', 'Does it start with the letter C?',
     lambda n: n[0].lower() == 'c'),
    
    ('starts_b', 'Does it start with the letter B?',
     lambda n: n[0].lower() == 'b'),
    
    ('starts_p', 'Does it start with the letter P?',
     lambda n: n[0].lower() == 'p'),
    
    ('starts_m', 'Does it start with the letter M?',
     lambda n: n[0].lower() == 'm'),
    
    ('starts_d', 'Does it start with the letter D?',
     lambda n: n[0].lower() == 'd'),
    
    ('starts_a', 'Does it start with the letter A?',
     lambda n: n[0].lower() == 'a'),
    
    # Phase 3: Additional discriminators
    ('contains_e', 'Does it contain the letter E?',
     lambda n: 'e' in n.lower()),
    
    ('contains_a', 'Does it contain the letter A?',
     lambda n: 'a' in n.lower()),
    
    ('contains_l', 'Does it contain the letter L?',
     lambda n: 'l' in n.lower()),
    
    ('contains_s', 'Does it contain the letter S?',
     lambda n: 's' in n.lower()),
    
    # Phase 4: Ending letters
    ('ends_e', 'Does it end with the letter E?',
     lambda n: n[-1].lower() == 'e'),
    
    ('ends_r', 'Does it end with the letter R?',
     lambda n: n[-1].lower() == 'r'),
    
    ('ends_n', 'Does it end with the letter N?',
     lambda n: n[-1].lower() == 'n'),
    
    ('ends_t', 'Does it end with the letter T?',
     lambda n: n[-1].lower() == 't'),
    
    ('ends_s', 'Does it end with the letter S?',
     lambda n: n[-1].lower() == 's'),
    
    # Phase 5: Word patterns
    ('has_space', 'Does it have a space in it (is it multiple words)?',
     lambda n: ' ' in n),
    
    ('long_word', 'Is it a long word (10+ letters)?',
     lambda n: len(n.replace(' ', '')) >= 10),
]


# Secondary strategy: Category-based tiebreakers (only if needed)
CATEGORIES = {
    'exercise': {
        'test': lambda n: any(word in n.lower() for word in [
            'press', 'curl', 'squat', 'lift', 'pull', 'push', 'row', 'raise', 
            'extension', 'lunge', 'bridge', 'plank', 'crunch', 'burpee', 'jump'
        ]),
        'question': 'Is it an exercise or workout movement?'
    },
    'motorcycle': {
        'test': lambda n: any(x in n.lower() for x in [
            'ninja', 'cbr', 'gsxr', 'duke', 'monster', 'panigale', 'r1', 'r6',
            'zx', 'hayabusa', 'fireblade'
        ]) or any(c.isdigit() for c in n),
        'question': 'Is it a motorcycle model?'
    },
    'state': {
        'test': lambda n: n.lower() in {
            'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
            'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
            'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
            'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
            'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
            'new hampshire', 'new jersey', 'new mexico', 'new york',
            'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon',
            'pennsylvania', 'rhode island', 'south carolina', 'south dakota',
            'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
            'west virginia', 'wisconsin', 'wyoming'
        },
        'question': 'Is it a US state?'
    },
}


def select_best_letter_question(candidates, asked_letters):
    """Select the letter question that best splits the remaining candidates"""
    
    best_question = None
    best_ratio = 0
    
    for letter_key, question, test_fn in LETTER_STRATEGY:
        if letter_key in asked_letters:
            continue
        
        try:
            yes_nouns = [n for n in candidates if test_fn(n)]
            no_nouns = [n for n in candidates if not test_fn(n)]
        except:
            continue
        
        if not yes_nouns or not no_nouns:
            continue
        
        # Calculate how close to 50-50 this split is
        split_ratio = min(len(yes_nouns), len(no_nouns)) / max(len(yes_nouns), len(no_nouns))
        
        # Prefer questions that split more evenly
        if split_ratio > best_ratio:
            best_ratio = split_ratio
            best_question = (letter_key, question, test_fn, yes_nouns, no_nouns)
    
    return best_question


def select_category_question(candidates, asked_categories):
    """Secondary strategy: ask category question if it helps"""
    
    for cat_key, cat_info in CATEGORIES.items():
        if cat_key in asked_categories:
            continue
        
        yes_nouns = [n for n in candidates if cat_info['test'](n)]
        no_nouns = [n for n in candidates if not cat_info['test'](n)]
        
        if not yes_nouns or not no_nouns:
            continue
        
        # Only use if it gives a reasonable split
        split_ratio = min(len(yes_nouns), len(no_nouns)) / max(len(yes_nouns), len(no_nouns))
        
        if split_ratio > 0.15:  # At least 15% in smaller group
            return (cat_key, cat_info['question'], cat_info['test'], yes_nouns, no_nouns)
    
    return None


def play_game(noun_data):
    candidates = list(noun_data.keys())
    asked_letters = set()
    asked_categories = set()
    question_count = 0
    
    print(f"Think of one of the {len(candidates)} nouns...")
    print("=" * 60)
    print("I'll figure it out by asking about the letters in the word!")
    print("=" * 60)
    
    while question_count < 19 and len(candidates) > 1:
        # PRIMARY STRATEGY: Letter questions
        letter_result = select_best_letter_question(candidates, asked_letters)
        
        if letter_result:
            letter_key, question, test_fn, yes_nouns, no_nouns = letter_result
            question_count += 1
            
            yes_count = len(yes_nouns)
            no_count = len(no_nouns)
            split_ratio = min(yes_count, no_count) / max(yes_count, no_count)
            
            print(f"\nQ{question_count} [LETTER]: {question}")
            print(f"   (This splits {yes_count} yes / {no_count} no)")
            answer = input("Enter 1 for YES, 0 for NO: ").strip()
            answer_bool = (answer == "1")
            
            asked_letters.add(letter_key)
            
            # Filter candidates
            if answer_bool:
                candidates = yes_nouns
            else:
                candidates = no_nouns
            
            print(f"   → {len(candidates)} candidates remaining")
            
            # Show top candidates if narrowed down enough
            if len(candidates) <= 10:
                print(f"   → Remaining: {', '.join(sorted(candidates)[:10])}")
            
            continue
        
        # SECONDARY STRATEGY: Category questions (only if letter questions exhausted)
        category_result = select_category_question(candidates, asked_categories)
        
        if category_result:
            cat_key, question, test_fn, yes_nouns, no_nouns = category_result
            question_count += 1
            
            print(f"\nQ{question_count} [CATEGORY]: {question}")
            answer = input("Enter 1 for YES, 0 for NO: ").strip()
            answer_bool = (answer == "1")
            
            asked_categories.add(cat_key)
            
            # Filter candidates
            if answer_bool:
                candidates = yes_nouns
            else:
                candidates = no_nouns
            
            print(f"   → {len(candidates)} candidates remaining")
            
            if len(candidates) <= 10:
                print(f"   → Remaining: {', '.join(sorted(candidates)[:10])}")
            
            continue
        
        # If no good questions, break
        print("   [No more discriminating questions available]")
        break
    
    # Question 20: Final guess
    print("\n" + "=" * 60)
    
    if candidates:
        # Pick the first alphabetically (or could use other logic)
        guess = sorted(candidates)[0]
        question_count += 1
        
        if len(candidates) > 1:
            print(f"Narrowed down to {len(candidates)} candidates:")
            print(f"   {', '.join(sorted(candidates)[:10])}")
            print()
        
        print(f"Q{question_count}: Are you thinking of {guess}?")
        correct = input("Enter 1 for YES, 0 for NO: ").strip()
        
        if correct == "1":
            print(f"\n✓ SUCCESS in {question_count} questions using letter-based detection!")
        else:
            print(f"\n✗ Wrong.")
            if len(candidates) <= 10:
                print(f"   It was one of: {', '.join(sorted(candidates))}")
            else:
                print(f"   Top 10 remaining: {', '.join(sorted(candidates)[:10])}")
    else:
        print("Error: No candidates remain!")
    
    return candidates


# Run the game
play_game(noun_data)