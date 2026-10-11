# Project Proposal

Dokumen ini mempertahankan rancangan dan target awal Kuping Negara. Arsitektur,
metrik, jadwal, dan layanan yang diusulkan belum seluruhnya diimplementasikan.
Lihat [README](../README.md) untuk kemampuan yang tersedia dan
[roadmap](roadmap.md) untuk pekerjaan berikutnya.

## Executive Summary

Percakapan mengenai program publik di social media berubah dengan cepat dan
mengandung variasi bahasa, konteks, sarkasme, spam, serta bias sampling. Analisis
sentimen yang hanya dilakukan sebagai eksperimen notebook tidak cukup karena
hasilnya sulit direproduksi, tidak memiliki data lineage, dan akan mengalami
degradasi ketika distribusi data berubah.

Proposal Kuping Negara menggunakan MLOps practices untuk mengelola keseluruhan
lifecycle: scheduled ingestion, immutable raw storage, schema validation,
preprocessing, manual annotation, experiment tracking, model registry,
controlled deployment, observability, dan retraining. Output sistem ditujukan
sebagai decision-support signal, bukan survei opini publik atau ukuran resmi
keberhasilan kebijakan.

## Project Proposal

### Background

Empat program yang menjadi initial monitoring scope adalah:

| Program ID | Program | Initial Collection Schedule |
| --- | --- | --- |
| `mbg` | Makan Bergizi Gratis | Monday |
| `ckg` | Cek Kesehatan Gratis | Tuesday |
| `kopdes_merah_putih` | Koperasi Desa Merah Putih | Wednesday |
| `sekolah_rakyat` | Sekolah Rakyat | Thursday |

Initial labeling dan data quality review direncanakan setiap Friday. Seluruh
scheduling menggunakan timezone `Asia/Jakarta`. Jadwal ini merupakan operating
proposal dan akan dievaluasi kembali berdasarkan volume data, rate limit,
latency, serta biaya operasional.

### Problem Statement

Project ini menjawab lima technical problems utama:

1. **Data freshness**: data harus dikumpulkan secara periodik tanpa menghasilkan
   duplicate record atau kehilangan run history.
2. **Data reliability**: source schema, volume, bahasa, dan kualitas teks dapat
   berubah tanpa pemberitahuan.
3. **Model reliability**: vocabulary drift, topic drift, dan sentiment drift
   dapat menurunkan performa model setelah deployment.
4. **Traceability**: prediction harus dapat ditelusuri ke source record,
   preprocessing version, dataset version, model version, dan code revision.
5. **Interpretability**: stakeholder membutuhkan trend, confidence, coverage,
   dan limitations yang dapat dipahami, bukan hanya sebuah class label.

### Research Questions

- Bagaimana membangun sentiment classification pipeline yang reproducible untuk
  Bahasa Indonesia dan percakapan social media yang dinamis?
- Seberapa baik baseline model dibandingkan Indonesian pretrained language
  model pada Macro-F1, per-class recall, calibration, dan inference cost?
- Monitoring signal apa yang paling efektif untuk mendeteksi degradation akibat
  data drift, concept drift, dan source schema change?
- Bagaimana menampilkan aggregate sentiment tanpa menghilangkan uncertainty dan
  tanpa menggeneralisasikan pengguna X sebagai seluruh masyarakat Indonesia?

### Objectives

#### Primary Objectives

- Menghasilkan weekly, versioned, dan quality-checked dataset untuk setiap
  target program.
- Mengembangkan three-class sentiment classifier dengan target Macro-F1 minimum
  `0.75` pada representative holdout set.
- Menyediakan batch inference dan online inference contract yang menyertakan
  class probabilities, confidence, dan model version.
- Menyediakan observability untuk data, model, pipeline, dan serving layer.
- Menetapkan controlled retraining dan rollback process yang dapat diaudit.

#### Engineering Objectives

- Menjaga source code modular di bawah satu Python namespace.
- Menjalankan environment yang konsisten melalui GitHub Codespaces/Dev
  Containers.
- Menggunakan automated tests dan CI sebagai minimum merge gate.
- Menjaga secrets, raw datasets, dan model binaries di luar Git history.
- Mendokumentasikan ownership, naming convention, code placement, dan Git
  workflow untuk contributor baru.

