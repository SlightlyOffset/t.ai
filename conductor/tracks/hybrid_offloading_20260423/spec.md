# Spec: Hybrid Offloading & Async Post-Processing

## Problem
Using a remote Colab GPU for all LLM tasks causes high latency and blocking. Heavy tasks (Roleplay) compete with lightweight utility tasks (Sentiment scoring, summarization), leading to GPU queuing and OOM errors.

## Goals
- Offload lightweight utility tasks to local LLMs via Ollama.
- Make post-processing tasks (sentiment, score updates) asynchronous to prevent UI blocking.
- Reduce Colab GPU load and context-switching.

## Technical Requirements
- New setting `local_utility_model` in `settings.json`.
- `get_sentiment_score` must use local Ollama and the utility model.
- `generate_summary` and `update_rolling_summary` must use local Ollama and the utility model.
- `get_respond_stream` must fire background threads for post-processing tasks.
