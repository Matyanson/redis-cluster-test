import os
import csv

# Define paths
source_dir = './data_full'
target_dir = './data_short'
max_lines = 5000

# Create target directory if it doesn't exist
os.makedirs(target_dir, exist_ok=True)

# Iterate over each file in the source directory
for filename in os.listdir(source_dir):
    if filename.endswith('.csv'):
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)
        
        with open(source_path, 'r', newline='', encoding='utf-8') as src_file:
            reader = csv.reader(src_file)
            rows = []
            for i, row in enumerate(reader):
                if i >= max_lines:
                    break
                rows.append(row)

        with open(target_path, 'w', newline='', encoding='utf-8') as tgt_file:
            writer = csv.writer(tgt_file)
            writer.writerows(rows)

print("Done copying first 5000 lines of each .csv file.")
