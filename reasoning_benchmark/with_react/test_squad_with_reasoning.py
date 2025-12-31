"""
Parallel testing script for SQuAD dataset WITH reasoning schema.
Tests questions using structured reasoning before answering.
"""

import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    API_KEY, BASE_URL, MODEL, TEMPERATURE, 
    MAX_TOKENS_REASONING, MAX_TOKENS_ANSWER, MAX_WORKERS, NUM_QUESTIONS,
    REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

console = Console()


@dataclass
class TestResult:
    """Result of a single question test."""
    question_id: str
    question: str
    context: str
    gold_answers: List[str]
    reasoning_steps: List[str]
    final_answer: str
    emin_passed: bool
    emin_results: Dict[str, bool]
    response_time: float
    error: str | None = None


class SQuADReasoningTester:
    """Parallel tester for SQuAD dataset with reasoning."""
    
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
        self.start_time = None
        self.output_file = None  # Will be set when test starts
        
    async def load_squad_data(self) -> List[Dict[str, Any]]:
        """Load SQuAD validation dataset."""
        squad_file = Path(__file__).parent.parent / "squad_data" / "validation.json"
        
        if not squad_file.exists():
            raise FileNotFoundError(f"SQuAD data not found at {squad_file}")
        
        # Load JSONL format
        data = []
        with open(squad_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data.append(json.loads(line))
        
        questions = data[:self.num_questions]
        return questions
    
    async def test_single_question(
        self,
        session: aiohttp.ClientSession,
        question_data: Dict[str, Any],
        index: int
    ) -> TestResult:
        """Test a single question with reasoning."""
        question_id = question_data["id"]
        context = question_data["context"]
        question = question_data["question"]
        gold_answers = question_data["answers"]["text"]
        
        async with self.semaphore:
            start_time = asyncio.get_event_loop().time()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            
            # Response schema with reasoning (simplified - no constraints)
            # TWO-STEP APPROACH: Reasoning first, then extract answer
            reasoning_text = ""
            final_answer = ""
            
            for attempt in range(MAX_RETRIES):
                try:
                    # STEP 1: Model calls reasoning tool
                    tools = [
                        {
                            "type": "function",
                            "function": {
                                "name": "generate_reasoning",
                                "description": "Generate step-by-step reasoning to find the answer in the context",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "reasoning": {
                                            "type": "string",
                                            "description": "Step-by-step analysis of where the answer is in the context"
                                        }
                                    },
                                    "required": ["reasoning"]
                                }
                            }
                        }
                    ]
                    
                    step1_payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant. Use the generate_reasoning tool to think step-by-step, then provide the final answer."
                            },
                            {
                                "role": "user",
                                "content": f"Context: {context}\n\nQuestion: {question}\n\nFirst, use the generate_reasoning tool to analyze where the answer is in the context. Then extract the exact answer."
                            }
                        ],
                        "tools": tools,
                        "tool_choice": {"type": "function", "function": {"name": "generate_reasoning"}},
                        "temperature": TEMPERATURE,
                        "max_tokens": MAX_TOKENS_REASONING
                    }
                    
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=step1_payload,
                        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                    ) as response:
                        response.raise_for_status()
                        result = await response.json()
                        
                        # Extract tool call
                        message = result["choices"][0]["message"]
                        tool_calls = message.get("tool_calls", [])
                        
                        if not tool_calls:
                            reasoning_text = "No tool call generated"
                        else:
                            tool_call = tool_calls[0]
                            try:
                                function_args = json.loads(tool_call["function"]["arguments"])
                                reasoning_text = function_args.get("reasoning", "")
                            except json.JSONDecodeError as e:
                                # Model returned invalid JSON in tool arguments
                                reasoning_text = f"Failed to parse tool arguments: {e}"
                                # Try to extract raw arguments as fallback
                                raw_args = tool_call["function"]["arguments"]
                                if "reasoning" in raw_args:
                                    # Attempt to extract reasoning even from malformed JSON
                                    reasoning_text = raw_args
                    
                    # STEP 2: Continue conversation with tool result
                    # Add descriptive content to assistant message
                    assistant_message = message.copy()
                    assistant_message["content"] = "Let me call the reasoning function to analyze where the answer is located in the context."
                    
                    step2_payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant. Use the generate_reasoning tool to think step-by-step, then provide the final answer."
                            },
                            {
                                "role": "user",
                                "content": f"Context: {context}\n\nQuestion: {question}\n\nFirst, use the generate_reasoning tool to analyze where the answer is in the context. Then extract the exact answer."
                            },
                            assistant_message,  # Assistant's tool call with descriptive content
                            {
                                "role": "tool",
                                "tool_call_id": tool_calls[0]["id"] if tool_calls else "call_0",
                                "content": "Reasoning process completed. Based on the analysis above, now extract the exact answer from the context."
                            }
                        ],
                        "temperature": TEMPERATURE,
                        "max_tokens": MAX_TOKENS_ANSWER
                    }
                    
                    async with session.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=step2_payload,
                        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                    ) as response:
                        if response.status != 200:
                            # Bad request - likely invalid tool call or too long context
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            else:
                                # Last attempt failed, use fallback answer
                                final_answer = "Failed to get answer after retries"
                                break
                        
                        result = await response.json()
                        final_answer = result["choices"][0]["message"]["content"].strip()
                        
                        # Check for bad answer (model looping on whitespace)
                        if final_answer and len(final_answer) > 100:
                            # Check if answer is mostly whitespace/newlines
                            non_whitespace = len(final_answer.strip())
                            if non_whitespace < 10 and len(final_answer) > 100:
                                # Bad answer - retry
                                if attempt < MAX_RETRIES - 1:
                                    continue
                        
                        # Valid answer - break retry loop
                        break
                        
                except asyncio.TimeoutError:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    final_answer = "Timeout error"
                    break
                except aiohttp.ClientError as e:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    final_answer = f"Client error: {e}"
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    final_answer = f"Error: {e}"
                    break
            
            response_time = asyncio.get_event_loop().time() - start_time
                
            # EMIN check
            answer_lower = final_answer.lower()
            emin_results = {}
            emin_passed = False
            
            for gold_answer in gold_answers:
                gold_lower = gold_answer.lower()
                if gold_lower in answer_lower:
                    emin_results[gold_answer] = True
                    emin_passed = True
                    break
                else:
                    emin_results[gold_answer] = False
            
            # Print errors
            if not emin_passed:
                print(f"\n❌ Error on question: {question[:60]}...")
                print(f"   Expected: {gold_answers}")
                print(f"   Got: {final_answer[:100]}")
                if reasoning_text:
                    print(f"   Reasoning: {reasoning_text[:150]}...")
            
            # Update counters
            async with self.lock:
                self.completed += 1
                if emin_passed:
                    self.correct += 1
                current_accuracy = (self.correct / self.completed * 100) if self.completed > 0 else 0
                
                # Update progress
                errors = self.completed - self.correct
                progress_pct = (self.completed / self.num_questions * 100)
                bar_length = 40
                filled = int(bar_length * self.completed / self.num_questions)
                bar = '█' * filled + '░' * (bar_length - filled)
                
                if self.start_time and self.completed > 0:
                    elapsed = asyncio.get_event_loop().time() - self.start_time
                    q_per_sec = self.completed / elapsed
                    remaining_q = self.num_questions - self.completed
                    eta_seconds = (elapsed / self.completed) * remaining_q
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
                reasoning_steps=[reasoning_text] if reasoning_text else [],
                final_answer=final_answer,
                emin_passed=emin_passed,
                emin_results=emin_results,
                response_time=response_time
            )
            
            # Save result immediately
            await self._save_single_result(result)
            
            return result
    
    def _update_progress(self):
        """Update progress bar (called from error handlers)."""
        current_accuracy = (self.correct / self.completed * 100) if self.completed > 0 else 0
        errors = self.completed - self.correct
        progress_pct = (self.completed / self.num_questions * 100)
        bar_length = 40
        filled = int(bar_length * self.completed / self.num_questions)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        if self.start_time and self.completed > 0:
            elapsed = asyncio.get_event_loop().time() - self.start_time
            q_per_sec = self.completed / elapsed
            remaining_q = self.num_questions - self.completed
            eta_seconds = (elapsed / self.completed) * remaining_q
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
            # Don't fail the test if save fails
            pass
    
    async def run_tests(self) -> Dict[str, Any]:
        """Run all tests in parallel."""
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]SQuAD v1.1 WITH REASONING Schema[/]\n"
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
        self.output_file = output_dir / f"squad_reasoning_{timestamp}.jsonl"
        
        # Load data
        questions = await self.load_squad_data()
        
        print()  # New line before progress
        self.start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.test_single_question(session, q, i)
                for i, q in enumerate(questions)
            ]
            
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
        
        # Calculate average reasoning steps
        avg_reasoning_steps = (
            sum(len(r.reasoning_steps) for r in successful_results) / len(successful_results)
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
            "avg_reasoning_steps": avg_reasoning_steps,
            "questions_per_second": total_questions / total_time if total_time > 0 else 0,
            "model": self.model,
            "max_workers": self.max_workers,
            "with_reasoning": True,
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
        summary_file = results_dir / f"summary_reasoning_{timestamp}.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("SQUAD WITH REASONING SCHEMA TEST SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Model: {metrics['model']}\n")
            f.write(f"Workers: {metrics['max_workers']}\n")
            f.write(f"Timestamp: {metrics['timestamp']}\n\n")
            f.write(f"Total Questions: {metrics['total_questions']}\n")
            f.write(f"Correct Answers: {metrics['correct_answers']}\n")
            f.write(f"Incorrect Answers: {metrics['incorrect_answers']}\n")
            f.write(f"Errors: {metrics['errors']}\n\n")
            f.write(f"Accuracy: {metrics['accuracy']:.2f}%\n")
            f.write(f"Avg Reasoning Steps: {metrics['avg_reasoning_steps']:.1f}\n\n")
            f.write(f"Total Time: {metrics['total_time']:.2f}s\n")
            f.write(f"Avg Response Time: {metrics['avg_response_time']:.2f}s\n")
            f.write(f"Questions/Second: {metrics['questions_per_second']:.2f}\n")
            f.write("=" * 80 + "\n")
        
        console.print(f"[green]✓[/] Summary saved to: [cyan]{summary_file.name}[/]")
    
    def print_summary(self, metrics: Dict[str, Any]):
        """Print test summary to console."""
        table = Table(title="SQuAD WITH REASONING Results", title_style="bold cyan")
        
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
        table.add_row("🧠 Avg Reasoning Steps", f"{metrics['avg_reasoning_steps']:.1f}")
        table.add_row("", "")
        table.add_row("⏱️  Total Time", f"{metrics['total_time']:.1f}s ({metrics['total_time']/60:.1f} min)")
        table.add_row("⚡ Avg Response", f"{metrics['avg_response_time']:.2f}s")
        table.add_row("🚀 Throughput", f"{metrics['questions_per_second']:.2f} q/s")
        
        console.print(table)
        console.print()


async def main():
    """Main function to run parallel tests with reasoning."""
    
    # Create tester with config
    tester = SQuADReasoningTester(
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

