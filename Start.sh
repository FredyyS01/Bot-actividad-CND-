#!/bin/bash
python3 -m flask run --host=0.0.0.0 --port=$PORT & python3 main.py
