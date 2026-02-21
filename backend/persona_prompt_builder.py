import json

def generate_persona_prompt(person_data):
    """
    Converts a single person's JSON data into a descriptive prompt.
    Recursively handles nested dictionaries and lists.
    """
    sentences = []

    # Helper function to format keys (camelCase -> Normal Text)
    def clean_key(k):
        # Insert space before capitals: "jobTitle" -> "job Title"
        k = ''.join([' ' + c if c.isupper() else c for c in k]).strip()
        return k.replace("_", " ").title()

    # Recursive function to parse values
    def parse_value(key, val):
        if val is None or val == "":
            return None
        
        clean_k = clean_key(key)
        
        if isinstance(val, dict):
            # For nested objects (e.g., "professional"), drill down
            sub_sentences = []
            for sub_k, sub_v in val.items():
                res = parse_value(sub_k, sub_v)
                if res:
                    sub_sentences.append(res)
            return " ".join(sub_sentences)
            
        elif isinstance(val, list):
            # For lists (e.g., "skills"), join with commas
            items = ", ".join([str(i) for i in val if i])
            return f"Your {clean_k} are {items}."
            
        else:
            # For simple values (strings/numbers)
            return f"Your {clean_k} is {val}."

    # Main extraction loop
    # 1. Extract Name first for a strong start (if available)
    name = person_data.get("profile", {}).get("fullName") or person_data.get("name")
    if name:
        sentences.append(f"You are {name}.")

    # 2. Loop through all keys
    for key, value in person_data.items():
        # Skip metadata or already used keys
        if key in ["timestamp", "profilePhoto", "id"]: 
            continue
            
        # Parse the value (handles dicts, lists, and strings)
        description = parse_value(key, value)
        if description:
            sentences.append(description)

    return " ".join(sentences)

# --- Usage Example ---
# Load your JSON file

# person_name = "Kanishkha_S"
# person_name = "Anagha_Palandye"
person_name = "Nirbhay_R"
# person_name = "Gaurav_Atavale"

with open(f"{person_name}.json", "r", encoding="utf-8") as f:
    people_list = json.load(f)

# Generate prompt for the first person
prompt = generate_persona_prompt(people_list[0])

with open(f"{person_name}_persona_prompt.txt", "a", encoding="utf-8") as f:
    f.write(prompt)

# print(prompt)