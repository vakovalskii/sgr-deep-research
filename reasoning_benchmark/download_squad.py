"""
Script to download the SQuAD dataset from Hugging Face.
"""
from datasets import load_dataset
import json
import os

def download_squad():
    """Download SQuAD dataset and save it locally."""
    print("Downloading SQuAD dataset from Hugging Face...")
    
    # Load the dataset
    dataset = load_dataset("rajpurkar/squad")
    
    # Create directory for the dataset
    output_dir = "squad_data"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\nDataset info:")
    print(f"Train set size: {len(dataset['train'])}")
    print(f"Validation set size: {len(dataset['validation'])}")
    
    # Save train set
    train_path = os.path.join(output_dir, "train.json")
    dataset['train'].to_json(train_path)
    print(f"\nTrain set saved to: {train_path}")
    
    # Save validation set
    val_path = os.path.join(output_dir, "validation.json")
    dataset['validation'].to_json(val_path)
    print(f"Validation set saved to: {val_path}")
    
    # Show example
    print("\n" + "="*80)
    print("Example from the dataset:")
    print("="*80)
    example = dataset['train'][0]
    print(f"\nContext: {example['context'][:200]}...")
    print(f"\nQuestion: {example['question']}")
    print(f"Answer: {example['answers']}")
    print(f"ID: {example['id']}")
    print(f"Title: {example['title']}")
    
    return dataset

if __name__ == "__main__":
    dataset = download_squad()
    print("\n✓ Dataset downloaded successfully!")


