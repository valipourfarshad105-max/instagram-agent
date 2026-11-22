#!/usr/bin/env python3
"""راه‌انداز ساده:  python main.py <دستور>   (مثل python main.py generate)"""
import sys

from agent.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
