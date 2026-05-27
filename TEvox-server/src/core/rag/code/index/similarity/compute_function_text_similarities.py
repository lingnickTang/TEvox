import json
import re
import os
import sys
from collections import Counter
from math import log
import time
from tqdm import tqdm

# Add parent directory to sys.path to import config module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import load_config

def tokenize(text):
    """Simple tokenization function."""
    # Convert to lowercase and split by non-alphanumeric characters
    return re.findall(r'\w+', text.lower())

class BM25:
    """BM25 implementation for text matching."""
    
    def __init__(self, corpus, k1=1.5, b=0.75):
        """Initialize BM25 with corpus.
        
        Args:
            corpus: List of tokenized documents
            k1: Term frequency scaling parameter (default: 1.5)
            b: Length normalization parameter (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / self.corpus_size
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        
        # Calculate document lengths and document frequencies
        print("Processing document lengths and frequencies...")
        term_doc_freq = Counter()  # 用于跟踪每个词出现在多少个文档中
        
        for doc in tqdm(corpus):
            # 计算文档长度
            self.doc_len.append(len(doc))
            # 计算词频
            doc_counter = Counter(doc)
            self.doc_freqs.append(doc_counter)
            # 更新每个词的文档频率（一个词在文档中出现多次只计算一次）
            term_doc_freq.update(set(doc))
            
        # Calculate IDF values
        print("Calculating IDF values...")
        for term, doc_freq in term_doc_freq.items():
            self.idf[term] = log((self.corpus_size - doc_freq + 0.5) / (doc_freq + 0.5) + 1)
    
    def get_score(self, query, index):
        """Calculate BM25 score between query and document at given index."""
        score = 0
        doc = self.corpus[index]
        doc_len = self.doc_len[index]
        doc_freqs = self.doc_freqs[index]
        
        for term in query:
            if term not in doc:
                continue
                
            # Get term frequency in document
            freq = doc_freqs[term]
            
            if term in self.idf:
                # Calculate BM25 score for this term
                idf_val = self.idf[term]
                numerator = idf_val * freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += numerator / denominator
                
        return score
    
    def get_scores(self, query):
        """Calculate BM25 scores between query and all documents in corpus."""
        scores = []
        for i in range(self.corpus_size):
            scores.append(self.get_score(query, i))
        return scores

def process_function_name(function_name):
    """Process function name into query tokens.
    Split by underscores and camelCase, convert to lowercase.
    """
    tokens = []
    
    # Split by underscores first
    if '_' in function_name:
        parts = function_name.split('_')
        for part in parts:
            tokens.extend(tokenize(part))
    else:
        # Handle camelCase
        tokens = tokenize(function_name)
    
    # Add the original function name as a whole token
    if function_name.lower() not in tokens:
        tokens.append(function_name.lower())
    
    return tokens

def main(functions_file, text_content_file, output_file):
    
    # Read functions data from JSONL file
    print("Reading functions data...")
    functions_data = []
    try:
        with open(functions_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():  # Skip empty lines
                    functions_data.append(json.loads(line))
        print(f"Successfully read {len(functions_data)} functions.")
    except Exception as e:
        print(f"Error reading functions file: {e}")
        return
    
    # Read text unit content
    print("Reading text unit content...")
    try:
        with open(text_content_file, 'r', encoding='utf-8') as f:
            text_content_data = json.load(f)
            print(f"Successfully read {len(text_content_data)} text contents.")
    except Exception as e:
        print(f"Error reading text content file: {e}")
        return

    # Prepare corpus (only do this once)
    print("\nTokenizing documents...")
    tokenization_start_time = time.time()
    
    corpus = []
    text_ids = []
    
    for text_unit in text_content_data:
        tokens = tokenize(text_unit['content'])
        corpus.append(tokens)
        text_ids.append(text_unit['id'])
    
    tokenization_end_time = time.time()
    tokenization_time = tokenization_end_time - tokenization_start_time
    print(f"Tokenization time for {len(corpus)} documents: {tokenization_time:.2f} seconds")

    # Initialize BM25 (only do this once)
    print("\nInitializing BM25...")
    bm25_init_start_time = time.time()
    bm25 = BM25(corpus)
    bm25_init_end_time = time.time()
    print(f"BM25 initialization time: {bm25_init_end_time - bm25_init_start_time:.2f} seconds")

    # Process each function
    all_results = {}
    total_matching_time = 0
    k = 100  # top-k results to keep
    
    print(f"\nProcessing {len(functions_data)} functions...")
    for func in tqdm(functions_data):
        function_id = func['id']
        function_name = func['symbolName']
        
        # Process function name into query tokens
        query_tokens = process_function_name(function_name)
        
        # Compute matches
        matching_start_time = time.time()
        scores = bm25.get_scores(query_tokens)
        matching_end_time = time.time()
        matching_time = matching_end_time - matching_start_time
        total_matching_time += matching_time
        
        # Get top-k results
        scored_results = list(zip(scores, text_ids, range(len(scores))))
        scored_results.sort(reverse=True)
        
        # Store only text_unit_id and rank for top-k results
        function_results = []
        for rank, (score, text_id, _) in enumerate(scored_results[:k], 1):
            result = {
                'text_unit_id': text_id,
                'rank': rank
            }
            function_results.append(result)
        
        # Add to all results
        all_results[function_id] = {
            'function_name': function_name,
            'top_k_matches': function_results
        }
    
    # Prepare output data
    output_data = {
        'metadata': {
            'total_functions': len(functions_data),
            'total_documents': len(corpus),
            'top_k': k,
            'timing': {
                'tokenization': tokenization_time,
                'bm25_initialization': bm25_init_end_time - bm25_init_start_time,
                'total_matching': total_matching_time,
                'average_matching_per_function': total_matching_time / len(functions_data) if len(functions_data) > 0 else 0
            }
        },
        'results': all_results
    }
    
    # Save results
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\nSuccessfully saved all results to {output_file}")
        print(f"Total processing time: {tokenization_time + (bm25_init_end_time - bm25_init_start_time) + total_matching_time:.2f} seconds")
    except Exception as e:
        print(f"Error saving results: {e}")

if __name__ == "__main__":
    # Load config
    config = load_config()
    
    # Get paths from config
    functions_file = config['functionBodiesPath']
    text_content_file = config['baseTextUnitsPath']
    output_file = config['topKMatchesPath']
    
    # Run the main function
    main(functions_file, text_content_file, output_file) 