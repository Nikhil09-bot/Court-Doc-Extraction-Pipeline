"""Verify the local and cloud setup for the court document extraction project."""

import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()
PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ["GOOGLE_CLOUD_LOCATION"]


def check(label, fn):
    try:
        detail = fn()
        print(f"  PASS  {label}" + (f" - {detail}" if detail else ""))
        return True
    except Exception as error:
        print(f"  FAIL  {label}\n        {type(error).__name__}: {str(error)[:180]}")
        return False


def adc():
    import google.auth

    _, project = google.auth.default()
    return f"project={project}"


def vertex():
    from google import genai

    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    response = client.models.generate_content(
        model=os.environ["GEMINI_MODEL"],
        contents="Reply with exactly: OK",
    )
    return f"model replied {response.text.strip()[:20]!r}"


def vision():
    from google.cloud import vision

    vision.ImageAnnotatorClient()
    return "client initialized"


def docai():
    from google.cloud import documentai

    location = os.environ["DOCAI_LOCATION"]
    client = documentai.DocumentProcessorServiceClient(
        client_options={"api_endpoint": f"{location}-documentai.googleapis.com"}
    )
    name = client.processor_path(PROJECT, location, os.environ["DOCAI_PROCESSOR_ID"])
    processor = client.get_processor(name=name)
    return f"processor '{processor.display_name}' state={processor.state.name}"


def bigquery():
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    dataset = client.get_dataset(f"{PROJECT}.{os.environ['BQ_DATASET']}")
    return f"dataset in {dataset.location}"


def gcs():
    from google.cloud import storage

    bucket = storage.Client(project=PROJECT).get_bucket(os.environ["GCS_BUCKET"])
    return f"bucket in {bucket.location}"


def courtlistener():
    request = urllib.request.Request(
        "https://www.courtlistener.com/api/rest/v4/courts/?page_size=1",
        headers={"Authorization": f"Token {os.environ['COURTLISTENER_TOKEN']}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return f"HTTP {response.status}"


if __name__ == "__main__":
    print(f"\nVerifying setup for {PROJECT} ({LOCATION})\n")
    results = [
        check("Application Default Credentials", adc),
        check("Vertex AI / Gemini", vertex),
        check("Cloud Vision", vision),
        check("Document AI processor", docai),
        check("BigQuery dataset", bigquery),
        check("Cloud Storage bucket", gcs),
        check("CourtListener API", courtlistener),
    ]
    print(f"\n{sum(results)}/{len(results)} passed\n")