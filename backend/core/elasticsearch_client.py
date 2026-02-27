"""
Elasticsearch client — enhanced with scoring, kNN, and aggregations
"""

from elasticsearch import Elasticsearch
from typing import Dict, List
import logging
from .config import settings

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


class ElasticsearchClient:

    def __init__(self):
        if not settings.ELASTIC_ENDPOINT or not settings.ELASTIC_API_KEY:
            raise ValueError("Elasticsearch credentials not configured.")

        self.client = Elasticsearch(
            hosts=[settings.ELASTIC_ENDPOINT],
            api_key=settings.ELASTIC_API_KEY,
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True,
        )

        if not self.client.ping():
            raise ConnectionError("Cannot connect to Elasticsearch")

        info = self.client.info()
        logger.info(f"✅ Connected to Elasticsearch {info['version']['number']}")
        self.setup_indices()

    # ══════════════════════════════════════════════════════════
    # Index Setup
    # ══════════════════════════════════════════════════════════

    def setup_indices(self):
        lab_results_mapping = {
            "mappings": {
                "properties": {
                    "patient_id":  {"type": "keyword"},
                    "test_date":   {"type": "date"},
                    "test_type":   {"type": "keyword"},
                    "lab_name":    {"type": "keyword"},
                    "results": {
                        "type": "nested",
                        "properties": {
                            "test_name":     {"type": "keyword"},
                            "value":         {"type": "float"},
                            "unit":          {"type": "keyword"},
                            "reference_min": {"type": "float"},
                            "reference_max": {"type": "float"},
                            "is_abnormal":   {"type": "boolean"},
                            "severity":      {"type": "keyword"},
                            "deviation_pct": {"type": "float"},
                        }
                    },
                    "abnormal_flags": {"type": "keyword"},
                    "critical_flags": {"type": "keyword"},
                    "report_text":    {"type": "text", "analyzer": "english"},
                    "processed_at":   {"type": "date"},
                    "source_file":    {"type": "keyword"},
                    "risk_vector": {
                        "type":       "dense_vector",
                        "dims":       8,
                        "index":      True,
                        "similarity": "cosine",
                    },
                    "risk_score": {"type": "float"},
                    "risk_level": {
                        "type": "text",
                        "fields": {
                            "keyword": {"type": "keyword", "ignore_above": 32}
                        }
                    },
                }
            }
        }

        knowledge_base_mapping = {
            "mappings": {
                "properties": {
                    "question":   {"type": "text"},
                    "answer":     {"type": "text"},
                    "test_type":  {"type": "keyword"},
                    "keywords":   {"type": "keyword"},
                    "source":     {"type": "keyword"},
                    "confidence": {"type": "float"},
                }
            }
        }

        alert_actions_mapping = {
            "mappings": {
                "properties": {
                    "patient_id": {"type": "keyword"},
                    "action":     {"type": "keyword"},
                    "actor":      {"type": "keyword"},
                    "timestamp":  {"type": "date"},
                    "source":     {"type": "keyword"},
                }
            }
        }

        for index_name, mapping in [
            (settings.LAB_RESULTS_INDEX,    lab_results_mapping),
            (settings.KNOWLEDGE_BASE_INDEX,  knowledge_base_mapping),
            ("labiq-alert-actions",          alert_actions_mapping),
        ]:
            if not self.client.indices.exists(index=index_name):
                self.client.indices.create(index=index_name, body=mapping)
                logger.info(f"✅ Created index: {index_name}")
            else:
                logger.info(f"   Index exists: {index_name}")

    # ══════════════════════════════════════════════════════════
    # Basic CRUD
    # ══════════════════════════════════════════════════════════

    def index_document(self, index: str, document: Dict) -> str:
        response = self.client.index(index=index, document=document)
        return response["_id"]

    def search(self, index: str, query: Dict) -> Dict:
        return self.client.search(index=index, body=query)

    def count(self, index: str) -> int:
        return self.client.count(index=index)["count"]

    # ══════════════════════════════════════════════════════════
    # Relevance Scoring — function_score
    # ══════════════════════════════════════════════════════════

    def scored_patient_search(self, patient_id: str) -> List[Dict]:
        query = {
            "query": {
                "function_score": {
                    "query": {"term": {"patient_id": patient_id}},
                    "functions": [
                        {"filter": {"exists": {"field": "critical_flags"}}, "weight": 10},
                        {"filter": {"exists": {"field": "abnormal_flags"}},  "weight": 3},
                        {
                            "field_value_factor": {
                                "field": "risk_score", "factor": 0.1,
                                "modifier": "sqrt", "missing": 0,
                            }
                        },
                        {
                            "gauss": {
                                "test_date": {"origin": "now", "scale": "30d", "decay": 0.5}
                            }
                        },
                    ],
                    "score_mode": "sum",
                    "boost_mode": "multiply",
                }
            },
            "size": 20,
            "_source": True,
        }

        results = self.client.search(index=settings.LAB_RESULTS_INDEX, body=query)
        return [
            {**h["_source"], "_score": round(h["_score"], 3), "_doc_id": h["_id"]}
            for h in results["hits"]["hits"]
        ]

    # ══════════════════════════════════════════════════════════
    # kNN Similarity Search — with per-patient deduplication
    # ══════════════════════════════════════════════════════════

    def find_similar_patients(self, patient_id: str, k: int = 5) -> List[Dict]:
        """
        Find k most similar UNIQUE patients using kNN cosine similarity.

        Time-series aware: each patient may have many documents (one per upload).
        We fetch (k+1)*3 candidates so that after deduplication we still have k
        unique patients. Only the highest-scoring document per patient is kept.
        """
        # Step 1 — Use the patient's most recent upload as the query vector
        anchor = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "query":   {"term": {"patient_id": patient_id}},
                "size":    1,
                "_source": ["risk_vector"],
                "sort":    [{"test_date": "desc"}],
            }
        )

        hits = anchor["hits"]["hits"]
        if not hits or "risk_vector" not in hits[0].get("_source", {}):
            logger.warning(f"No risk_vector found for {patient_id}")
            return []

        query_vector = hits[0]["_source"]["risk_vector"]

        # Step 2 — Fetch extra candidates to survive deduplication
        fetch_size = (k + 1) * 3
        knn_results = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "knn": {
                    "field":          "risk_vector",
                    "query_vector":   query_vector,
                    "k":              fetch_size,
                    "num_candidates": max(50, fetch_size * 2),
                },
                "_source": ["patient_id", "risk_score", "risk_level",
                            "critical_flags", "abnormal_flags", "test_date"],
                "size": fetch_size,
            }
        )

        # Step 3 — Deduplicate: one result per unique patient_id (best score wins
        # because kNN results are already sorted by cosine similarity descending)
        seen: set   = set()
        similar: list = []

        for h in knn_results["hits"]["hits"]:
            src = h["_source"]
            pid = src.get("patient_id", "")

            if pid == patient_id or pid in seen:
                continue  # skip self and duplicates

            seen.add(pid)
            similar.append({
                "patient_id":     pid,
                "similarity":     round(h["_score"], 3),
                "risk_score":     src.get("risk_score", 0),
                "risk_level":     src.get("risk_level", "UNKNOWN"),
                "critical_flags": src.get("critical_flags", []) or [],
                "abnormal_flags": src.get("abnormal_flags", []) or [],
                "test_date":      src.get("test_date", "")[:10],
            })

            if len(similar) >= k:
                break

        logger.info(f"kNN [{patient_id}] → {[s['patient_id'] for s in similar]}")
        return similar

    # ══════════════════════════════════════════════════════════
    # Aggregations — population statistics
    # ══════════════════════════════════════════════════════════

    def population_stats(self) -> Dict:
        result = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "size": 0,
                "aggs": {
                    "risk_percentiles": {
                        "percentiles": {
                            "field":    "risk_score",
                            "percents": [25, 50, 75, 90, 95, 99],
                        }
                    },
                    "by_risk_level": {"terms": {"field": "risk_level.keyword"}},
                    "avg_risk":      {"avg":   {"field": "risk_score"}},
                    "has_criticals": {"filter": {"exists": {"field": "critical_flags"}}},
                    "tests_over_time": {
                        "date_histogram": {
                            "field": "test_date", "calendar_interval": "month",
                        }
                    },
                }
            }
        )

        aggs = result["aggregations"]
        return {
            "risk_percentiles":        aggs["risk_percentiles"]["values"],
            "by_risk_level":           {b["key"]: b["doc_count"]
                                        for b in aggs["by_risk_level"]["buckets"]},
            "avg_risk_score":          round(aggs["avg_risk"]["value"] or 0, 1),
            "patients_with_criticals": aggs["has_criticals"]["doc_count"],
            "tests_over_time":         [
                {"month": b["key_as_string"], "count": b["doc_count"]}
                for b in aggs["tests_over_time"]["buckets"]
            ],
        }

    def patient_percentile(self, patient_id: str) -> Dict:
        """
        Computes percentile rank using each patient's PEAK (max) risk score.
        Time-series safe: multiple docs per patient collapse to one score via max agg.
        """
        result = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "query": {"term": {"patient_id": patient_id}},
                "size":  0,
                "aggs":  {"max_risk": {"max": {"field": "risk_score"}}},
            }
        )

        if result["hits"]["total"]["value"] == 0:
            logger.warning(f"No documents for patient_id={patient_id}")
            return {}

        score = result["aggregations"]["max_risk"]["value"] or 0

        # Get max risk score per patient across entire population
        pop = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "size": 0,
                "aggs": {
                    "by_patient": {
                        "terms": {"field": "patient_id", "size": 1000},
                        "aggs":  {"max_risk": {"max": {"field": "risk_score"}}}
                    }
                }
            }
        )

        all_scores = [b["max_risk"]["value"] or 0
                      for b in pop["aggregations"]["by_patient"]["buckets"]]
        total      = len(all_scores)
        lower      = sum(1 for s in all_scores if s < score)
        percentile = round((lower / max(total, 1)) * 100, 1)

        return {
            "patient_id":     patient_id,
            "risk_score":     score,
            "percentile":     percentile,
            "total_patients": total,
            "interpretation": (
                f"Peak risk score {score}/100 — higher than "
                f"{percentile}% of {total} patients."
            ),
        }

    def trending_biomarkers(self, patient_id: str, test_name: str) -> List[Dict]:
        result = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "query": {"term": {"patient_id": patient_id}},
                "size":  0,
                "aggs": {
                    "over_time": {
                        "date_histogram": {
                            "field": "test_date", "calendar_interval": "week",
                        },
                        "aggs": {
                            "biomarker_values": {
                                "nested": {"path": "results"},
                                "aggs": {
                                    "filtered": {
                                        "filter": {"term": {"results.test_name": test_name}},
                                        "aggs": {
                                            "avg_value": {"avg": {"field": "results.value"}},
                                            "max_value": {"max": {"field": "results.value"}},
                                            "min_value": {"min": {"field": "results.value"}},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        )

        trend = []
        for b in result["aggregations"]["over_time"]["buckets"]:
            f   = b["biomarker_values"]["filtered"]
            avg = f["avg_value"]["value"]
            if avg is not None:
                trend.append({
                    "date":      b["key_as_string"][:10],
                    "avg":       round(avg, 2),
                    "max":       round(f["max_value"]["value"] or avg, 2),
                    "min":       round(f["min_value"]["value"] or avg, 2),
                    "doc_count": b["doc_count"],
                })
        return trend

    # ══════════════════════════════════════════════════════════
    # Risk Trend — recovery timeline across uploads
    # ══════════════════════════════════════════════════════════

    def patient_risk_trend(self, patient_id: str) -> List[Dict]:
        """
        Returns one data point per uploaded document (lab visit), sorted oldest→newest.
        This is the patient's recovery/deterioration timeline over time.
        Each document in ES = one real-world lab visit.
        """
        result = self.client.search(
            index=settings.LAB_RESULTS_INDEX,
            body={
                "query":   {"term": {"patient_id": patient_id}},
                "sort":    [{"test_date": "asc"}],
                "size":    50,
                "_source": ["test_date", "risk_score", "risk_level",
                            "critical_flags", "abnormal_flags", "test_type"],
            }
        )

        points = []
        for h in result["hits"]["hits"]:
            src = h["_source"]
            points.append({
                "date":       src.get("test_date", "")[:10],
                "risk_score": src.get("risk_score", 0),
                "risk_level": src.get("risk_level", "LOW"),
                "critical":   len(src.get("critical_flags", []) or []),
                "abnormal":   len(src.get("abnormal_flags", []) or []),
                "test_type":  src.get("test_type", ""),
            })

        return points


# ── Singleton ──────────────────────────────────────────────────
_es_client = None

def get_es_client() -> ElasticsearchClient:
    global _es_client
    if _es_client is None:
        _es_client = ElasticsearchClient()
    return _es_client