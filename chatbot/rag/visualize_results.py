#!/usr/bin/env python
import os
import sys
import json
import argparse
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path
import django

# Add the project directory to the Python path
project_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(project_dir))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings')
django.setup()

from rag.evaluation import EVALUATION_RESULTS_PATH

def load_results(results_path=None):
    """Load evaluation results from file"""
    if results_path is None:
        results_path = EVALUATION_RESULTS_PATH
    
    if not os.path.exists(results_path):
        print(f"Error: Results file not found at {results_path}")
        return None
    
    with open(results_path, 'r') as f:
        results = json.load(f)
    
    return results

def plot_overall_metrics(results, output_path=None):
    """Plot overall metrics as a bar chart"""
    metrics = results['metrics']
    
    # Create a bar chart
    fig, ax = plt.figure(figsize=(10, 6)), plt.axes()
    
    # Prepare data
    labels = [metric.replace('_', ' ').title() for metric in metrics.keys()]
    values = list(metrics.values())
    
    # Create bars
    bars = ax.bar(labels, values, color='skyblue')
    
    # Add labels and title
    ax.set_ylabel('Score (0-1)')
    ax.set_title('RAG System Evaluation Metrics')
    ax.set_ylim(0, 1)
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 0.02,
                f'{height:.2f}', ha='center', va='bottom')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path)
        print(f"Saved overall metrics chart to {output_path}")
    else:
        plt.show()

def plot_qa_metrics(results, output_path=None):
    """Plot metrics for each QA pair as a heatmap"""
    qa_results = results['qa_results']
    
    if not qa_results:
        print("No QA results to visualize")
        return
    
    # Extract metrics for each question
    data = []
    questions = []
    
    for i, result in enumerate(qa_results):
        if 'scores' in result:
            # Truncate question for display
            question = result['question']
            if len(question) > 40:
                question = question[:37] + "..."
            
            questions.append(f"Q{i+1}: {question}")
            
            # Get scores
            scores = result['scores']
            data.append([
                scores.get('relevance', 0),
                scores.get('faithfulness', 0),
                scores.get('context_precision', 0),
                scores.get('answer_correctness', 0)
            ])
    
    if not data:
        print("No score data found in results")
        return
    
    # Create DataFrame
    df = pd.DataFrame(
        data,
        index=questions,
        columns=['Relevance', 'Faithfulness', 'Context Precision', 'Answer Correctness']
    )
    
    # Plot heatmap
    plt.figure(figsize=(12, max(8, len(questions) * 0.4)))
    heatmap = plt.pcolor(df, cmap='YlGnBu', vmin=0, vmax=1)
    
    # Add color bar
    plt.colorbar(heatmap)
    
    # Add labels
    plt.yticks(np.arange(0.5, len(df.index)), df.index)
    plt.xticks(np.arange(0.5, len(df.columns)), df.columns, rotation=45)
    
    plt.title('Per-Question Evaluation Metrics')
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path)
        print(f"Saved per-question metrics chart to {output_path}")
    else:
        plt.show()

def main():
    parser = argparse.ArgumentParser(description='Visualize RAG evaluation results')
    
    parser.add_argument('--results', type=str, default=None, help='Path to the evaluation results JSON file')
    parser.add_argument('--output-dir', type=str, default='visualization', help='Directory to save visualization charts')
    parser.add_argument('--overall', action='store_true', help='Generate overall metrics chart')
    parser.add_argument('--qa-metrics', action='store_true', help='Generate per-question metrics chart')
    parser.add_argument('--all', action='store_true', help='Generate all visualization charts')
    
    args = parser.parse_args()
    
    # Default behavior if no specific charts are requested
    if not (args.overall or args.qa_metrics or args.all):
        args.all = True
    
    # Load results
    results = load_results(args.results)
    if not results:
        return
    
    # Create output directory if it doesn't exist
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
    
    # Generate visualizations
    if args.overall or args.all:
        output_path = os.path.join(args.output_dir, 'overall_metrics.png') if args.output_dir else None
        plot_overall_metrics(results, output_path)
    
    if args.qa_metrics or args.all:
        output_path = os.path.join(args.output_dir, 'qa_metrics.png') if args.output_dir else None
        plot_qa_metrics(results, output_path)

if __name__ == '__main__':
    main() 