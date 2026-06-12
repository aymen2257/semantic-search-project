import json
import itertools

def open_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except json.JSONDecodeError:
        print("Error: Failed to decode JSON from the file.")
    except FileNotFoundError:
        print("Error: File not found.")

list_pers_en = open_json_file('crawled_urls_personal_en.json')
list_pers_fr = open_json_file('crawled_urls_personal_fr.json')
list_bs_en = open_json_file('crawled_urls_business_en.json')
list_bs_fr = open_json_file('crawled_urls_business_fr.json')

it= itertools.chain(list_pers_en,list_pers_fr,list_bs_en,list_bs_fr)
list_final=list(it)
print (len(list_final))

with open('urls_final.json', 'w') as f:
    json.dump(list_final, f, indent=4)