### Stakeholders and Use Cases

| Stakeholder | Primary Use Case | Expected Output |
| --- | --- | --- |
| Researcher/data analyst | Menganalisis perubahan discourse per program dan periode | Versioned dataset, trend, uncertainty |
| ML engineer | Melatih, membandingkan, dan mendaftarkan model | Metrics, artifacts, lineage, model card |
| Data engineer | Mengoperasikan ingestion dan validation pipeline | Run status, freshness, data quality report |
| Policy communication team | Memahami issue dan aggregate public response | Filtered dashboard dan explainable summary |
| Project maintainer | Menjaga quality, security, dan release process | CI status, PR review, rollback path |

### System Scope

#### In Scope

- Public posts yang diperoleh melalui collection method yang diizinkan.
- Program-specific keyword configuration dan scheduled collection.
- Raw, processed, dan labeled data zones.
- Bahasa Indonesia sebagai primary language; language detection tetap direkam.
- Manual annotation dengan `positive`, `neutral`, `negative`, dan temporary
  `uncertain` label untuk adjudication.
- Baseline model, transformer experiment, batch inference, REST API contract,
  dashboard, monitoring, serta retraining workflow.

#### Out of Scope

- Private messages, restricted data, atau bypass terhadap access control.
- Individual profiling, identity resolution, dan automated decision tentang
  seseorang.
- Causal inference mengenai keberhasilan program pemerintah.
- Klaim bahwa pengguna X merepresentasikan seluruh populasi Indonesia.
- Production deployment sebelum security, privacy, reliability, dan cost review.

### Key Deliverables

1. Reproducible development environment dan repository standard.
2. Config-driven ingestion pipeline dengan immutable raw zone.
3. Versioned data contract, validation report, dan preprocessing pipeline.
4. Annotation guideline, labeled dataset, serta inter-annotator agreement report.
5. Baseline dan candidate model comparison beserta experiment lineage.
6. Model registry, promotion gate, inference service, dan rollback procedure.
7. Monitoring dashboard untuk data quality, model quality, service health, dan
   pipeline health.
8. Technical documentation, operational runbook, dan assessment evidence.

## Functional and Non-Functional Requirements

### Functional Requirements

| ID | Requirement |
| --- | --- |
| `FR-01` | Sistem menerima keyword configuration per target program. |
| `FR-02` | Ingestion run menyimpan record secara append-only dan idempotent. |
| `FR-03` | Invalid record dikarantina dan dilaporkan sebelum processed zone. |
| `FR-04` | Preprocessing melakukan cleaning, normalization, anonymization, dan deduplication. |
| `FR-05` | Training pipeline merekam dataset, parameters, metrics, artifact, dan code version. |
| `FR-06` | Inference menghasilkan sentiment, probabilities, confidence, program, dan model version. |
| `FR-07` | Dashboard mendukung filter berdasarkan program dan time window. |
| `FR-08` | Monitoring mendeteksi data quality issue, drift, stale data, dan service failure. |

### Non-Functional Requirements

| Attribute | Initial Target |
| --- | --- |
| Reproducibility | Environment dan dependency dapat dibuat ulang dari repository. |
| Traceability | Prediction memiliki reference ke data/model/schema/run version. |
| Reliability | Scheduled pipeline success rate minimal `95%`. |
| Maintainability | Modular package, documented boundaries, automated tests, reviewed PR. |
| Security | Secrets tidak masuk Git; least-privilege access diterapkan pada runtime. |
| Privacy | Personal identifier diminimalkan sebelum downstream processing. |
| Observability | Structured logs, metrics, run status, dan alert context tersedia. |
| Recoverability | Model promotion memiliki previous-version rollback path. |

## Solution Architecture

