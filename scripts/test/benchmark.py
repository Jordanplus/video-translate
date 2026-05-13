"""A/B benchmark for translate_lines() across backends.

Usage:
    python scripts/test/benchmark.py --backend mtplx
    python scripts/test/benchmark.py --backend ollama
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT))

from translate.translate import check_backend, translate_lines  # noqa: E402


LINES = [
    "Welcome back to the channel, everyone.",
    "Today we are going to talk about something that I have been meaning to cover for a long time.",
    "It's about how to actually get started with a new programming language without getting overwhelmed.",
    "I know a lot of you have asked me this in the comments, so let's dive right in.",
    "The first mistake people make is trying to read the entire documentation before writing any code.",
    "Don't do that. It's a recipe for burnout.",
    "Instead, pick a small project, something you actually want to build.",
    "It could be a todo list, a weather app, anything that motivates you.",
    "The reason this works is because you'll hit real problems as you go.",
    "And when you hit a problem, you have a concrete question to search for.",
    "That's a much better way to learn than reading abstract concepts in isolation.",
    "The second thing I want to mention is the importance of typing out code yourself.",
    "Copy-pasting from tutorials feels productive but you'll forget everything within a day.",
    "Your fingers need to feel the syntax, that's how it sticks.",
    "Even if you have to type the same loop ten times, it's worth it.",
    "Next, let's talk about the community around the language.",
    "Every modern language has a Discord server, a subreddit, a Stack Overflow tag.",
    "Join them, lurk for a while, see what kinds of problems people are solving.",
    "You'll pick up idioms and best practices just by reading other people's discussions.",
    "Don't be afraid to ask questions either, but make sure you've tried something first.",
    "Show what you tried and what didn't work, that's how you get good answers.",
    "Another tip: read other people's open source code.",
    "Pick a small library that you use and walk through its source.",
    "You'll be surprised how much you learn from seeing how experienced devs structure things.",
    "Don't try to read a giant framework on day one though, start small.",
    "Now, about tooling: every language has its preferred linter, formatter, and test runner.",
    "Set these up on day one, not later.",
    "Having immediate feedback as you type makes a huge difference.",
    "You catch mistakes before they become bugs, and you learn idiomatic style faster.",
    "Speaking of tests, write them from the start, even if they're trivial.",
    "It forces you to think about how your code is going to be used.",
    "And it gives you a safety net when you refactor later.",
    "Refactoring without tests is just gambling.",
    "Let me also mention something controversial: don't use AI assistants for everything at the beginning.",
    "I know it's tempting, but you need to struggle with the basics yourself.",
    "If the AI writes the loop for you, you don't actually learn the loop.",
    "Use it as a tutor, not as a code generator.",
    "Ask it to explain concepts, not to produce solutions.",
    "Once you're comfortable, then start using it to speed things up.",
    "OK, moving on, let's talk about projects to build as you learn.",
    "The classic ones are useful: todo apps, calculators, simple games.",
    "But try to find something with a real use case for you personally.",
    "Maybe you want to automate a tedious task at work.",
    "Maybe you want to scrape data from a website you visit often.",
    "Maybe you want to build a tool that you'd actually use day to day.",
    "That intrinsic motivation makes all the difference when you hit hard problems.",
    "And you will hit hard problems, that's part of the journey.",
    "Don't get discouraged when you spend three hours on something that seemed easy.",
    "That's literally how everyone learned to program.",
    "Finally, set a realistic timeline.",
    "You won't be fluent in a new language in a week.",
    "Three to six months of consistent practice is more realistic.",
    "And remember, even experienced developers don't know everything.",
    "We just know how to find what we need quickly.",
    "Alright, that's it for today's video.",
    "If you found this helpful, please give it a like and subscribe.",
    "Let me know in the comments which language you're learning right now.",
    "I read every comment and try to respond when I can.",
    "Thanks for watching, and I'll see you in the next one.",
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", required=True, choices=["mtplx", "ollama"])
    p.add_argument("--model", default=None)
    args = p.parse_args()

    n = len(LINES)
    src_chars = sum(len(s) for s in LINES)
    print(f"Backend : {args.backend}")
    print(f"Model   : {args.model or '(default)'}")
    print(f"Lines   : {n}")
    print(f"SrcChars: {src_chars}")
    print()

    check_backend(args.backend)

    t0 = time.perf_counter()
    out = translate_lines(LINES, backend=args.backend, model=args.model)
    elapsed = time.perf_counter() - t0

    tgt_chars = sum(len(s) for s in out)
    print()
    print(f"Elapsed       : {elapsed:.2f} s")
    print(f"Lines/sec     : {n / elapsed:.2f}")
    print(f"SrcChars/sec  : {src_chars / elapsed:.1f}")
    print(f"TgtChars total: {tgt_chars}")

    out_path = SCRIPTS_ROOT.parent / "output" / "test" / f"benchmark_{args.backend}.txt"
    with out_path.open("w") as f:
        f.write(f"Backend: {args.backend}\n")
        f.write(f"Elapsed: {elapsed:.2f}s   Lines/sec: {n/elapsed:.2f}\n\n")
        for src, tgt in zip(LINES, out):
            f.write(f"EN: {src}\nZH: {tgt}\n\n")
    print(f"Output saved  : {out_path}")


if __name__ == "__main__":
    main()
