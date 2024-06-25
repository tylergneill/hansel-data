import json
import math
import os
import re
from collections import Counter

ABSOLUTE_PATH = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    'max_ngram_size': 2,  # unigrams and bigrams
    'reference_ngrams_filepath': os.path.join(ABSOLUTE_PATH, 'reference_ngrams.json'),
    'unfamiliar_ngrams_default_filepath': 'tmp/unfamiliar_ngrams.txt',
    'bracketless_content_default_filepath': 'tmp/bracketless_content.txt',
    'long_sequence_threshold': 128,
    'residuals_ranking_k': 10,
    'residual_threshold': 100,
}

def remove_bracket_groups(content, bracket_group_pattern):
    """
    returns
        1) content without named bracket group
        2) errors
    """
    errors = []
    while True:
        hits = re.findall(bracket_group_pattern, content)
        if not hits:
            break
        for hit in hits:
            # Report illegally nested brackets within hit bracket group
            if re.search(r'[\[\]\{\}]', hit):
                errors.append(f"Invalid nesting within group {hit}")
            content = content.replace(hit, '')
    return content, errors
    

def remove_removables(file_content):
    # Patterns for (valid sets of) removable brackets
    patterns = [
        r'\([^()\[\]\{\}<>]*\)',
        r'<[^<>\[\]\{\}()]*>',
        r'\[[^\[\]\{\}<>]*\]',
        r'\{[^\[\]\{\}<>]*\}'
    ]
    
    # Remove all removable brackets
    for pattern in patterns:
        while re.search(pattern, file_content):
            file_content = re.sub(pattern, '', file_content)
    
    return file_content


def keep_keepables(file_content):
    # Pattern for (valid sets of) brackets with keepable content
    pattern = r'〈(.*?)〉'

    # Keep that content
    return re.sub(pattern, r'\1', file_content)
    

def clean_up_whitespace(content):
    # Define the regex replacements for cleaning up whitespace
    regex_replacements = [
        [r'\t{2,}', r'\t'],       # multiple tab
        [r' *(\n+) *', r'\1'],    # extraneous space adjacent to newline
        [r'\n{2,}', r'\n\n'],     # extraneous newline (max 2)
        [r' {2,}', r' '],         # duplicate space
        [r'\A\s*', r''],          # file-initial whitespace
        [r'\s*\Z', r'']           # file-final whitespace
    ]
    
    # Apply the regex replacements
    for pattern, replacement in regex_replacements:
        content = re.sub(pattern, replacement, content)
    
    return content


def get_ngrams(content, n):
    return [content[i:i+n] for i in range(len(content)-n+1)]


def calculate_new_ngram_counts(content, n):
    ngrams = get_ngrams(content, n)
    return Counter(ngrams)


def load_ngram_counts(json_file, max_n):
    try:
        with open(json_file, 'r') as file:
            ngram_counts = json.load(file)
    except FileNotFoundError:
        ngram_counts = {str(i): {} for i in range(1, max_n+1)}
    return ngram_counts


def upsert_ngram_counts(ngram_counts, new_counts, n):

    # dict for n will be mutated in-place
    ngram_dict = ngram_counts.get(str(n), {})

    for ngram, count in new_counts.items():
        if ngram in ngram_dict:
            ngram_dict[ngram] += count
        else:
            ngram_dict[ngram] = count

    # replace with sorted dict
    ngram_counts[str(n)] = dict(sorted(ngram_dict.items(), key=lambda x: x[1], reverse=True))

    return ngram_counts


def save_ngram_counts(ngram_counts, json_file, max_n):
    with open(json_file, 'w') as file:
        json.dump(ngram_counts, file, indent=4, ensure_ascii=False)


def calculate_standardized_residuals(ref_counts, new_ngram_counts, n):

    # Prepare reference data
    total_ref_ngrams = sum(ref_counts[str(n)].values())
    ref_prob = {ngram: count / total_ref_ngrams for ngram, count in ref_counts[str(n)].items()}

    # Prepare new data
    total_new_ngrams = sum(new_ngram_counts.values())    
    
    # Calculate standardized residuals
    residuals = {}
    for ngram in ref_prob:
        expected_count = ref_prob[ngram] * total_new_ngrams
        observed_count = new_ngram_counts.get(ngram, 0)
        if expected_count > 0:
            residual = (observed_count - expected_count) / math.sqrt(expected_count)
            residuals[ngram] = residual

    return residuals
