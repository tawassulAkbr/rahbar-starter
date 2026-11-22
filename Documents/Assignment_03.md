![][image1]**National University ![][image2]o f C o m p u t e r & E m e r g i n g S c i e n c e s , I s l a m a b a d** 

**Department of Software Engineering** 

**(Software Construction and Development, CS4032)** 

**Assignment 03 \- RAGOps** 

**Semester: Fall 26 (CS4032)** 

**Section: All** 

**Group size:** 2 students 

**Marks:** 185 

**Reference paper:** Xu, Weytjens, Zhang, Lu, Weber and Zhu, *RAGOps: Operating and Managing Retrieval Augmented Generation Pipelines* (preprint, 2026). 

**Instructions** 

Read the instructions very carefully. 

Late submissions will receive zero marks. 

Plagiarism may result in zero marks in the whole assignments category (all assignments) regardless of the percentage plagiarized. 

There will be no credit if the given requirements are changed. 

**This is a group assignment. Both members must be able to explain every part of the work at the demo.** 

**AI tools and libraries are allowed. Every number in your report must come from runs of your own pipeline, and the result files must be committed to your repository.** 

**The pipeline must be deployed on Kubernetes during the demo. If it is run on Docker containers only (for example plain docker run or Docker Compose), the demo will receive 0\.** You will build on your RAHBAR pipeline from Assignment 02\. If your group has a different working RAG pipeline (document ingestion, a vector store, a retriever and an LLM generator), you may use it instead. The pipeline must run on Kubernetes (minikube is fine) for Part F. 

Read the paper before you start. Sections 3.2, 4.2, Table 1, Table 2, 5.1 and 6.2 matter most. Figure 3 is the map of this assignment. 

**Submission Guidelines** 

Repository: the URL of your group's GitHub repository. Commits must come from both members. Report: one PDF, at most 8 pages, with the screenshots listed under Submission added as an appendix (the appendix does not count towards the 8 pages). The first page lists the names and roll numbers of 

Page \| 1  
both members. 

Results: all result files, trace samples and reports produced by your scripts are committed under eval/results/ and traces/. All Kubernetes manifests are committed under k8s/. README: the repository README gives the exact command to run each part (A to F). Demo: both members attend and bring a laptop with the pipeline running on your local Kubernetes cluster. Running only on Docker containers gives 0 for the demo. During the demo you will run your evaluation as a Kubernetes Job, open a trace, and ingest a small batch of documents you have not seen by running your ingestion Job. 

**Tasks Overview** 

The paper argues that a RAG system needs two intertwined lifecycles: the usual software lifecycle for the query pipeline, and a data management lifecycle (ingest, verify, update the data lake, update the retrieval sources) that is tested against its own evolving data. Your task is to add this "RAGOps layer" to your pipeline. You will verify and update the data, test the pipeline at three levels, gate a pipeline change behind those tests, trace and monitor every query, and check that your tests still match real usage. All of this runs on Kubernetes: ingestion and evaluation are Jobs, the data and results live on persistent volumes, thresholds are ConfigMaps, and a pipeline change is released with a controlled rollout. 

**Deliverable** 

**Part A: Data management: verify and update** (paper 4.2.1 to 4.2.4) 

**A1. Verification stage.** Add a step that runs after ingestion and before chunking. For every document it records pass or fail, with a reason, for each of four checks: quality (empty, garbled or failed extraction), completeness (required metadata present: source, title, date or version, page count; text not truncated), recency (a newer version of the same document is detected), and uniqueness (exact duplicates by hash, near-duplicates by embedding similarity). 

Documents that fail are moved to a quarantine folder and are not indexed. The output is a verification report file per run. 

**A2. Incremental update.** Re-running ingestion on an unchanged corpus must embed zero chunks (show the counts). A changed document replaces only its own chunks. A deleted document leaves no orphan chunks in the vector store (prove it with a count by document id). A superseded version is archived and excluded from retrieval through metadata, and you can restore it (rollback demo). 

