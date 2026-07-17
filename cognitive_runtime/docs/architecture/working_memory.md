# Working Memory Architecture

## Why Working Memory Exists

Working Memory serves as the "active cognitive workspace" of the RAGE runtime. In cognitive architectures, it acts similarly to a human's short-term attention span—a highly constrained context window where current reasoning, planning, and evaluation take place.

## Separation from Memory and Knowledge

**Memory** is a long-term storage of *experiences* ("What happened?").
**Knowledge** is a persistent, structural representation of *facts* ("What is true?").

In contrast, **Working Memory** is strictly temporary. It is entirely disjoint from persistent storage mechanisms. It does not write to a database, nor does it maintain a historical log. It exists solely to hold references (`reference_id`) to information from Memory, Knowledge, or Goals that are actively being considered by the runtime.

## Why It Remains Intentionally Small

Working Memory enforces a strict capacity limit (default: 20 items). 
This constraint is intentional:
1. **Focus:** By limiting active context, the reasoning engine (and underlying models) are forced to operate on only the most salient information, reducing "hallucinations" and context-bloat.
2. **Performance:** An unbounded working memory would slow down reasoning loops.
3. **Eviction Mechanisms:** The capacity constraint necessitates an Eviction Policy. While Version 0.1 uses Least Recently Used (LRU), future iterations are designed to use Attention, Salience, or Activation Decay mechanisms to selectively "forget" the least relevant information—mimicking human cognition.
