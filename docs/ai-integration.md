# AI & LLM Integration

Fluxio is designed from the ground up so an **LLM inside a chatbot** (even small local quantized models) can generate rich, interactive visualizations in a few lines of Python with zero hallucinations.

## Built-in Runtime Context (`fx.llm_context`)

When embedding Python inside your chatbot application (e.g. Flutter + Python backend), inject Fluxio's prompt reference directly at runtime without network calls:

```python
import fluxio as fx

# 1. Ultra-lightweight .pyi type signatures only (~450 tokens)
stub_prompt = fx.llm_context("stub")

# 2. Compact LLM guide + rules + API signatures (~750 tokens, recommended default)
system_addon = fx.llm_context("compact")

# 3. Specific chart documentation page on demand (for tool-use / RAG)
number_doc = fx.llm_context(chart="number")

# 4. Complete documentation bundle (llms-full.txt)
full_doc = fx.llm_context("full")
```

## Static Files for AI Agents & RAG

At the root of the repository (and served by MkDocs), Fluxio maintains auto-synchronized files generated via `uv run python -m fluxio.ai_docs`:

- **[`llms.txt`](llms.txt)**: Concise index, golden rules for LLM code generation, and condensed `.pyi` signatures.
- **[`llms-full.txt`](llms-full.txt)**: Full concatenation of all documentation pages and examples in clean Markdown.
- **[`fluxio.pyi`](fluxio.pyi)**: Condensed PEP 484 type stub covering 100% of the public API.
