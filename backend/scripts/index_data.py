# backend/scripts/index_data.py

import sys
sys.path.append('..')

from core.elasticsearch_client import ElasticsearchClient
from core.data_loader import SyntheaDataLoader
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Initialize clients
    logger.info("Initializing...")
    es_client = ElasticsearchClient()
    data_loader = SyntheaDataLoader("../../data/raw/csv")
    
    # Create indices
    logger.info("Creating indices...")
    es_client.create_indices()
    
    # Load and process data
    logger.info("Loading Synthea data...")
    documents = data_loader.process_for_elasticsearch()
    logger.info(f"Loaded {len(documents)} documents")
    
    # Take first 1000 for demo (to save on API costs)
    documents = documents[:1000]
    
    # Add embeddings
    logger.info("Generating embeddings (this may take a few minutes)...")
    documents = es_client.add_embeddings_to_documents(documents)
    
    # Index documents
    logger.info("Indexing documents...")
    success, failed = es_client.index_documents("lab-results", documents)
    
    logger.info(f"✅ Successfully indexed {success} documents")
    logger.info(f"❌ Failed: {len(failed)}")
    
    # Verify
    count = es_client.client.count(index="lab-results")
    logger.info(f"Total documents in index: {count['count']}")

if __name__ == "__main__":
    main()