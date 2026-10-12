"""Download Emotion and select 10 texts per emotion for the labeling task."""

import json
import random
from collections import Counter
from pathlib import Path

from datasets import load_dataset


ROOT = Path(__file__).resolve().parent


def main():
    dataset = load_dataset(
        "dair-ai/emotion", "split", split="train",
        cache_dir=str(ROOT / ".cache" / "huggingface"),
    )
    emotions = dataset.features["label"].names
    groups = {emotion: [] for emotion in emotions}
    seen_texts = set()

    for index, row in enumerate(dataset):
        if row["text"] in seen_texts:
            continue
        seen_texts.add(row["text"])
        emotion = emotions[row["label"]]
        groups[emotion].append({
            "tweet_id": f"train_{index}",
            "text": row["text"],
            "ground_truth": emotion,
        })

    rng = random.Random(117)
    selected = []
    for emotion in emotions:
        selected.extend(rng.sample(groups[emotion], 10))
    rng.shuffle(selected)

    output = ROOT / "data" / "tweets.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(selected)} tweets to {output}")
    print(dict(Counter(row["ground_truth"] for row in selected)))


if __name__ == "__main__":
    main()
