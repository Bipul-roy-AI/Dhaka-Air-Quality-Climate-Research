"""Bind a user-provided deposited-source attribution to inspected file bytes."""
KNOWN_CSV_SHA256 = "8760175fc048eea4180b828fd60d10cb799a73a5144a7e4aca19ddbaf8dbdd62"
DOI = "10.17632/9j447cynb9.2"


def attribution(csv_sha256):
    if csv_sha256 != KNOWN_CSV_SHA256:
        return {"doi": None, "status": "No deposited-source attribution asserted for these input bytes", "measurement_validated": False}
    return {"doi": DOI, "status": "User-provided Mendeley V2 attribution corroborated by public metadata; no fresh provider-file byte match or instrument validation", "licence": "CC BY 4.0", "measurement_validated": False}
