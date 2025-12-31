"""
Parallel testing script for SQuAD dataset WITH ReAct Two Tools.
Agent calls two tools sequentially:
1. generate_reasoning - to analyze the context
2. submit_answer - to provide the final answer
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


class SQuADReActTwoToolsTester:
    """Parallel tester for SQuAD dataset with ReAct Two Tools."""
    
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
        self.output_file = None
        
    async def load_squad_data(self) -> List[Dict[str, Any]]:
        """Load SQuAD validation dataset."""
        squad_file = Path(__file__).parent.parent / "squad_data" / "validation.json"
        
        if not squad_file.exists():
            raise FileNotFoundError(f"SQuAD data not found at {squad_file}")
        
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
        """Test a single question with ReAct Two Tools."""
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
            
            reasoning_text = ""
            final_answer = ""
            
            for attempt in range(MAX_RETRIES):
                try:
                    # Define two tools
                    tools = [
                        {
                            "type": "function",
                            "function": {
                                "name": "generate_reasoning",
                                "description": "Generate step-by-step reasoning to analyze where the answer is in the context",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "reasoning": {
                                            "type": "string",
                                            "description": "Step-by-step analysis of where the answer is located in the context"
                                        }
                                    },
                                    "required": ["reasoning"]
                                }
                            }
                        },
                        {
                            "type": "function",
                            "function": {
                                "name": "submit_answer",
                                "description": "Submit the final answer extracted from the context",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "answer": {
                                            "type": "string",
                                            "description": "The exact answer extracted from the context"
                                        }
                                    },
                                    "required": ["answer"]
                                }
                            }
                        }
                    ]
                    
                    # STEP 1: Force model to call generate_reasoning tool
                    step1_payload = {
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant. First use generate_reasoning to analyze, then use submit_answer to provide the final answer."
                            },
                            {
                                "role": "user",
                                "content": f"Context: {context}\n\nQuestion: {question}\n\nFirst, call generate_reasoning to analyze where the answer is. Then call submit_answer with the exact answer."
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
                            final_answer = "No tool call generated"
                            break
                        
                        # Process first tool call (should be generate_reasoning)
                        first_tool = tool_calls[0]
                        if first_tool["function"]["name"] == "generate_reasoning":
                            try:
                                function_args = json.loads(first_tool["function"]["arguments"])
                                reasoning_text = function_args.get("reasoning", "")
                            except json.JSONDecodeError as e:
                                reasoning_text = f"Failed to parse reasoning: {e}"
                        
                        # Build conversation history with tool response
                        messages = [
                            {
                                "role": "system",
                                "content": "You are a helpful assistant. First use generate_reasoning to analyze, then use submit_answer to provide the final answer."
                            },
                            {
                                "role": "user",
                                "content": f"Context: {context}\n\nQuestion: {question}\n\nFirst, call generate_reasoning to analyze where the answer is. Then call submit_answer with the exact answer."
                            },
                            message,  # Assistant's first tool call
                            {
                                "role": "tool",
                                "tool_call_id": first_tool["id"],
                                "content": f"Reasoning recorded: {reasoning_text[:100]}... Now call submit_answer with the exact answer from the context."
                            }
                        ]
                    
                    # STEP 2: Model calls submit_answer tool
                    step2_payload = {
                        "model": self.model,
                        "messages": messages,
                        "tools": tools,
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
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(RETRY_DELAY)
                                continue
                            final_answer = "Failed to get answer"
                            break
                        
                        result = await response.json()
                        message2 = result["choices"][0]["message"]
                        tool_calls2 = message2.get("tool_calls", [])
                        
                        if tool_calls2:
                            # Extract answer from submit_answer tool call
                            for tool_call in tool_calls2:
                                if tool_call["function"]["name"] == "submit_answer":
                                    try:
                                        function_args = json.loads(tool_call["function"]["arguments"])
                                        final_answer = function_args.get("answer", "").strip()
                                        break
                                    except json.JSONDecodeError:
                                        final_answer = "Failed to parse answer"
                        else:
                            # Fallback to content if no tool call
                            final_answer = message2.get("content", "No answer provided").strip()
                        
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
            f"[bold cyan]SQuAD v1.1 WITH ReAct Two Tools[/]\n"
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
        self.output_file = output_dir / f"squad_react_two_tools_{timestamp}.jsonl"
        
        # Load data
        questions = await self.load_squad_data()
        
        print()
        self.start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.test_single_question(session, q, i)
                for i, q in enumerate(questions)
            ]
            
            start_time = asyncio.get_event_loop().time()
            self.results = await asyncio.gather(*tasks)
            total_time = asyncio.get_event_loop().time() - start_time
        
        print()
        
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
        
        return {
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
            "approach": "ReAct Two Tools",
            "timestamp": datetime.now().isoformat()
        }
    
    def _save_results(self, metrics: Dict[str, Any]):
        """Save test summary."""
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        
        if self.output_file:
            console.print(f"[green]✓[/] Results saved to: [cyan]{self.output_file.name}[/]")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = results_dir / f"summary_react_two_tools_{timestamp}.txt"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("SQUAD WITH REACT TWO TOOLS TEST SUMMARY\n")
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
        table = Table(title="SQuAD WITH ReAct Two Tools Results", title_style="bold cyan")
        
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")
        
        table.add_row("Model", metrics['model'])
        table.add_row("Workers", str(metrics['max_workers']))
        table.add_row("", "")
        table.add_row("Total Questions", str(metrics['total_questions']))
        table.add_row("Correct Answers", str(metrics['correct_answers']))
        table.add_row("Incorrect Answers", str(metrics['incorrect_answers']))
        table.add_row("Errors", str(metrics['errors']))
        table.add_row("", "")
        table.add_row("Accuracy", f"{metrics['accuracy']:.2f}%")
        table.add_row("", "")
        table.add_row("Total Time", f"{metrics['total_time']:.2f}s")
        table.add_row("Avg Response Time", f"{metrics['avg_response_time']:.2f}s")
        table.add_row("Questions/Second", f"{metrics['questions_per_second']:.2f}")
        
        console.print(table)


async def main():
    """Main function to run parallel tests with ReAct Two Tools."""
    
    # Create tester with config
    tester = SQuADReActTwoToolsTester(
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

