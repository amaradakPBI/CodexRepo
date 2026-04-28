# CodexRepo

Scientific calculator application built from the tracked PRD, with Streamlit UI, a safe local expression engine, programmer conversions, unit conversion, history persistence, and export workflows.

## What is included

- Standard, Scientific, and Programmer calculator modes
- Safe local expression evaluation with trig, logarithms, roots, powers, factorial, permutations, combinations, and bitwise operations
- Degree, Radian, and Gradian angle settings with configurable number formatting
- Local history persistence, memory register actions, variable assignment, and `Ans` reuse
- Built-in constants browser and inline unit conversion support such as `150 lb to kg`
- Export of history to TXT, PDF, and JSON

## Project layout

- `app.py`: main Streamlit application
- `calculator/`: engine, constants, unit conversion, export, and storage helpers
- `tests/`: focused unit tests for the engine, conversions, and persistence

## Local run

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -r requirements.txt
   ```

2. Start the app on localhost:

   ```bash
   streamlit run app.py --server.address localhost --server.port 8501
   ```

3. Run tests:

   ```bash
   python -m pytest -q tests
   ```
