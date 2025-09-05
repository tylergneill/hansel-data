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


def validate_structure(structured_content, options):
    
    valid = True
    errors = []

    # Step 1: Remove innermost valid closed sets of notes (...) and <...>
    
    paren_pattern = r'\([^()\[\]\{\}<>]*\)'
    angle_pattern = r'<[^<>\[\]\{\}()]*>'

    for pattern in [paren_pattern, angle_pattern]:
        structured_content, new_errors = remove_bracket_groups(structured_content, pattern)
        if new_errors:
            valid = False
            errors.extend(new_errors)    

    # Step 2: Find all valid closed sets of identifiers [...] and {...}

    document_identifiers = re.findall(r'\[.*?\]', structured_content)
    group_identifiers = re.findall(r'\{.*?\}', structured_content)
    
    # Step 3: Ensure there is at least one of each type
    
    if not document_identifiers:
        valid = False
        errors.append("No document identifier ([...]) found.")
    
    if not group_identifiers:
        valid = False
        errors.append("No group identifier ({...}) found.")
    
    # Step 4a: Ensure each [...] contains some text and no {}
    
    for doc_id in document_identifiers:
        if not re.search(r'\[.+\]', doc_id):
            valid = False
            errors.append(f"Empty document identifier found: {doc_id}")
        if re.search(r'\{.*\}', doc_id):
            valid = False
            errors.append("Invalid brackets {}"f"found within document identifier: {doc_id}")

    # Step 4b: Ensure each {...} contains some text and no []
    
    for group_id in group_identifiers:
        if not re.search(r'\{.+\}', group_id):
            valid = False
            errors.append(f"Empty document group identifier found: {group_id}")
        if re.search(r'\[.*\]', group_id):
            valid = False
            errors.append(f"Invalid brackets [] found within document group identifier: {group_id}")

    return valid, errors


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
                errors.append(f"N-gram {repr(ngram)} (count {new_ngram_counts[ngram]}) is unfamiliar")
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
        structure_valid, structure_errors = validate_structure(raw_input_text, options)
        structure_errors_str = '\n'.join([f"\t{e}" for e in structure_errors])
        if not structure_valid:
            print(f"Structure of file {filename} not valid:\n{structure_errors_str}")
            exit(1)
    
    if args.content_validation:
        content_valid, content_errors = validate_content(raw_input_text, options)
        content_errors_str = '\n'.join([f"\t{e}" for e in content_errors])
        if not content_valid:
            print(f"Content of file {filename} not valid:\n{content_errors_str}")
            if not options["allow_content_fail"]:
                exit(1)

    print(f"File {filename} validated successfully.")
    exit(0)
