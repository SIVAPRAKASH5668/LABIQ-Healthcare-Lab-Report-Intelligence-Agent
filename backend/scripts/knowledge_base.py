# backend/scripts/create_knowledge_base.py

import sys
sys.path.append('..')

from core.elasticsearch_client import ElasticsearchClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Medical Q&A pairs
QA_PAIRS = [
    {
        "question": "What does high glucose mean?",
        "answer": "High glucose levels (above 100 mg/dL fasting) may indicate prediabetes or diabetes. Glucose is the sugar in your blood that provides energy. Consistently high levels can damage blood vessels and organs over time. If your glucose is elevated, your doctor may recommend dietary changes, exercise, or medication. It's important to follow up for proper diagnosis and treatment.",
        "test_type": "Glucose",
        "keywords": ["glucose", "diabetes", "blood sugar", "high", "prediabetes"],
        "source": "Medical Guidelines",
        "confidence": 0.95
    },
    {
        "question": "Why is my cholesterol high?",
        "answer": "High cholesterol (above 200 mg/dL total) increases heart disease risk. Cholesterol is a waxy substance needed for cell function, but too much can clog arteries. Causes include diet high in saturated fats, lack of exercise, genetics, obesity, and certain medical conditions. Your doctor may recommend lifestyle changes (healthier diet, more exercise) and possibly medication to lower cholesterol.",
        "test_type": "Cholesterol",
        "keywords": ["cholesterol", "high", "heart disease", "diet", "statins"],
        "source": "American Heart Association",
        "confidence": 0.95
    },
    {
        "question": "What is a normal hemoglobin level?",
        "answer": "Normal hemoglobin is 13.5-17.5 g/dL for men and 12.0-15.5 g/dL for women. Hemoglobin is the protein in red blood cells that carries oxygen throughout your body. Low hemoglobin (anemia) can cause fatigue, weakness, and shortness of breath. High hemoglobin may indicate dehydration, lung disease, or other conditions. Your doctor will interpret results based on your symptoms and medical history.",
        "test_type": "Hemoglobin",
        "keywords": ["hemoglobin", "anemia", "iron", "blood", "oxygen"],
        "source": "Mayo Clinic",
        "confidence": 0.95
    },
    {
        "question": "Should I worry about high creatinine?",
        "answer": "Elevated creatinine (above 1.3 mg/dL) may indicate reduced kidney function, but context matters. Creatinine is a waste product filtered by kidneys. High levels can result from kidney disease, dehydration, certain medications, or high muscle mass. Your doctor will likely order additional kidney function tests and review your medications. Early detection is important for managing kidney health.",
        "test_type": "Creatinine",
        "keywords": ["creatinine", "kidney", "renal", "function", "GFR"],
        "source": "National Kidney Foundation",
        "confidence": 0.9
    },
    {
        "question": "What does TSH measure?",
        "answer": "TSH (Thyroid Stimulating Hormone) measures thyroid function. Normal range is 0.4-4.0 mIU/L. TSH tells your thyroid gland to produce thyroid hormones that regulate metabolism. High TSH suggests hypothyroidism (underactive thyroid), causing fatigue, weight gain, and cold sensitivity. Low TSH may indicate hyperthyroidism (overactive thyroid), causing weight loss, rapid heartbeat, and anxiety. Treatment options are available for both conditions.",
        "test_type": "TSH",
        "keywords": ["TSH", "thyroid", "hypothyroidism", "hyperthyroidism", "metabolism"],
        "source": "Endocrine Society",
        "confidence": 0.95
    },
    {
        "question": "What causes high triglycerides?",
        "answer": "High triglycerides (above 150 mg/dL) increase heart disease and pancreatitis risk. Triglycerides are fats in your blood from food and made by your liver. Common causes include obesity, excessive alcohol, high-sugar/high-carb diet, diabetes, and certain medications. Lifestyle changes (weight loss, exercise, limiting sweets and alcohol) often help. Very high levels (above 500 mg/dL) may require medication.",
        "test_type": "Triglycerides",
        "keywords": ["triglycerides", "fat", "heart disease", "diet", "alcohol"],
        "source": "American Heart Association",
        "confidence": 0.9
    },
    {
        "question": "What is HDL cholesterol?",
        "answer": "HDL (High-Density Lipoprotein) is 'good' cholesterol that removes excess cholesterol from arteries. Higher levels (above 60 mg/dL) protect against heart disease. Low HDL (below 40 mg/dL for men, 50 for women) increases risk. Exercise, maintaining healthy weight, avoiding smoking, and eating healthy fats can raise HDL. It's one part of your overall cholesterol profile.",
        "test_type": "HDL Cholesterol",
        "keywords": ["HDL", "good cholesterol", "heart health", "exercise"],
        "source": "American Heart Association",
        "confidence": 0.95
    },
    {
        "question": "What is LDL cholesterol?",
        "answer": "LDL (Low-Density Lipoprotein) is 'bad' cholesterol that can build up in artery walls. Optimal level is below 100 mg/dL. LDL above 160 mg/dL is high risk for heart disease. Diet changes (less saturated fat, more fiber), exercise, and weight loss can lower LDL. Your doctor may prescribe statins if lifestyle changes aren't enough. Regular monitoring is important.",
        "test_type": "LDL Cholesterol",
        "keywords": ["LDL", "bad cholesterol", "statins", "heart disease", "plaque"],
        "source": "American Heart Association",
        "confidence": 0.95
    }
]

def main():
    # Initialize client
    es_client = ElasticsearchClient()
    
    # Generate embeddings for Q&A pairs
    logger.info("Generating embeddings for knowledge base...")
    
    # Combine question and answer for better semantic search
    texts = [f"{qa['question']} {qa['answer']}" for qa in QA_PAIRS]
    embeddings = es_client.generate_embeddings(texts)
    
    # Add embeddings
    for qa, embedding in zip(QA_PAIRS, embeddings):
        qa['embedding'] = embedding
    
    # Index
    logger.info("Indexing knowledge base...")
    success, failed = es_client.index_documents("knowledge-base", QA_PAIRS)
    
    logger.info(f"✅ Indexed {success} Q&A pairs")
    
    # Verify
    count = es_client.client.count(index="knowledge-base")
    logger.info(f"Total Q&A pairs in index: {count['count']}")

if __name__ == "__main__":
    main()