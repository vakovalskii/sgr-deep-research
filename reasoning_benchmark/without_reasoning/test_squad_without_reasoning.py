"""
Parallel testing script for SQuAD dataset without reasoning schema.
Tests 1000 questions using 10 concurrent workers with aiohttp.
"""

import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import logging
from dataclasses import dataclass, asdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
import sys
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    API_KEY, BASE_URL, MODEL, TEMPERATURE, 
    MAX_TOKENS_NO_REASONING, MAX_WORKERS, NUM_QUESTIONS,
    REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

console = Console()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)


@dataclass
class TestResult:
    """Result of a single question test."""
    question_id: str
    question: str
    context: str
    gold_answers: List[str]
    model_answer: str
    emin_passed: bool
    emin_results: Dict[str, bool]
    response_time: float
    error: str | None = None


class SQuADTester:
    """Parallel tester for SQuAD dataset."""
    
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        max_workers: int = 10,
        num_questions: int = 1000
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.max_workers = max_workers
        self.num_questions = num_questions
        self.results: List[TestResult] = []
        self.semaphore = asyncio.Semaphore(max_workers)
        self.completed = 0
        self.correct = 0
        self.lock = asyncio.Lock()
        self.progress = None
        self.task_id = None
        self.start_time = None
        self.output_file = None
        
    async def load_squad_data(self) -> List[Dict[str, Any]]:
        """Load SQuAD validation dataset."""
        squad_file = Path(__file__).parent.parent / "squad_data" / "validation.json"
        
        if not squad_file.exists():
            raise FileNotFoundError(f"SQuAD data not found at {squad_file}")
        
        # Load JSONL format (each line is a JSON object)
        data = []
        with open(squad_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        
        # Take first N questions
        questions = data[:self.num_questions]
        
        return questions
    
    async def test_single_question(
        self,
        session: aiohttp.ClientSession,
        question_data: Dict[str, Any],
        index: int
    ) -> TestResult:
        """Test a single question."""
        async with self.semaphore:
            start_time = asyncio.get_event_loop().time()
            
            question_id = question_data["id"]
            context = question_data["context"]
            question = question_data["question"]
            gold_answers = question_data["answers"]["text"]
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Answer the question based on the given context."
                    },
                    {
                        "role": "user",
                        "content": f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
                    }
                ],
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS_NO_REASONING
            }
            
            try:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    
                    model_answer = result["choices"][0]["message"]["content"].strip()
                    response_time = asyncio.get_event_loop().time() - start_time
                    
                    # EMIN check
                    model_answer_lower = model_answer.lower()
                    emin_results = {}
                    emin_passed = False
                    found_fragment = None
                    matched_gold = None
                    
                    for gold_answer in gold_answers:
                        gold_lower = gold_answer.lower()
                        if gold_lower in model_answer_lower:
                            emin_results[gold_answer] = True
                            emin_passed = True
                            matched_gold = gold_answer
                            # Find the fragment in the original answer
                            start_idx = model_answer_lower.find(gold_lower)
                            end_idx = start_idx + len(gold_lower)
                            # Get context around the match
                            context_start = max(0, start_idx - 30)
                            context_end = min(len(model_answer), end_idx + 30)
                            found_fragment = model_answer[context_start:context_end]
                            break
                        else:
                            emin_results[gold_answer] = False
                    
                    # Update counters
                    async with self.lock:
                        self.completed += 1
                        if emin_passed:
                            self.correct += 1
                        current_accuracy = (self.correct / self.completed * 100) if self.completed > 0 else 0
                        
                        # Update progress - print to console
                        errors = self.completed - self.correct
                        progress_pct = (self.completed / self.num_questions * 100)
                        bar_length = 40
                        filled = int(bar_length * self.completed / self.num_questions)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        
                        # Calculate ETA and speed
                        if self.start_time and self.completed > 0:
                            elapsed = asyncio.get_event_loop().time() - self.start_time
                            avg_time_per_q = elapsed / self.completed
                            q_per_sec = self.completed / elapsed
                            remaining_q = self.num_questions - self.completed
                            eta_seconds = avg_time_per_q * remaining_q
                            eta_min = int(eta_seconds // 60)
                            eta_sec = int(eta_seconds % 60)
                            eta_str = f"ETA: {eta_min}m {eta_sec}s"
                            speed_str = f"{q_per_sec:.1f} q/s"
                        else:
                            eta_str = "ETA: --"
                            speed_str = "-- q/s"
                        
                        # Clear line and write progress (stay on same line)
                        line = f"[{bar}] {progress_pct:.1f}% | ✓ {self.correct} | ✗ {errors} | Acc: {current_accuracy:.1f}% | {self.completed}/{self.num_questions} | {speed_str} | {eta_str}"
                        sys.stdout.write(f"\r{line:<120}")
                        sys.stdout.flush()
                    
                    result = TestResult(
                        question_id=question_id,
                        question=question,
                        context=context,
                        gold_answers=gold_answers,
                        model_answer=model_answer,
                        emin_passed=emin_passed,
                        emin_results=emin_results,
                        response_time=response_time
                    )
                    
                    # Save result immediately
                    await self._save_single_result(result)
                    return result
                    
            except asyncio.TimeoutError:
                async with self.lock:
                    self.completed += 1
                    current_accuracy = (self.correct / self.completed * 100) if self.completed > 0 else 0
                    errors = self.completed - self.correct
                    progress_pct = (self.completed / self.num_questions * 100)
                    bar_length = 40
                    filled = int(bar_length * self.completed / self.num_questions)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    if self.start_time and self.completed > 0:
                        elapsed = asyncio.get_event_loop().time() - self.start_time
                        avg_time_per_q = elapsed / self.completed
                        q_per_sec = self.completed / elapsed
                        remaining_q = self.num_questions - self.completed
                        eta_seconds = avg_time_per_q * remaining_q
                        eta_min = int(eta_seconds // 60)
                        eta_sec = int(eta_seconds % 60)
                        eta_str = f"ETA: {eta_min}m {eta_sec}s"
                        speed_str = f"{q_per_sec:.1f} q/s"
                    else:
                        eta_str = "ETA: --"
                        speed_str = "-- q/s"
                    
                    line = f"[{bar}] {progress_pct:.1f}% | ✓ {self.correct} | ✗ {errors} | Acc: {current_accuracy:.1f}% | {self.completed}/{self.num_questions} | {speed_str} | {eta_str}"
                    sys.stdout.write(f"\r{line:<120}")
                    sys.stdout.flush()
                
                result = TestResult(
                    question_id=question_id,
                    question=question,
                    context=context,
                    gold_answers=gold_answers,
                    model_answer="",
                    emin_passed=False,
                    emin_results={},
                    response_time=0.0,
                    error="Timeout"
                )
                await self._save_single_result(result)
                return result
            except Exception as e:
                async with self.lock:
                    self.completed += 1
                    current_accuracy = (self.correct / self.completed * 100) if self.completed > 0 else 0
                    errors = self.completed - self.correct
                    progress_pct = (self.completed / self.num_questions * 100)
                    bar_length = 40
                    filled = int(bar_length * self.completed / self.num_questions)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    if self.start_time and self.completed > 0:
                        elapsed = asyncio.get_event_loop().time() - self.start_time
                        avg_time_per_q = elapsed / self.completed
                        q_per_sec = self.completed / elapsed
                        remaining_q = self.num_questions - self.completed
                        eta_seconds = avg_time_per_q * remaining_q
                        eta_min = int(eta_seconds // 60)
                        eta_sec = int(eta_seconds % 60)
                        eta_str = f"ETA: {eta_min}m {eta_sec}s"
                        speed_str = f"{q_per_sec:.1f} q/s"
                    else:
                        eta_str = "ETA: --"
                        speed_str = "-- q/s"
                    
                    line = f"[{bar}] {progress_pct:.1f}% | ✓ {self.correct} | ✗ {errors} | Acc: {current_accuracy:.1f}% | {self.completed}/{self.num_questions} | {speed_str} | {eta_str}"
                    sys.stdout.write(f"\r{line:<120}")
                    sys.stdout.flush()
                
                result = TestResult(
                    question_id=question_id,
                    question=question,
                    context=context,
                    gold_answers=gold_answers,
                    model_answer="",
                    emin_passed=False,
                    emin_results={},
                    response_time=0.0,
                    error=str(e)
                )
                await self._save_single_result(result)
                return result
    
    async def _save_single_result(self, result: TestResult):
        """Save a single result to file immediately (append mode)."""
        if not self.output_file:
            return
        
        try:
            async with self.lock:
                with open(self.output_file, "a", encoding="utf-8") as f:
                    json.dump(asdict(result), f, ensure_ascii=False)
                    f.write("\n")
        except Exception as e:
            pass
    
    async def run_tests(self) -> Dict[str, Any]:
        """Run all tests in parallel."""
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]SQuAD v1.1 Validation Benchmark[/]\n"
            f"[white]Questions:[/] {self.num_questions} | "
            f"[white]Workers:[/] {self.max_workers} | "
            f"[white]Model:[/] {self.model}",
            border_style="cyan"
        ))
        console.print()
        
        # Setup output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(__file__).parent / "results"
        output_dir.mkdir(exist_ok=True)
        self.output_file = output_dir / f"squad_test_{timestamp}.jsonl"
        
        # Load data
        questions = await self.load_squad_data()
        
        # Simple progress bar with stdout
        print()  # New line before progress
        
        # Set start time for ETA calculation
        self.start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            # Create tasks
            tasks = [
                self.test_single_question(session, q, i)
                for i, q in enumerate(questions)
            ]
            
            # Run all tasks
            start_time = asyncio.get_event_loop().time()
            self.results = await asyncio.gather(*tasks)
            total_time = asyncio.get_event_loop().time() - start_time
        
        print()  # New line after progress
        
        # Calculate metrics
        metrics = self._calculate_metrics(total_time)
        
        # Save results
        console.print()
        self._save_results(metrics)
        
        return metrics
    
    def _calculate_metrics(self, total_time: float) -> Dict[str, Any]:
        """Calculate accuracy and performance metrics."""
        total_questions = len(self.results)
        correct_answers = sum(1 for r in self.results if r.emin_passed)
        errors = sum(1 for r in self.results if r.error is not None)
        
        successful_results = [r for r in self.results if r.error is None]
        avg_response_time = (
            sum(r.response_time for r in successful_results) / len(successful_results)
            if successful_results else 0
        )
        
        accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
        
        metrics = {
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "incorrect_answers": total_questions - correct_answers - errors,
            "errors": errors,
            "accuracy": accuracy,
            "total_time": total_time,
            "avg_response_time": avg_response_time,
            "questions_per_second": total_questions / total_time if total_time > 0 else 0,
            "model": self.model,
            "max_workers": self.max_workers,
            "timestamp": datetime.now().isoformat()
        }
        
        return metrics
    
    def _save_results(self, metrics: Dict[str, Any]):
        """Save test summary (detailed results already saved incrementally)."""
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        
        # Results already saved incrementally to self.output_file
        if self.output_file:
            console.print(f"[green]✓[/] Results saved to: [cyan]{self.output_file.name}[/]")
        
        # Save summary
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = results_dir / f"summary_{timestamp}.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("SQUAD PARALLEL TEST SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Model: {metrics['model']}\n")
            f.write(f"Workers: {metrics['max_workers']}\n")
            f.write(f"Timestamp: {metrics['timestamp']}\n\n")
            f.write(f"Total Questions: {metrics['total_questions']}\n")
            f.write(f"Correct Answers: {metrics['correct_answers']}\n")
            f.write(f"Incorrect Answers: {metrics['incorrect_answers']}\n")
            f.write(f"Errors: {metrics['errors']}\n\n")
            f.write(f"Accuracy: {metrics['accuracy']:.2f}%\n\n")
            f.write(f"Total Time: {metrics['total_time']:.2f}s\n")
            f.write(f"Avg Response Time: {metrics['avg_response_time']:.2f}s\n")
            f.write(f"Questions/Second: {metrics['questions_per_second']:.2f}\n")
            f.write("=" * 80 + "\n")
        
        console.print(f"[green]✓[/] Summary saved to: [cyan]{summary_file.name}[/]")
    
    def print_summary(self, metrics: Dict[str, Any]):
        """Print test summary to console."""
        table = Table(title="SQuAD Validation Results", title_style="bold cyan")
        
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        
        table.add_row("Model", metrics['model'])
        table.add_row("Workers", str(metrics['max_workers']))
        table.add_row("", "")
        table.add_row("Total Questions", str(metrics['total_questions']))
        table.add_row("✅ Correct", f"[green]{metrics['correct_answers']}[/]")
        table.add_row("❌ Incorrect", f"[red]{metrics['incorrect_answers']}[/]")
        table.add_row("⚠️  Errors", str(metrics['errors']))
        table.add_row("", "")
        table.add_row("🎯 Accuracy (EMIN)", f"[bold green]{metrics['accuracy']:.2f}%[/]")
        table.add_row("", "")
        table.add_row("⏱️  Total Time", f"{metrics['total_time']:.1f}s ({metrics['total_time']/60:.1f} min)")
        table.add_row("⚡ Avg Response", f"{metrics['avg_response_time']:.2f}s")
        table.add_row("🚀 Throughput", f"{metrics['questions_per_second']:.2f} q/s")
        
        console.print(table)
        console.print()


async def main():
    """Main function to run parallel tests."""
    
    # Create tester with config
    tester = SQuADTester(
        api_key=API_KEY,
        base_url=BASE_URL,
        model=MODEL,
        max_workers=MAX_WORKERS,
        num_questions=NUM_QUESTIONS
    )
    
    # Run tests
    metrics = await tester.run_tests()
    
    # Print summary
    tester.print_summary(metrics)


if __name__ == "__main__":
    asyncio.run(main())