```mermaid
flowchart LR
    SRC[Public X Posts] --> ING[Scheduled Ingestion]
    CFG[Keyword Config] --> ING
    ING --> RAW[(Raw Zone<br/>Append-only)]
    RAW --> VAL[Schema & Quality Validation]
    VAL -->|Valid| PRE[Cleaning, Normalization,<br/>Anonymization, Deduplication]
    VAL -->|Invalid| QUA[(Quarantine)]
    PRE --> PRO[(Processed Zone)]
    PRO --> LAB[Manual Annotation]
    LAB --> LBL[(Labeled Zone)]
    LBL --> TRN[Training & Evaluation]
    TRN --> EXP[(Experiment Tracking)]
    TRN --> REG[(Model Registry)]
    REG --> INF[Batch / Online Inference]
    INF --> API[FastAPI Contract]
    API --> DASH[Streamlit Dashboard]
    PRO --> MON[Data Monitoring]
    INF --> MON
    API --> MON
    MON --> RET{Retraining Trigger}
    RET -->|Approved| TRN
```

Design principles:

- Raw data is immutable; corrections produce a new version.
- Pipeline stage communicates through explicit data contracts.
- DAG hanya mengatur orchestration dan tidak menyimpan business logic.
- Notebook hanya digunakan untuk exploration; reusable logic dipindahkan ke
  `src/kuping_negara/`.
- API dan dashboard menggunakan inference/service interface, bukan mengakses
  training internals.
- Model promotion membutuhkan evaluation evidence dan human approval.

## Data Strategy

### Data Zones

| Zone | Purpose | Storage Rule |
| --- | --- | --- |
| `raw` | Source-aligned ingestion output | Append-only, immutable, audit metadata required |
| `processed` | Cleaned, anonymized, normalized, deduplicated records | Must pass schema and quality gates |
| `labeled` | Annotated training/evaluation samples | Annotation guideline version required |
| `quarantine` | Invalid or suspicious records | Excluded until reviewed; planned storage |

Dataset contents are not committed to Git. The directories retain only
`.gitkeep`; large/versioned artifacts will use object storage and DVC or an
equivalent dataset registry.

### Data Contract

The initial JSON Schema is stored at
[`configs/schemas/tweet_record.schema.json`](../configs/schemas/tweet_record.schema.json).
The main field groups are:

- identity: `tweet_id`, `conversation_id`, `tweet_url`;
- collection context: `target_program`, `matched_keyword`;
- text: `raw_text`, `cleaned_text`, `language`;
- temporal: `published_at`, `collected_at`, `year_week`, `year_month`;
- engagement: reply, repost/retweet, like, dan quote counts;
- annotation/inference: label, prediction, class probabilities, confidence;
- lineage: `ingestion_run_id`, `data_version`, `model_version`,
  `schema_version`.

### Data Quality Gates

- Required fields, data types, enum values, dan timestamp format valid.
- `tweet_id` uniqueness dan duplicate rate berada dalam accepted threshold.
- Probability value berada pada interval `[0, 1]`.
- Empty text, unsupported language, spam, dan anomalous volume dilaporkan.
- Source schema change menghasilkan explicit failure atau quarantine, bukan
  silent corruption.
- Personally identifiable information diminimalkan sebelum downstream use.

## Machine Learning Strategy

### Task Definition

Supervised multi-class text classification:

- `positive`: support, benefit, praise, atau positive experience terhadap
  target program;
- `neutral`: factual statement, announcement, question, atau tidak ada
  evaluative stance yang dominan;
- `negative`: criticism, rejection, complaint, atau negative experience;
- `uncertain`: temporary annotation state untuk ambiguity/adjudication dan
  tidak digunakan langsung sebagai target three-class training.

Full decision rules tersedia pada
[`docs/annotation-guidelines.md`](annotation-guidelines.md).

### Experiment Plan

1. Build interpretable baseline menggunakan TF-IDF dan linear classifier.
2. Gunakan time-aware dan conversation-aware split untuk mengurangi leakage.
3. Ukur Macro-F1, per-class precision/recall/F1, confusion matrix, calibration,
   inference latency, dan model size.
4. Bandingkan baseline dengan IndoBERT/IndoBERTweet candidate.
5. Lakukan slice evaluation per program, period, dan language condition.
6. Simpan parameter, metric, artifact, dataset version, schema version, serta
   commit SHA di experiment tracker.
7. Register hanya candidate yang memenuhi quality gate dan documented review.

### Initial Model Acceptance Criteria

- Macro-F1 minimum `0.75` pada representative holdout set.
- Tidak ada critical class dengan recall yang berada di bawah threshold yang
  disepakati pada model review.
