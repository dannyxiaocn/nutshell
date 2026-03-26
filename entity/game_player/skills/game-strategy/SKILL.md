---
name: game-strategy
description: >
  Game strategy framework — teaches the agent how to classify games, select
  optimal strategies, and systematically solve puzzles, riddles, text adventures,
  math challenges, and code golf problems with maximum efficiency.
---

## Game Classification

Before playing, classify the game along these axes:

### Information
| Type | Description | Strategy Bias |
|------|-------------|---------------|
| **Perfect information** | All state visible (chess, puzzles) | Exact search / DP |
| **Imperfect information** | Hidden state (card games, fog of war) | Probabilistic reasoning, Bayesian updates |

### Players
| Type | Strategy |
|------|----------|
| **Single-player** | Optimization — find the globally best solution |
| **Two-player adversarial** | Minimax / alpha-beta pruning |
| **Cooperative** | Communication, role assignment, shared planning |

### Determinism
| Type | Strategy |
|------|----------|
| **Deterministic** | Exact planning, reproducible paths |
| **Stochastic** | Expected-value maximization, Monte Carlo sampling |

---

## Universal Solving Framework

Every game follows this loop:

```
1. OBSERVE  → What is the current state? What changed since last move?
2. ANALYZE  → What are my options? What does each option lead to?
3. DECIDE   → Pick the option with the best expected outcome.
4. ACT      → Execute the chosen move.
5. VERIFY   → Did the result match my expectation? Update my model if not.
```

**Key principle**: Spend more time in steps 1-3 than in step 4. The best players think long and act fast.

---

## Strategy Templates by Game Type

### Maze / Graph Exploration
- Model the world as a graph (nodes = locations, edges = connections).
- Use BFS for shortest path, DFS for full exploration.
- Track visited nodes to avoid loops.
- Use `state_diff` key `"maze_map"` to snapshot your mental map.

```python
# Quick maze solver template
from collections import deque

def bfs(graph, start, goal):
    queue = deque([(start, [start])])
    visited = {start}
    while queue:
        node, path = queue.popleft()
        if node == goal:
            return path
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))
    return None  # no path
```

### Permutation / Combinatorial Puzzles
- Identify the constraint set (e.g., "each row/column has unique values").
- Use constraint propagation first (eliminate impossible values).
- If not fully solved, apply backtracking search.
- For small N (≤10), brute force all N! permutations.

```python
from itertools import permutations

def solve_by_brute_force(n, is_valid):
    for perm in permutations(range(n)):
        if is_valid(perm):
            return perm
```

### Word / Letter Guessing (Hangman, Wordle-like)
- Start with frequency analysis: E, T, A, O, I, N, S, H, R are most common in English.
- Use regex filtering on a dictionary to narrow candidates after each guess.
- Maximize information gain: pick letters that split the remaining word set most evenly.

```python
import re

def filter_words(words, pattern, excluded):
    """pattern like '_a_e', excluded is set of wrong letters."""
    regex = pattern.replace('_', '[^' + ''.join(excluded) + ']')
    return [w for w in words if re.fullmatch(regex, w)]
```

### Math / Number Puzzles
- Translate the problem into equations or constraints.
- Use Python for exact computation — never estimate.
- Common techniques: modular arithmetic, prime factorization, GCD/LCM, systems of equations.
- For optimization: check if it's a known problem (knapsack, shortest path, linear programming).

```python
from math import gcd, isqrt
from functools import reduce

def solve_linear_system(equations):
    """Use sympy for symbolic solving."""
    from sympy import symbols, Eq, solve
    # ... set up and solve
```

### Text Adventures / Interactive Fiction
- **Map everything.** Create a graph of rooms and connections.
- **Inventory management.** Track all items, note where you found them and where they might be used.
- **Talk to everyone.** NPCs often give critical hints.
- **Try obvious combinations first.** Key→door, sword→monster, etc.
- **Save state frequently** with `state_diff`.

### Code Golf / Code Challenges
- Read the problem statement twice. Understand edge cases.
- Start with a correct brute-force solution.
- Optimize for the specific scoring metric (shortest code, fastest runtime, least memory).
- For code golf: use language-specific tricks (Python: `lambda`, `*a,`, walrus `:=`).
- Always test with the provided examples AND edge cases.

### Riddles / Lateral Thinking
- Parse the riddle literally — what do the words actually say?
- Identify metaphors, double meanings, homophones.
- Consider: "What has..." questions usually have non-obvious subjects.
- If stuck: list 10 possible answers, then eliminate.
- Use web_search as a last resort (not cheating if the game allows it).

### Strategy / Board Games
- Evaluate positions by material, tempo, and control.
- Think N moves ahead (depth-limited search with evaluation function).
- Prioritize moves that increase your options while reducing opponent's.
- In combinatorial games: look for Nim-values, Sprague-Grundy theory.

---

## Using `state_diff` for Game Tracking

Track game progress efficiently:

```
# After each move, snapshot the game state:
state_diff(key="game", content="Turn 3: Score 150, Position (3,7), Inventory: [key, torch]")

# The diff shows exactly what changed:
# -Turn 2: Score 100, Position (2,5), Inventory: [key]
# +Turn 3: Score 150, Position (3,7), Inventory: [key, torch]
```

**Recommended state keys:**
- `"game"` — overall game state summary
- `"map"` — spatial/graph state (for exploration games)
- `"inventory"` — items, resources, scores
- `"strategy"` — current plan and remaining steps

---

## Meta-Strategies

### When You're Stuck
1. **Re-read the rules.** You probably missed something.
2. **List all available actions** — is there one you haven't tried?
3. **Work backwards** from the goal. What state do you need to reach? What leads there?
4. **Try the opposite** of what seems natural. Many puzzles are counter-intuitive.
5. **Brute force.** If the search space is small enough, just try everything.

### When Speed Matters
1. **Don't explore everything** — go straight for the goal once you see the path.
2. **Use scripts** to automate repetitive calculations.
3. **Memoize** — if you've computed something before, don't recompute it.
4. **Parallelize** — if the game allows, spawn sub-agents for independent subtasks.

### Scoring Optimization
1. **Understand the scoring function** before playing.
2. **Collect all optional bonuses** if they're on the critical path.
3. **Minimize penalty actions** (wrong guesses, backtracking, hint usage).
4. **Time bonuses** — if the game rewards speed, use bash scripts for instant computation.