**Batch B.** Create a second batch of at least 10 documents with planted problems: at least 2 exact duplicates, 1 near-duplicate, 1 truncated or corrupt file, 1 with missing metadata, 1 newer version of an existing document, and 1 containing an injected instruction. Run both batches through A1 and A2. 

**Part B: Offline testing at three levels** (paper 4.2.5, Table 1\) 

**Golden set.** At least 25 questions in eval/golden.jsonl: at least 15 answerable (with ground-truth document and page), at least 5 unanswerable (the correct behaviour is to abstain), and at least 5 hard (paraphrased, or needing more than one chunk, or from Batch B). At least 8 questions are written by hand by the group. Each question is labelled human or synthetic, and at least 8 synthetic questions are reviewed by hand. 

Page \| 2  
**Module level (embedding).** Mean cosine similarity for at least 15 paraphrase pairs against at least 15 unrelated pairs, and the gap between them. Embedding time per chunk. Determinism: embed the same text twice and report the largest difference. 

**Component level (retrieval).** recall@3, recall@5, MRR and nDCG@5 on the golden set. Then a noise test: add at least 3 irrelevant documents, or add typos to the queries, and report how each metric changes. 

**End-to-end level (answers).** Faithfulness (is the answer supported by the retrieved context), abstention correctness on the unanswerable questions, citation validity, and latency p50 and p95. If you use an LLM as the judge for faithfulness, label at least 8 answers by hand and report how often the judge agrees with you. 

**Stochasticity.** Fix random seeds and run the whole suite twice. Report the difference for each metric and explain any remaining variation. 

One command runs the whole suite and writes a timestamped result file to eval/results/ with a summary table. 

**Part C: Change experiment and release gate** (paper 4.1 (d), 4.2.5, 4.2.6) 

**C1. One change.** Choose one pipeline change: chunk size or overlap, embedding model, reranker, top-k, or prompt template. Run the Part B suite on the baseline and on the candidate and compare all three levels. 

**C2. Release gate.** Write thresholds in a config file (for example: recall@5 may not drop by more than 2 points against the baseline, faithfulness at least a value you justify, p95 latency at most a value you justify, abstention correctness not lower than the baseline). A script applies the gate and exits with pass or fail. Show one candidate that fails (a deliberately bad one is fine) and one that passes. 

**C3. Roll-out.** The candidate is released and, if needed, rolled back on Kubernetes. See F3. 

**Part D: Observability and traceability** (paper 3.2.3, 5.1, Table 2\) 

**D1. Trace record.** Every query writes one JSON line containing: trace id, timestamp, user query, any rewritten query, embedding model and version, collection name or version, retrieved chunk ids with document ids, document versions and scores, filters applied, reranked order, a prompt hash (or the full prompt), model and parameters, response, citations, guardrail actions, latency per stage, and cache hit or miss. 

**D2. Trace tool.** A command takes a trace id and prints the exact context and prompt that produced that answer. 

**D3. Metrics.** Expose or report at least: top-1 retrieval similarity distribution, abstention rate, cache hit rate, p95 latency per stage, and number of injection attempts flagged. A script summarizes the trace log over a time window. 

**D4. Guardrail logging.** The injection defence you built in Assignment 02 (or one simple retrieval rail of your choice) writes its action into the trace. Test it with the injected document from Batch B. **D5. Root cause from the trace only.** Pick one wrong or abstained answer from Part B. Using only its trace, find the cause (which chunk, document version or filter), and write 5 lines in the report. 

Page \| 3  
**Part E: Drift and coverage checking** (paper 4.2.7) 

**E1. Live query log.** Create at least 40 queries as if from users: about 28 in the domain of your golden set and at least 12 from a topic your corpus or tests do not cover. 