- Evaluation bebas known data leakage.
- Prediction contract menyertakan calibrated confidence atau limitation note.
- Model card, dataset reference, dan rollback artifact tersedia.

## MLOps Lifecycle

```text
Collect → Validate → Process → Label → Train → Evaluate → Register
       → Deploy → Monitor → Approve Retraining → Compare → Promote/Rollback
```

Every stage will produce machine-readable metadata. A model is never promoted
only because a single aggregate metric improves; regression by program,
calibration, operational cost, privacy, dan failure behavior harus ditinjau.

## Technology Stack

| Layer | Candidate Technology | Repository Status |
| --- | --- | --- |
| Language/runtime | Python 3.12+ | Configured |
| Development environment | GitHub Codespaces / Dev Containers | Configured |
| Package management | uv + committed lockfile | Configured |
| Data manipulation | pandas | Installed by project requirements |
| Baseline ML | scikit-learn | Installed by project requirements |
| NLP candidate | IndoBERT / IndoBERTweet | Planned experiment |
| Orchestration | Apache Airflow | Directory prepared |
| Data versioning | DVC + object storage | Planned |
| Experiment tracking | MLflow | Planned |
| API | FastAPI | Package boundary prepared |
| Metadata store | PostgreSQL | Planned |
| Dashboard | Streamlit | Package boundary prepared |
| Monitoring | Prometheus + Grafana | Planned |
| CI | GitHub Actions | Basic workflow configured |

`Planned` means architectural candidate, not an implemented production
component.


## Monitoring and Retraining

| Monitoring Domain | Initial Signals |
| --- | --- |
| Data quality | missing rate, duplicate rate, invalid schema, language mix, volume anomaly |
| Data drift | feature/vocabulary distribution, topic emergence, program distribution |
| Model quality | sampled Macro-F1, per-class recall, confidence, calibration |
| Service | latency, throughput, error rate, timeout, model version |
| Pipeline | success rate, duration, retry, freshness, late/missed schedule |

Retraining is proposed monthly or when approved drift/quality thresholds are
crossed. Candidate model must be compared with the active model and pass review.
Rollback must retain the previous production artifact and configuration.

## Risk Register

| Risk | Impact | Planned Mitigation |
| --- | --- | --- |
| Platform policy or source-access change | Ingestion interruption | Approved adapters, explicit failures, documented fallback |
| Sampling bias | Misleading interpretation | Coverage disclosure, no population-level claim |
| Vocabulary/topic drift | Model degradation | Drift monitoring, audit sampling, scheduled review |
| Annotation disagreement | Noisy ground truth | Versioned guideline, double annotation, adjudication |
| Sensitive information exposure | Privacy/security incident | Data minimization, anonymization, access control, no raw data in Git |
| Data leakage | Inflated evaluation | Time/conversation-aware split and lineage checks |
| Low-confidence prediction | Poor decision support | Probability output, threshold policy, abstention/review path |
| Pipeline silently succeeds with bad data | Corrupted downstream output | Schema gate, quarantine, alerting, run-level metrics |

## Success Metrics

| Category | Metric | Initial Target |
| --- | --- | --- |
| Model | Macro-F1 | `>= 0.75` on representative holdout data |
| Pipeline | Scheduled run success rate | `>= 95%` |
| Freshness | Program data and summary update | Weekly |
| Traceability | Prediction linked to run/data/model/schema version | `100%` |
| Usability | Test users understand primary dashboard insight | `>= 80%` |

These values are acceptance targets, not achieved results. Every report must
include dataset period, sample size, split strategy, label distribution, and
known limitations.


## Ethics, Privacy, and Limitations

- Process only data that may legally and contractually be accessed.
- Follow platform terms, institutional policy, and applicable regulation.
- Minimize or pseudonymize personal identifiers before downstream processing.
- Never commit authentication headers, cookies, tokens, or raw personal data.
- Do not use the system for individual profiling or automated individual action.
- Disclose that X users are not a representative sample of Indonesia.
- Present uncertainty and error; sentiment prediction is not verified fact.
- Maintain audit, correction, rollback, retention, and deletion procedures.
