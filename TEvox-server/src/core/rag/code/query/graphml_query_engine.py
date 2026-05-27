from typing import List, Dict
import os
import json
import networkx as nx   
import time

from src.core.rag.doc.model import TextUnit
from src.core.rag.doc.query.nx_query_engine import NxQueryEngine
from src.utils import get_llm, Agent

select_code_functions_prompt = """To efficiently complete the current task `{question}`, you have retrieved the following code functions:

{context}

Please select the code functions that are helpful to complete the task. For each selected code function, provide the index number. Finally, output in JSON format with the code block:
```json
[
    "Only output the index numbers of the selected code functions."
]
```"""

def select_code_functions(**kwargs):
    return Agent(llm=get_llm()).invoke_with_structured_output(
        select_code_functions_prompt.format(**kwargs),
    )

class GraphMLQueryEngine(NxQueryEngine):
    def __init__(self, config: dict):
        super().__init__(config)
    
    def query_with_related_functions(self, question, text_units, rank_threshold=1, function_limit=10, select=False):
        """
        Query the database with related function bodies.
        
        1. Get text units from the query
        2. Extract text unit IDs
        3. Find related function IDs from the graph file
        4. Get function bodies from the functions file
        5. Generate a response using LLM with text units and function bodies as context
        
        Args:
            question: User's query
            text_units: List of text units to use as context
            rank_threshold: Threshold for ranking in function selection
            function_limit: Maximum number of functions to include
            select: Whether to use LLM to filter code functions
            
        Returns:
            Response from LLM
        """
        # 2. Extract text unit IDs
        text_unit_ids = [unit.id for unit in text_units]
        # 3. Load the graph and find related function IDs
        root_path = self.config.get("root_path")
        graph_path = os.path.join(root_path, "output/nxgraph_txt_with_code.graphml")
        G = nx.read_graphml(graph_path)
        
        related_function_ids = []
        for text_id in text_unit_ids:
            # Convert text_id to the format used in the graph
            graph_text_id = f"(('text_unit_id', '{text_id}'), ('type', 'text_unit'))"
            if graph_text_id in G:
                # Get neighbors that have edges to this text unit
                for neighbor in G.neighbors(graph_text_id):
                    # Check if the neighbor is a function node
                    if "('type', 'function')" in neighbor:
                        # Extract the function_id from the node string
                        function_id = neighbor.split("'function_id', '")[1].split("'")[0]
                        # Get the edge data which represents the ranking
                        edge_data = G.get_edge_data(graph_text_id, neighbor)
                        # The edge data contains a 'relation' key with the rank value
                        rank = int(edge_data.get('relation', 0))  # Default to 0 if not found
                        # Store function_id if it meets the rank threshold
                        if function_id not in related_function_ids:
                            if rank <= rank_threshold and rank > 0:
                                related_function_ids.append(function_id)
        if len(related_function_ids) >= function_limit:
            related_function_ids = related_function_ids[:function_limit]
        
        # 4. Get function bodies from the functions file
        function_bodies, symbol_names = [], []
        functions_file_path = os.path.join(root_path, "output/functions_bodys.jsonl")
        # Read the JSONL file and extract function bodies
        if os.path.exists(functions_file_path):
            with open(functions_file_path, 'r') as f:
                for line in f:
                    data = json.loads(line)
                    if data.get('id') in related_function_ids:
                        function_bodies.append(data.get('functionBody', ''))
                        symbol_names.append(data.get('symbolName', ''))
        
        if select:
            functions = []
            symbols = []
            for i in select_code_functions(
                question=question, context=self._format_function_bodies(function_bodies, symbol_names)
            ):
                if int(i) > len(function_bodies) or int(i) < 0:
                    continue
                functions.append(function_bodies[int(i)])
                symbols.append(symbol_names[int(i)])
            function_bodies = functions
            symbol_names = symbols
            
        # 5. Create a system prompt and generate a response
        system_prompt = f"""You are an expert assistant that provides accurate and helpful information.
Please directly answer the user's question based on the provided context.

requirements:
1. The answer should be written in markdown format.
2. Each information you described can find the basis in Context, and you cannot fabricate.

The context includes two types of information:
1. Text units: These are documentation fragments that provide information about the topic.
2. Function implementations: These are code snippets that show how the functionality is implemented.

Question: {question}

Text Units:
{self.format_context(text_units)}

Related Function Implementations:
{self._format_function_bodies(function_bodies, symbol_names)}

Provide a comprehensive answer that combines information from both the text units and function implementations.
"""
        
        # Call LLM with the combined context
        response = Agent(llm=get_llm()).invoke(system_prompt)
        return response
    
    def _format_function_bodies(self, function_bodies, symbol_names):
        """Format function bodies for context."""
        return "\n\n".join([
            f"<function_{i}>\n{body}\n</function_{i}>"
            for i, body in enumerate(function_bodies)
        ])
    
    def evaluate_responses(self, query: str, response1: str, response2: str) -> Dict[str, str]:
        """
        Evaluate two different responses to a query and determine which one is better.
        
        Args:
            query: The user's query
            response1: First response to evaluate
            response2: Second response to evaluate
            
        Returns:
            Dict: A dictionary containing evaluation metrics (specificity, conciseness, completeness)
        """
        evaluation_prompt = f"""You are an expert in embedded system skilled in domain specific customization. You are knowledgeable about general domain knowledge about RTOS, MCU, etc.

-Goal-
Given a question and two responses written by two people, your goal is to evaluate the responses and select the better one. You should read the criteria carefully and for each metric, decide which response is better.

-Criteria-
- Specificity: Identify which answer is more specific, such as explicitly mentioning the exact functions, commands, or steps required, rather than providing a vague or general description.
- Conciseness: Determine which response directly addresses the question in a clear and focused manner, avoiding unnecessary or unrelated information.
- Completeness: Assess which answer provides a more comprehensive explanation, covering all the key points necessary to fully resolve the question.

#####
-Question-
{query}

=====
-Response A-
{response1}

=====
-Response B-
{response2}

#####

Output your evaluation in JSON format with the code block:
```json
{{
  "specificity": "A or B or Tie",
  "conciseness": "A or B or Tie",
  "completeness": "A or B or Tie"
}}
```
"""
        
        result = Agent(llm=get_llm()).invoke_with_structured_output(evaluation_prompt)
        return result

    def process_questions_from_json(
        self, 
        json_file_path: str, 
        output_dir: str,
        entry_limit: int = 3,
        topk: int = 10,
        select_text_units: bool = False,
        rank_threshold: int = 1,
        function_limit: int = 10,
        select_code_functions: bool = False
    ):
        """
        Process questions from a JSON file and generate responses.
        
        Args:
            json_file_path: Path to the JSON file containing questions
            output_dir: Directory to save the results
            entry_limit: Number of entries to retrieve initially
            topk: Number of top results to return
            select_text_units: Whether to use LLM to filter text units
            rank_threshold: Threshold for ranking in function selection
            function_limit: Maximum number of functions to include
            select_code_functions: Whether to use LLM to filter code functions
        """
        
        with open(json_file_path, 'r') as f:
            data = json.loads(f.read())
        
        # Extract the base filename without extension
        base_filename = os.path.splitext(os.path.basename(json_file_path))[0]
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Files to store results
        responses_file = os.path.join(output_dir, f"{base_filename}_responses.txt")
        enhanced_responses_file = os.path.join(output_dir, f"{base_filename}_enhanced_responses.txt")
        evaluations_file = os.path.join(output_dir, f"{base_filename}_evaluations.json")
        summary_file = os.path.join(output_dir, "questions_summary.txt")
        
        # Process each question
        for i, q_data in enumerate(data.get('questions', [])):
            question = q_data.get('question', '')
            if not question:
                continue
            
            # Replace % with %% in the question to avoid format string errors
            safe_question = question.replace('%', '%%')
            print(f"\nProcessing question {i+1}: {safe_question}")
            
            # Generate responses
            text_units = self.query(question, entry_limit=entry_limit, top_k=topk)
            response = self.query(question, text_units=text_units)
            
            text_units = self.query(question, entry_limit=entry_limit, top_k=50)
            enhanced_response = self.query_with_related_functions(
                question, 
                text_units=text_units, 
                rank_threshold=rank_threshold,
                function_limit=function_limit, 
                select=select_code_functions
            )
            evaluation = self.evaluate_responses(question, response, enhanced_response)
            
            # Save responses
            with open(responses_file, 'a', encoding='utf-8') as f:
                f.write(f"\nQuestion {i+1}: {safe_question}\n")
                f.write("-" * 80 + "\n")
                f.write(response + "\n")
            
            with open(enhanced_responses_file, 'a', encoding='utf-8') as f:
                f.write(f"\nQuestion {i+1}: {safe_question}\n")
                f.write("-" * 80 + "\n")
                f.write(enhanced_response + "\n")
            
            # Save evaluations as JSON
            with open(evaluations_file, 'a', encoding='utf-8') as f:
                evaluation_data = {
                    "question": question,
                    "question_number": i+1,
                    "metrics": evaluation,
                    "parameters": {
                        "entry_limit": entry_limit,
                        "topk": topk,
                        "select_text_units": select_text_units,
                        "rank_threshold": rank_threshold,
                        "function_limit": function_limit,
                        "select_code_functions": select_code_functions
                    }
                }
                f.write(json.dumps(evaluation_data, ensure_ascii=False) + "\n")
            
            # Determine overall winner based on the metrics
            metrics_count = {"A": 0, "B": 0, "Tie": 0}
            for metric, value in evaluation.items():
                metrics_count[value] += 1
            
            winner = "Tie"
            if metrics_count["A"] > metrics_count["B"]:
                winner = "A"
            elif metrics_count["B"] > metrics_count["A"]:
                winner = "B"
            
            # Append to summary file
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write(f"File: {base_filename}, Question {i+1}: {safe_question}\n")
                f.write(f"Enhanced Text Units length: {len(text_units)}\n")
                f.write("Parameters: " + json.dumps({
                    'entry_limit': entry_limit,
                    'topk': topk,
                    'select_text_units': select_text_units,
                    'rank_threshold': rank_threshold,
                    'function_limit': function_limit,
                    'select_code_functions': select_code_functions
                }, ensure_ascii=False) + "\n")
                f.write(f"Evaluation Result: {json.dumps(evaluation, ensure_ascii=False)}\n")
                f.write(f"Overall Winner: {winner} (A=Regular, B=Enhanced)\n")
                f.write("-" * 80 + "\n")

    def process_all_json_files(
        self, 
        input_dir: str, 
        output_dir: str,
        entry_limit: int = 3,
        topk: int = 10,
        select_text_units: bool = False,
        rank_threshold: int = 1,
        function_limit: int = 10,
        select_code_functions: bool = False
    ):
        """
        Process all JSON files in the input directory.
        
        Args:
            input_dir: Directory containing JSON files
            output_dir: Directory to save the results
            entry_limit: Number of entries to retrieve initially
            topk: Number of top results to return
            select_text_units: Whether to use LLM to filter text units
            rank_threshold: Threshold for ranking in function selection
            function_limit: Maximum number of functions to include
            select_code_functions: Whether to use LLM to filter code functions
        """
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Clear the summary file
        summary_file = os.path.join(output_dir, "questions_summary.txt")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("Questions and Evaluations Summary\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Parameters:\n")
            f.write(json.dumps({
                'entry_limit': entry_limit,
                'topk': topk,
                'select_text_units': select_text_units,
                'rank_threshold': rank_threshold,
                'function_limit': function_limit,
                'select_code_functions': select_code_functions
            }, indent=2, ensure_ascii=False) + "\n\n")
        
        # Process each JSON file
        for filename in os.listdir(input_dir):
            if filename.endswith('.json'):
                json_file_path = os.path.join(input_dir, filename)
                print(f"\nProcessing file: {filename}")
                self.process_questions_from_json(
                    json_file_path, 
                    output_dir,
                    entry_limit=entry_limit,
                    topk=topk,
                    select_text_units=select_text_units,
                    rank_threshold=rank_threshold,
                    function_limit=function_limit,
                    select_code_functions=select_code_functions
                )

if __name__ == "__main__":
    config = {"root_path": ".rag/JLAC7013"}
    query_engine = GraphMLQueryEngine(config)
    
    # Define input and output directories
    input_dir = ".rag/JLAC7013/queries/"
    output_dir = ".rag/JLAC7013/evaluations/results_5"
    
    # Process all JSON files with custom parameters
    time_start = time.time()
    query_engine.process_all_json_files(
        input_dir, 
        output_dir,
        entry_limit=3,  # Customize these parameters as needed
        topk=10,
        select_text_units=False,
        rank_threshold=1,
        function_limit=10,
        select_code_functions=False
    )
    time_end = time.time()
    print(f"Time taken: {time_end - time_start} seconds")
