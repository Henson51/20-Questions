import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import json
from typing import List, Dict
from pathlib import Path
from collections import defaultdict

class NounCategorizer:
    def __init__(self, model_name="microsoft/Phi-3-mini-4k-instruct", device="mps"):
        """Initialize the model and tokenizer."""
        print("Loading model and tokenizer...")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map=device,
            torch_dtype="auto",
            trust_remote_code=False,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.device = device
        print("Model loaded successfully!")
    
    def generate_response(self, prompt: str, max_new_tokens: int = 1000, temperature: float = 0.7, system_message: str = None) -> str:
        """Generate a response from the model."""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": prompt})
        
        # Format the prompt using the chat template
        input_text = self.tokenizer.apply_chat_template(
            messages, 
            tokenize=False, 
            add_generation_prompt=True
        )
        
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            # Use greedy decoding for very low temperatures to avoid numerical instability
            if temperature < 0.5:
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,  # Greedy decoding for stability
                    repetition_penalty=1.1,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            else:
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    do_sample=True,
                    top_p=0.9,
                    repetition_penalty=1.1,
                    pad_token_id=self.tokenizer.eos_token_id
                )
        
        # Decode only the generated tokens (excluding the prompt)
        generated_text = self.tokenizer.decode(
            outputs[0][inputs['input_ids'].shape[1]:], 
            skip_special_tokens=True
        )
        
        return generated_text.strip()
    
    def categorize_nouns(self, nouns: List[str], categories: List[str], batch_size: int = 25) -> Dict[str, List[str]]:
        """
        Assign each noun to a predefined category.
        Processes nouns in batches due to context length limits.
        
        Args:
            nouns: List of nouns to categorize
            categories: List of predefined category names
            batch_size: Number of nouns to process per batch (default: 25, optimized for Phi-3)
        
        Returns:
            Dictionary mapping category names to lists of nouns
        
        Note:
            Uses temperature=0.3 for optimal balance between consistency and numerical stability.
            Lower temperatures (< 0.3) can cause RuntimeError with probability tensors.
        """
        print(f"\nCategorizing {len(nouns)} nouns into {len(categories)} predefined categories...")
        print(f"Processing in batches of {batch_size}...\n")
        
        categorized = {cat: [] for cat in categories}
        uncategorized = []
        
        system_message = "You are a classification expert. Categorize each noun accurately."
        
        total_batches = (len(nouns) - 1) // batch_size + 1
        
        for i in range(0, len(nouns), batch_size):
            batch = nouns[i:i+batch_size]
            batch_num = i // batch_size + 1
            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} nouns)...")
            
            # Create category list with relevant examples
            category_examples = {
                "Abstract Concepts, Places, People & Activities": "teacher, democracy, Chicago",
                "Aircraft": "airplane, helicopter, jet",
                "Birds, Fish, Insects & Other Animals": "eagle, salmon, butterfly",
                "Buildings & Large Structures": "skyscraper, bridge, stadium",
                "Cars, Trucks, Boats & Other Motorized Vehicles": "sedan, pickup truck, yacht",
                "Domesticated Mammals": "dog, cat, horse",
                "Fruits": "apple, banana, orange",
                "Geological Features & Minerals": "mountain, quartz, granite",
                "Handheld Objects & Tools": "hammer, phone, wrench",
                "Motorcycles": "harley, ducati, sportbike",
                "Natural Non-Geological Features": "ocean, cloud, river",
                "Non-Motorized Transportation": "bicycle, skateboard, canoe",
                "Non-Tree Plants": "grass, fern, rose",
                "Other Raw Foods": "beef, egg, milk",
                "Prepared Foods & Meals": "pizza, sandwich, soup",
                "Reptiles & Amphibians": "snake, lizard, frog",
                "Transportation Infrastructure": "highway, airport, bridge",
                "Trees": "oak, pine, maple",
                "Wild Mammals": "lion, elephant, wolf",
                "other": "things that don't fit above"
            }
            
            # Create concise category list
            category_list = '\n'.join(f'{idx+1}. {cat}' for idx, cat in enumerate(categories))
            
            prompt = f"""Categorize nouns into the correct category.

CATEGORIES:
{category_list}

NOUNS:
{', '.join(batch)}

RULES:
1. Match each noun to ONE category
2. Use exact category names from list
3. Consider primary meaning only
4. If unsure, use "other"

FORMAT: noun|Category Name

EXAMPLES:
apple|Fruits
lion|Wild Mammals
bicycle|Non-Motorized Transportation
teacher|Abstract Concepts, Places, People & Activities
unknown_term|other

OUTPUT ({len(batch)} assignments):"""

            response = self.generate_response(
                prompt, 
                max_new_tokens=800,
                temperature=0.3,  # Optimal balance: stable and consistent
                system_message=system_message
            )
            
            # Parse assignments
            assigned_in_batch = 0
            batch_lower = [n.lower() for n in batch]  # Create lowercase lookup once
            
            for line in response.split('\n'):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('//'):
                    continue
                    
                if '|' in line:
                    parts = line.split('|', 1)  # Split on first | only
                    if len(parts) == 2:
                        noun = parts[0].strip().lower()
                        category = parts[1].strip()
                        
                        # Check if this noun is in the current batch
                        if noun in batch_lower:
                            # Find matching category (case-insensitive)
                            matched_category = None
                            for cat in categories:
                                if cat.lower() == category.lower():
                                    matched_category = cat
                                    break
                            
                            # If no exact match, try partial matching for common mistakes
                            if not matched_category:
                                for cat in categories:
                                    # Handle common truncations or typos
                                    if category.lower() in cat.lower() or cat.lower() in category.lower():
                                        matched_category = cat
                                        break
                            
                            if matched_category:
                                # Find original noun (with correct capitalization)
                                original_noun = batch[batch_lower.index(noun)]
                                
                                if original_noun not in categorized[matched_category]:
                                    categorized[matched_category].append(original_noun)
                                    assigned_in_batch += 1
                            else:
                                # Category not found - add to "other"
                                original_noun = batch[batch_lower.index(noun)]
                                if 'other' in categories and original_noun not in categorized['other']:
                                    categorized['other'].append(original_noun)
                                    assigned_in_batch += 1
            
            print(f"  ✓ Successfully categorized {assigned_in_batch}/{len(batch)} nouns")
            
            # Track any nouns that weren't assigned in this batch
            for noun in batch:
                assigned = False
                for cat_list in categorized.values():
                    if noun in cat_list:
                        assigned = True
                        break
                if not assigned:
                    uncategorized.append(noun)
        
        # Automatically assign any uncategorized nouns to "other"
        if uncategorized:
            print(f"\n⚠ Warning: {len(uncategorized)} nouns were not categorized in batches.")
            print(f"  Automatically assigning them to 'other' category...")
            
            if 'other' in categorized:
                for noun in uncategorized:
                    if noun not in categorized['other']:
                        categorized['other'].append(noun)
                print(f"  ✓ Added {len(uncategorized)} nouns to 'other' category")
            else:
                print(f"  ⚠ ERROR: 'other' category not found in category list!")
                print(f"  The following nouns remain uncategorized:")
                print(f"  {', '.join(uncategorized[:20])}" + ("..." if len(uncategorized) > 20 else ""))
        
        return categorized
    
    def save_results(self, categorized: Dict[str, List[str]], output_file: str = "categorized_nouns.json"):
        """Save categorization results to JSON file."""
        # Calculate statistics
        stats = {
            'total_categories': len(categorized),
            'total_nouns_categorized': sum(len(nouns) for nouns in categorized.values()),
            'category_distribution': {cat: len(nouns) for cat, nouns in categorized.items()},
            'empty_categories': [cat for cat, nouns in categorized.items() if len(nouns) == 0]
        }
        
        output_data = {
            'categories': categorized,
            'statistics': stats
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Results saved to '{output_file}'")
        return stats
    
    def print_summary(self, categorized: Dict[str, List[str]]):
        """Print a summary of the categorization results."""
        print("\n" + "="*70)
        print("CATEGORIZATION SUMMARY")
        print("="*70)
        
        total_nouns = sum(len(nouns) for nouns in categorized.values())
        print(f"Total nouns categorized: {total_nouns}")
        print(f"Total categories: {len(categorized)}")
        print(f"\nDistribution:")
        print("-" * 70)
        
        # Sort categories by number of nouns (descending)
        sorted_cats = sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True)
        
        for category, nouns in sorted_cats:
            count = len(nouns)
            if count > 0:
                # Show first few examples
                examples = ', '.join(nouns[:3])
                if len(nouns) > 3:
                    examples += '...'
                print(f"{category:45} {count:4} nouns  (e.g., {examples})")
            else:
                print(f"{category:45} {count:4} nouns")
        
        print("="*70)