**E2. Query coverage.** For each live query find the most similar golden question. Report the share above a similarity threshold you choose and justify (the paper's example flags a gap when under 85 percent reach a score). List the uncovered queries and group them into topics. 

**E3. Data drift.** Ingest Batch B, re-run the Part B suite, and report what changed and why. **E4. Close the gap.** Add at least 6 new golden questions from the uncovered topics, re-run, and show that coverage rises. A script returns a non-zero exit code when coverage falls below your threshold. 

**Part F: Run it on Kubernetes** (paper 4.1 (e) and (f), 5.1 reliability) 

**F1. Deploy.** The API runs as a Deployment, the vector store as a StatefulSet (or a Deployment with a PersistentVolumeClaim), and a Service exposes the API. The data lake, quarantine folder and archived document versions live on a PersistentVolumeClaim, so they survive pod restarts. 

**F2. Jobs.** Ingestion with verification (Part A) runs as a Kubernetes Job, and a CronJob re-runs it on a schedule. The only writer to the vector store is that Job. The Part B suite runs as a Job (kubectl apply \-f k8s/eval-job.yaml), writes its result file to a volume, and exits with a failing status when the release gate (C2) fails. The gate thresholds (C2) are a ConfigMap, and you show that changing a threshold changes the outcome without rebuilding the image. 

**F3. Controlled release.** The candidate from Part C runs as a second Deployment with its own Service and its own collection name, and the Part B suite Job is run against it. If the gate passes, release it to the live Deployment with a rolling update (maxUnavailable: 0), watched with kubectl rollout status. Show a candidate that is stopped by the gate and never rolled out, and a bad release that you reverse with kubectl rollout undo. After the undo, a new trace must show the previous collection and embedding version. 

**F4. Observability on the cluster.** Trace records go to standard output as JSON lines and are readable with kubectl logs. They are also written to a volume for the report scripts. The metrics endpoint is reachable with kubectl port-forward. 

**F5. Resources.** Set resource requests and limits for the API, the vector store and the Jobs, from measurements you take (copy the numbers into the report). 

Every manifest is committed under k8s/. A fresh cluster must reach a working pipeline by applying them, with any extra commands listed in a k8s/README.md. 

**Part G: Report** (8 pages at most) 

1\. A table that maps each stage of Figure 3 (ingest, verify, update data lake, update retrieval sources, offline testing, live testing, check coverage) to what your pipeline does, the file that does it, and what is missing. 

2\. A table for the five qualities in the paper's Table 2 (adaptability, monitorability, observability, traceability, reliability): what you measure, your threshold, and the evidence. 

3\. Your results tables and figures from Parts A to F, and the release decision for Part C (release or reject, with reasons). 

Page \| 4  
4\. Short answers: (a) Which verification check caught the most problems in Batch B, and which problem did you not catch? What would catch it? (b) Give an example from your results where a module-level metric looked fine but a component or end-to-end metric did not, or explain why you did not see one. (c) Did you archive or delete old versions, and what breaks if you delete? (d) Which metric in your suite do you trust least, and why? (e) Which of the paper's ideas was hardest to apply to your pipeline, and what did you change from the paper? (f) Which Kubernetes object carries which RAGOps responsibility in your design (for example, which object makes sure only one component writes to the vector store)? 

5\. A contribution table (what each member did) and an AI statement of 2 to 3 lines. 

**Submission** 

Submit two things: the GitHub repository and the report PDF with screenshots. 

**1\. GitHub repository** 

The URL of your group's repository, containing the code, k8s/, eval/ (golden set and result files), traces/, the configuration files and a README with the command for each part. 

**2\. Screenshots (appendix of the report)** 

Each screenshot shows the command you ran and its output, in the terminal, with nothing cropped. Label it with the part and item (for example "B3"). Screenshots must come from your own cluster and your own runs. 

**A:** the verification report for Batch B (pass or fail per check, with reasons); a second ingestion run on an unchanged corpus showing 0 chunks embedded. 

**B:** the evaluation summary with all three levels. 

**C:** the release gate failing and the release gate passing. 

**D:** one full trace record; the trace tool rebuilding the prompt for a trace id. 

**E:** the coverage output before and after adding the new questions. 

**F:** kubectl get all,pvc,configmap,cronjob,job for your namespace; the logs of a completed ingestion Job and a completed evaluation Job; the gate result changing after a ConfigMap edit; kubectl rollout status and kubectl rollout undo with a trace afterwards showing the previous collection and embedding version. 

**Best of Luck ☺** 

Page \| 5

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>