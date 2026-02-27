# backend/api/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import tempfile, os
from core.elasticsearch_client import get_es_client
from tools.pdf_processor import LabReportProcessor

router        = APIRouter()
es_client     = get_es_client()
pdf_processor = LabReportProcessor()


@router.post("/api/upload-lab-report")
async def upload_lab_report(file: UploadFile = File(...), patient_id: str = Form(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files supported")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        result = pdf_processor.process_pdf(tmp_path, patient_id)
        os.unlink(tmp_path)
        if result["status"] != "success":
            raise HTTPException(400, result.get("message", "Processing failed"))
        document = result["document"]

        try:
            doc_id = es_client.client.index(
                index="lab-results", document=document,
                pipeline="lab_auto_status")["_id"]
            pipeline_used = True
        except Exception:
            doc_id = es_client.index_document("lab-results", document)
            pipeline_used = False

        return {
            "status": "success", "document_id": doc_id,
            "patient_id": patient_id, "test_date": document["test_date"],
            "results_count": len(document["results"]),
            "abnormal_flags": document["abnormal_flags"],
            "critical_flags": document["critical_flags"],
            "auto_status_applied": pipeline_used,
        }
    except Exception as e:
        raise HTTPException(500, str(e))