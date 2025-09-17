import argparse
import os
import re

from utils import (
    remove_bracket_groups,
    remove_removables,
    keep_keepables,
    clean_up_whitespace,
    load_ngram_counts,
    save_ngram_counts,
    calculate_new_ngram_counts,
    calculate_standardized_residuals,
    upsert_ngram_counts,
    CONFIG,
)


def validate_structure(structured_content):
    """
    Validates the bracket structure of the input content against a set of rules.

    This function performs two main types of checks:
    1. Non-Destructive Structural Checks: It first validates the nesting of different
       bracket types on the original, unmodified content. This ensures that the
       hierarchical structure is correct.
    2. Content and Existence Checks: It then checks for the existence of mandatory
       identifiers and ensures they are not empty.

    Rules enforced:
    - ERRORS (will cause validation to fail):
      - At least one document identifier `[...]` must exist.
      - At least one group identifier `{...}` must exist.
      - `[...]` and `{...}` must not be empty or contain only whitespace.
      - `[...]` must not contain `{...}` or `<...>`. 
      - `{...}` must not contain `[...]` or `<...>`. 
      - `<...>` must not contain `[...]` or `{...}`.
    - WARNINGS (will be flagged but will not cause failure):
      - `(...)` should not contain any other bracket characters.

    The function is designed to be non-destructive for structural checks, avoiding
    the issues of prematurely removing parts of the string before validation is complete.

    Args:
        structured_content (str): The string content to validate.

    Returns:
        tuple[bool, list[str], list[str]]: A tuple containing:
            - valid (bool): False if any errors were found, True otherwise.
            - errors (list[str]): A list of error messages.
            - warnings (list[str]): A list of warning messages.
    """
    valid = True
    errors = []
    warnings = []
    
    # Part A: Non-Destructive Structural Checks
    
    # 1. Find all instances of each bracket type
    all_squares = re.findall(r'\[.*?\]', structured_content, re.DOTALL)
    all_curlies = re.findall(r'\{.*?\}', structured_content, re.DOTALL)
    all_angles = re.findall(r'<.*?>', structured_content, re.DOTALL)
    all_rounds = re.findall(r'\(.*?\)', structured_content, re.DOTALL)
    
    # 2. Perform Nesting Validation
    
    # Check [...]
    for s in all_squares:
        inner = s[1:-1]
        if any(c in inner for c in '{}<>'):
            valid = False
            errors.append(f"Invalid brackets {{}}, <> found within document identifier: {s}")

    # Check {...}
    for c in all_curlies:
        inner = c[1:-1]
        if any(c in inner for c in '[]<>'):
            valid = False
            errors.append(f"Invalid brackets [], <> found within group identifier: {c}")

    # Check <...>
    for a in all_angles:
        inner = a[1:-1]
        if any(c in inner for c in '[]{}'):
            valid = False
            errors.append(f"Invalid brackets [], {{}} found within note: {a}")

    # Check (...)
    for r in all_rounds:
        inner = r[1:-1]
        if any(c in inner for c in '()[]{}<>'):
            warnings.append(f"Round brackets contain brackets: {r}")

    # Part B: Content and Existence Checks
    
    # 1. Existence Check
    if not all_squares:
        valid = False
        errors.append("No document identifier ([...]) found.")
    
    if not all_curlies:
        valid = False
        errors.append("No group identifier ({...}) found.")
        
    # 2. Emptiness Check
    for s in all_squares:
        if not s[1:-1].strip():
            valid = False
            errors.append(f"Empty document identifier found: {s}")
            
    for c in all_curlies:
        if not c[1:-1].strip():
            valid = False
            errors.append(f"Empty document group identifier found: {c}")

    return valid, errors, warnings


