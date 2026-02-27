# backend/tools/knowledge_search.py

"""
Medical Knowledge Search
Searches knowledge base for medical information
"""

from elasticsearch import Elasticsearch
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class KnowledgeSearcher:
    """Search medical knowledge base"""
    
    def __init__(self, es_client: Elasticsearch):
        self.es = es_client
    
    def search(self, query: str, top_k: int = 3) -> Dict:
        """Search knowledge base for medical information"""
        
        search_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["question^3", "answer^2", "keywords"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "size": top_k,
            "_source": ["question", "answer", "test_type", "source", "confidence"]
        }
        
        try:
            response = self.es.search(index="knowledge-base", body=search_query)
            
            if response["hits"]["total"]["value"] == 0:
                return {
                    "status": "no_results",
                    "message": "No relevant information found. Please try rephrasing your question."
                }
            
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "question": source.get("question"),
                    "answer": source.get("answer"),
                    "test_type": source.get("test_type"),
                    "source": source.get("source", "Medical Guidelines"),
                    "confidence": source.get("confidence", 0.8),
                    "relevance_score": hit["_score"]
                })
            
            return {
                "status": "success",
                "query": query,
                "results": results,
                "top_answer": results[0]["answer"] if results else None
            }
        
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return {"status": "error", "message": str(e)}