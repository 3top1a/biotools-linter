from __future__ import annotations

from message import Level, Message

from .url import req_session


def filter_pub(json) -> list[Message] | None:
    if json is None:
        return None

    if "publication" not in json:
        return None

    output = []

    # Check each publication
    # Schema at https://biotoolsschema.readthedocs.io/en/latest/biotoolsschema_elements.html#publication-group
    for publication in json["publication"]:
        doi = publication["doi"]
        pmid = publication["pmid"]
        pmcid = publication["pmcid"]

        # Check for DOI but not PMID
        if doi and not pmid:
            # Check if DOI to PMID can be automatically converted
            pmid = doi_to_pmid(doi)
            if pmid:
                output.append(Message("DOI_BUT_NOT_PMID", f"Publication DOI {doi} has a PMID {pmid} but is not in database.", json["name"], Level.ReportMedium))
                pass

            # If not, do not output
            pass

        # Check for DOI but not PMID
        if doi and not pmcid:
            # Check if DOI to PMID can be automatically converted
            pmcid = doi_to_pmcid(doi)
            if pmcid:
                output.append(Message("DOI_BUT_NOT_PMCID", f"Publication DOI {doi} has a PMCID {pmcid} but is not in database.", json["name"], Level.ReportMedium))
                pass

            # If not, do not output
            pass

    if output == []:
        return None
    return output

def doi_to_pmid(doi: str) -> str | None:
    """Convert DOI to PMID."""
    url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=biotools-linter&email=251814@mail.muni.cz&ids={doi}&format=json"

    result = req_session.get(url).json()

    if result is None:
        return None

    if result["status"] != "ok":
        return None

    pub = result["records"][0]

    if "live" in pub and pub["live"] == "false":
        return None

    if "pmid" not in pub:
        return None

    return pub["pmid"]

def doi_to_pmcid(doi: str) -> str | None:
    """Convert DOI to PMCID."""
    url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=biotools-linter&email=251814@mail.muni.cz&ids={doi}&format=json"

    result = req_session.get(url).json()

    if result is None:
        return None

    if result["status"] != "ok":
        return None

    pub = result["records"][0]

    if "live" in pub and pub["live"] == "false":
        return None

    if "pmcid" not in pub:
        return None

    return pub["pmcid"]