def validate_content(structured_content, options):

    valid = True
    errors = []
    unfamiliar_ngrams = []

    # Step 1: Remove all structural elements

    unstructured_content = remove_removables(structured_content)
    unstructured_content = keep_keepables(unstructured_content)
    unstructured_content = clean_up_whitespace(unstructured_content)

    # Optionally: Output the bracketless content undergoing n-gram validation

    if options['output_bracketless']:
        with open(CONFIG['bracketless_content_default_filepath'], 'w') as f_out:
            f_out.write(unstructured_content)
    
    # Step 2: Load reference n-gram counts from JSON file

    ref_ngram_counts = load_ngram_counts(
        CONFIG['reference_ngrams_filepath'],
        CONFIG['max_ngram_size'],
    )

    # Step 3: Check new n-grams against reference set

    for n in range(1, CONFIG['max_ngram_size']+1):
        
        # Calculate new n-gram counts
        new_ngram_counts = calculate_new_ngram_counts(unstructured_content, n)
        sorted_ngram_counts = dict(sorted(new_ngram_counts.items(), key=lambda x: x[1], reverse=True))

        # Check for unfamiliar n-grams never recorded before
        # (These DO count as validation errors)

        for ngram in sorted_ngram_counts:
            if ngram not in ref_ngram_counts[str(n)]:
                valid = False
                errors.append(f"N-gram {repr(ngram)} ({','.join([str(hex(ord(c))) for c in ngram])}) (count {new_ngram_counts[ngram]}) is unfamiliar")
                unfamiliar_ngrams.append(f"{new_ngram_counts[ngram]}\t{repr(ngram)}")

        # Optionally: Output unfamiliar n-gram data for inspection

        if options['output_unfamiliar_ngrams']:
            unfamiliar_ngrams_filepath = (
                options['unfamiliar_ngrams_filepath']
                or CONFIG['unfamiliar_ngrams_default_filepath']
            )
            with open(unfamiliar_ngrams_filepath, 'w') as f:
                f.write(
                    '\n'.join(unfamiliar_ngrams)
                )
        
        # Use standardized residuals to highlight out-of-distribution n-grams
        # (These do NOT count as validation errors)

        standardized_residuals = calculate_standardized_residuals(ref_ngram_counts, new_ngram_counts, n)
        ranked_ngrams = dict(sorted(standardized_residuals.items(), key=lambda item: abs(item[1]), reverse=True))
        for ngram, residual in list(ranked_ngrams.items())[:CONFIG['residuals_ranking_k']]:
            if residual > CONFIG['residual_threshold']:
                print(f"N-gram {repr(ngram)} residual {residual:0.1f} exceeds threshold ({CONFIG['residual_threshold']})")

        # Optionally: Add all new n-gram counts to reference set
        # (Do this ONLY AFTER addressing unfamiliar and out-of-distribution n-grams!)

        if options['update_ngrams']:
            updated_ref_ngram_counts = upsert_ngram_counts(ref_ngram_counts, new_ngram_counts, n)
            save_ngram_counts(
                updated_ref_ngram_counts,
                CONFIG['reference_ngrams_filepath'],
                # CONFIG['max_ngram_size'], # TODO: use later
            )

    return valid, errors


if __name__ == '__main__':

    # Load CL arguments

    parser = argparse.ArgumentParser()

    # input argument
    parser.add_argument("-i", "--input-filepath", help="path to input file", required=True)

    # mode arguments (exactly one out of two required)
    parser.add_argument("-s", "--structure-validation", help="validate bracket annotation structure", action="store_true")
    parser.add_argument("-c", "--content-validation", help="validate n-gram counts", action="store_true")

    # more options
    parser.add_argument("-v", "--verbose", help="make validation more verbose (both structure and content)", action="store_true")
    parser.add_argument("--output-bracketless", help="optional output to accompany verbose content validation", action="store_true")
    parser.add_argument("--bracketless-content-filepath", help="where to save optional bracketless content output", required=False)
    parser.add_argument("--pause", help="extra option for verbose structure validation", action="store_true")
    parser.add_argument("--output-unfamiliar-ngrams", help="optional output to help address unfamiliar n-grams", action="store_true")
    parser.add_argument("--unfamiliar-ngrams-filepath", help="where to save optional unfamiliar n-gram output", required=False)
    # parser.add_argument("--flag-long-sequences", help="flag char sequences longer than threshold", action="store_true")
    parser.add_argument("-u", "--update-ngrams", help="option to accept all remaining flagged n-grams and add to json", action="store_true")
    parser.add_argument("--allow-content-fail", help="don't propogate failure signal if content check fails", action="store_true")

    args = parser.parse_args()
    
    options = {
        'verbose': args.verbose,
        'output_bracketless': args.output_bracketless,
        'bracketless_content_filepath': args.bracketless_content_filepath,
        'pause': args.pause,
        'output_unfamiliar_ngrams': args.output_unfamiliar_ngrams,
        'unfamiliar_ngrams_filepath': args.unfamiliar_ngrams_filepath,
#         'flagged_ngrams_filepath': args.flagged_ngrams_filepath,
        'update_ngrams': args.update_ngrams,
        'allow_content_fail': args.allow_content_fail,
    }

    # Validate CL arguments
    
    if not args.input_filepath:
        print("Input argument needed '-i'/'--input-filepath'")
        exit(1)

    if not (args.structure_validation or args.content_validation):
        print("Mode argument needed: '-s'/'--structure-validation' or '-c'/'--content-validation'")
        exit(1)

    # Load text

    with open(args.input_filepath, 'r') as f_in:
        raw_input_text = f_in.read()    

    filename = os.path.basename(args.input_filepath)

    # Perform validation

    if args.structure_validation:
        structure_valid, structure_errors, structure_warnings = validate_structure(raw_input_text)
        
        if structure_warnings:
            structure_warnings_str = '\n'.join([f"\tWarning: {w}" for w in structure_warnings])
            print(f"Structure of file {filename} has warnings:\n{structure_warnings_str}")

        if not structure_valid:
            structure_errors_str = '\n'.join([f"\t{e}" for e in structure_errors])
            print(f"Structure of file {filename} not valid:\n{structure_errors_str}")
            exit(1)
    
    if args.content_validation:
        content_valid, content_errors = validate_content(raw_input_text, options)
        content_errors_str = '\n'.join([f"\t{e}" for e in content_errors])
        if not content_valid:
            print(f"Content of file {filename} has the following issues:\n{content_errors_str}")
            if not options["allow_content_fail"]:
                print(f"File {filename} failed content validation.")
                exit(1)

    print(f"File {filename} validated successfully.")
    exit(0)