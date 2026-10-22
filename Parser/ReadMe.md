# Cowrie Log to CSV

Run these commands in a terminal from this project folder. Replace the example paths with your file or folder paths.

## Process one file

```terminal
python .\cowrie_to_csv.py "C:\path\to\cowrie.json"
```

## Process a whole folder

```terminal
python .\cowrie_to_csv.py "C:\path\to\logs" -o ".\combined_results"
```

For a folder, the script processes `.json` and `.ndjson` files in that folder and its subfolders, combining them into one set of reports.

The reports are saved in `cowrie_analysis_output` by default, or in the folder given with `-o`. The input files must use newline-delimited JSON: one JSON object per line.