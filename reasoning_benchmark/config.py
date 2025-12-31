"""
Unified configuration for all SQuAD benchmark tests.
"""

# API Configuration
API_KEY = "F9yei26LMobzDdVmdKuEcbIlTod3OoTJXAszIUoMdAwYwGWS50bvKODj99JZRqcJA8mUQgR1zlXoHpCORP97ODLAyfagqrob"
BASE_URL = "https://4090-2-48.neuraldeep.tech/v1"
MODEL = "qwen3-30b-a3b-instruct-2507"

# Model Parameters
TEMPERATURE = 0.1
MAX_TOKENS_REASONING = 2000
MAX_TOKENS_ANSWER = 2000
MAX_TOKENS_NO_REASONING = 2000

# Benchmark Parameters
MAX_WORKERS = 30
NUM_QUESTIONS = 10570  # Full validation set

# Timeout Settings
REQUEST_TIMEOUT = 120  # seconds
MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds

