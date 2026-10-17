"""Reproduce Section 121 validation and evaluation counts from the two Excel files.

Usage: python reproduce_results.py
Dependency: pip install openpyxl
Place the workbooks beside this script, or in a Results/ subdirectory.
"""

from pathlib import Path
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parent


def rows(filename, id_column):
    path = ROOT / filename
    if not path.exists():
        path = ROOT / 'Results' / filename
    if not path.exists():
        raise FileNotFoundError(f'Workbook not found: {filename}')

    sheet = load_workbook(path, read_only=True, data_only=True).active
    values = sheet.iter_rows(values_only=True)
    headers = next(values)
    return [dict(zip(headers, cells)) for cells in values
            if dict(zip(headers, cells)).get(id_column)]


def yes(row, column):
    return str(row[column]).strip().lower() == 'yes'


def show(label, count, total):
    print(f'  {label:<40} {count:>3} / {total}  ({count / total:.2%})')


def main():
    validation = rows('Section_121_Accuracy_Validation_Cases.xlsx', 'ValidationID')
    print('Section 4.2 — Validation cases')
    show('Correct', sum(yes(r, 'Correct') for r in validation), len(validation))

    runs = rows('Section_121_Final_Evaluation_Cases.xlsx', 'EvaluationID')
    total = len(runs)
    correct = lambda r: yes(r, 'Correct')
    ttl = lambda r: yes(r, 'Proper Ontology Construction')
    shacl = lambda r: yes(r, 'Initial SHACL Errors')
    prompted = lambda r: yes(r, 'Additional Prompting')

    overall = sum(correct(r) for r in runs)
    first_pass = sum(ttl(r) and correct(r) and not shacl(r) and not prompted(r)
                     for r in runs)
    shacl_fixed = sum(shacl(r) and prompted(r) and correct(r) for r in runs)
    clarified = sum(prompted(r) for r in runs)
    clarified_correct = sum(prompted(r) and correct(r) for r in runs)
    failures = [r['EvaluationID'] for r in runs if not correct(r) and not ttl(r)]

    print('\nSection 4.3 — Final evaluation cases (Table 2)')
    show('Overall correctness', overall, total)
    show('First-pass accuracy', first_pass, total)
    show('Initial SHACL violations', sum(shacl(r) for r in runs), total)
    show('Cases requiring factual clarification', clarified, total)

    print('\nSection 4.3 — Outcome breakdown (Table 3)')
    show('Correct without human interaction', first_pass, total)
    show('Corrected with SHACL loop', shacl_fixed, total)
    show('Correct requiring factual clarification', clarified_correct, total)
    show('Failures', len(failures), total)
    print('  Failed run IDs:', ', '.join(failures))
    print('  Clarification and failure overlap:',
          sum(prompted(r) and not correct(r) and not ttl(r) for r in runs))
    print('  Table 3 totals:', first_pass + shacl_fixed + clarified_correct + len(failures), '/', total)


if __name__ == '__main__':
    main()