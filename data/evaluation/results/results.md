# Evaluation results

## Configuration

- embedding_model: `BAAI/bge-small-en-v1.5`
- retrieval: `hybrid BM25 + vector (RRF)`
- vector_store: `ChromaDB (persistent, per-document collection)`
- llm_provider: `local`
- indexed_chunks: `11`

## Entity extraction (vs. ground truth)

| Entity type | Expected | Extracted | Precision | Recall |
|---|---|---|---|---|
| component | 4 | 4 | 1.0 | 1.0 |
| interface | 3 | 3 | 1.0 | 1.0 |
| port | 6 | 6 | 1.0 | 1.0 |
| signal | 3 | 3 | 1.0 | 1.0 |
| dependency | 6 | 6 | 1.0 | 1.0 |
| functional_flow | 3 | 3 | 1.0 | 1.0 |
| **overall** | | | **1.0** | **1.0** |

## Question answering

- Questions: 32
- Overall accuracy: 0.906
- Accuracy on answerable questions: 0.885
- Citation on expected page: 0.885
- Groundedness (answers with valid citations): 1.0
- Refusal accuracy on unanswerable questions: 1.0
- By category: {'lookup': '15/15', 'paraphrase': '2/5', 'flow': '3/3', 'datatype': '2/2', 'integration': '1/1', 'unanswerable': '6/6'}

### Failures

- Q16 Who is responsible for publishing door state information? -> 'The requested information was not found in the document.'
- Q19 How does the window controller learn the requested window position? -> 'The requested information was not found in the document.'
- Q20 What safety-related constraint depends on speed? -> 'The requested information was not found in the document.'
