"""
Analyze errors from all 5 benchmark approaches.
Find most common error patterns and compare across approaches.
"""

import json
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def load_results(file_path: Path) -> List[Dict]:
    """Load JSONL results file."""
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                results.append(json.loads(line))
    return results


def get_incorrect_results(results: List[Dict]) -> List[Dict]:
    """Filter only incorrect answers."""
    return [r for r in results if not r.get('emin_passed', False)]


def categorize_error(result: Dict) -> str:
    """Categorize the type of error."""
    gold = result['gold_answers'][0].lower() if result['gold_answers'] else ""
    model = result.get('final_answer', result.get('model_answer', '')).lower()
    
    # Check for technical errors
    if 'error' in model or 'failed' in model or 'timeout' in model:
        return "Technical Error"
    
    # Check if model answer is empty or too short
    if len(model.strip()) < 3:
        return "Empty/Too Short"
    
    # Check if model answer is too long (likely explanation instead of answer)
    if len(model) > 200:
        return "Too Long (Explanation)"
    
    # Check for number format issues
    if gold.isdigit() and not any(char.isdigit() for char in model):
        return "Number Format (word vs digit)"
    
    # Check for partial match
    gold_words = set(gold.split())
    model_words = set(model.split())
    if gold_words & model_words:
        return "Partial Match"
    
    # Check for punctuation differences
    gold_clean = ''.join(c for c in gold if c.isalnum() or c.isspace())
    model_clean = ''.join(c for c in model if c.isalnum() or c.isspace())
    if gold_clean == model_clean:
        return "Punctuation Difference"
    
    return "Wrong Answer"


def analyze_approach(name: str, file_path: Path) -> Dict:
    """Analyze errors for a single approach."""
    console.print(f"\n[cyan]Analyzing {name}...[/]")
    
    results = load_results(file_path)
    incorrect = get_incorrect_results(results)
    
    # Categorize errors
    error_categories = Counter()
    error_examples = defaultdict(list)
    
    for result in incorrect:
        category = categorize_error(result)
        error_categories[category] += 1
        
        # Store example (only first 3 per category)
        if len(error_examples[category]) < 3:
            error_examples[category].append({
                'question': result['question'][:80] + "..." if len(result['question']) > 80 else result['question'],
                'expected': result['gold_answers'][0] if result['gold_answers'] else "N/A",
                'got': result.get('final_answer', result.get('model_answer', ''))[:100]
            })
    
    return {
        'total': len(results),
        'incorrect': len(incorrect),
        'accuracy': (len(results) - len(incorrect)) / len(results) * 100,
        'categories': error_categories,
        'examples': error_examples
    }


def main():
    """Main analysis function."""
    console.print(Panel.fit(
        "[bold cyan]Error Analysis Across All Approaches[/]\n"
        "[white]Analyzing 5 different reasoning approaches[/]",
        border_style="cyan"
    ))
    
    # Define all approaches
    approaches = {
        "Without Reasoning": Path("without_reasoning/results/squad_test_20251228_123452.jsonl"),
        "Single-Step SO": Path("with_structured_output/results/squad_so_20251228_124756.jsonl"),
        "Two-Step SO": Path("with_two_step_so/results/squad_two_step_so_20251228_135901.jsonl"),
        "ReAct (1 Tool)": Path("with_react/results/squad_reasoning_20251228_113451.jsonl"),
        "ReAct (2 Tools)": Path("with_react_two_tools/results/squad_react_two_tools_20251228_164513.jsonl"),
    }
    
    # Analyze each approach
    all_results = {}
    for name, path in approaches.items():
        if path.exists():
            all_results[name] = analyze_approach(name, path)
        else:
            console.print(f"[red]File not found: {path}[/]")
    
    # Print summary table
    console.print("\n")
    table = Table(title="Error Summary by Approach", title_style="bold cyan")
    table.add_column("Approach", style="cyan")
    table.add_column("Accuracy", style="green")
    table.add_column("Errors", style="red")
    table.add_column("Top Error Type", style="yellow")
    table.add_column("Count", style="yellow")
    
    for name, data in all_results.items():
        top_error = data['categories'].most_common(1)[0] if data['categories'] else ("N/A", 0)
        table.add_row(
            name,
            f"{data['accuracy']:.2f}%",
            str(data['incorrect']),
            top_error[0],
            str(top_error[1])
        )
    
    console.print(table)
    
    # Print detailed error categories for each approach
    for name, data in all_results.items():
        console.print(f"\n[bold cyan]━━━ {name} ━━━[/]")
        console.print(f"[green]Accuracy: {data['accuracy']:.2f}%[/] | [red]Errors: {data['incorrect']}[/]\n")
        
        # Error categories table
        cat_table = Table(show_header=True, header_style="bold magenta")
        cat_table.add_column("Error Category", style="yellow")
        cat_table.add_column("Count", justify="right", style="red")
        cat_table.add_column("% of Errors", justify="right", style="cyan")
        
        for category, count in data['categories'].most_common():
            percentage = (count / data['incorrect'] * 100) if data['incorrect'] > 0 else 0
            cat_table.add_row(category, str(count), f"{percentage:.1f}%")
        
        console.print(cat_table)
        
        # Print examples for top 3 error types
        console.print("\n[bold]Top Error Examples:[/]")
        for category, count in data['categories'].most_common(3):
            console.print(f"\n[yellow]• {category} ({count} errors):[/]")
            for i, example in enumerate(data['examples'][category][:2], 1):
                console.print(f"  {i}. Q: [dim]{example['question']}[/]")
                console.print(f"     Expected: [green]{example['expected']}[/]")
                console.print(f"     Got: [red]{example['got']}[/]")
    
    # Compare error types across approaches
    console.print("\n[bold cyan]━━━ Error Type Comparison ━━━[/]\n")
    
    # Collect all unique error categories
    all_categories = set()
    for data in all_results.values():
        all_categories.update(data['categories'].keys())
    
    comp_table = Table(title="Error Types Across Approaches", show_header=True)
    comp_table.add_column("Error Type", style="yellow")
    for name in all_results.keys():
        comp_table.add_column(name, justify="right", style="cyan")
    
    for category in sorted(all_categories):
        row = [category]
        for name, data in all_results.items():
            count = data['categories'].get(category, 0)
            percentage = (count / data['incorrect'] * 100) if data['incorrect'] > 0 else 0
            row.append(f"{count} ({percentage:.1f}%)")
        comp_table.add_row(*row)
    
    console.print(comp_table)
    
    # Save detailed report
    report_file = Path("error_analysis_report.txt")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("ERROR ANALYSIS REPORT - ALL APPROACHES\n")
        f.write("=" * 80 + "\n\n")
        
        for name, data in all_results.items():
            f.write(f"\n{name}\n")
            f.write("-" * 40 + "\n")
            f.write(f"Accuracy: {data['accuracy']:.2f}%\n")
            f.write(f"Total Errors: {data['incorrect']}\n\n")
            f.write("Error Categories:\n")
            for category, count in data['categories'].most_common():
                percentage = (count / data['incorrect'] * 100) if data['incorrect'] > 0 else 0
                f.write(f"  - {category}: {count} ({percentage:.1f}%)\n")
            f.write("\n")
    
    console.print(f"\n[green]✓ Detailed report saved to: {report_file}[/]")


if __name__ == "__main__":
    main()