def load_nouns_from_file(filepath: str) -> List[str]:
    """Load nouns from a text file, one noun per line."""
    print(f"Loading nouns from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        nouns = [line.strip() for line in f if line.strip()]
    print(f"✓ Loaded {len(nouns)} nouns")
    return nouns


def load_categories_from_file(filepath: str) -> List[str]:
    """Load category names from a text file, one category per line."""
    print(f"Loading categories from {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        categories = [line.strip() for line in f if line.strip()]
    print(f"✓ Loaded {len(categories)} categories")
    return categories


def main():
    # File paths
    nouns_file = "nouns.txt"
    #categories_file = "sorted_category_names.txt"
    categories_file = "categories.txt"
    output_file = "categorized_nouns.json"
    
    # Load data
    nouns = load_nouns_from_file(nouns_file)
    categories = load_categories_from_file(categories_file)
    
    print(f"\nCategories to use:")
    for i, cat in enumerate(categories, 1):
        print(f"  {i}. {cat}")
    
    # Initialize the categorizer
    categorizer = NounCategorizer(device="mps")  # Change to "cuda" or "cpu" as needed
    
    # Categorize all nouns (batch_size=25 is optimized for Phi-3)
    categorized_nouns = categorizer.categorize_nouns(nouns, categories)
    
    # Print summary
    categorizer.print_summary(categorized_nouns)
    
    # Save results
    stats = categorizer.save_results(categorized_nouns, output_file)
    
    # Additional statistics
    empty_cats = stats['empty_categories']
    if empty_cats:
        print(f"\n⚠ Note: {len(empty_cats)} categories have no nouns assigned:")
        for cat in empty_cats:
            print(f"  - {cat}")


if __name__ == "__main__":
    main()
