from __future__ import annotations

import logging

from message import Level, Message

from .url import req_session


def filter_pub(json: dict) -> list[Message] | None:
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
                output.append(Message("DOI_BUT_NOT_PMID", f"Publication DOI {doi} (https://www.doi.org/{doi}) has a PMID {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}) but is not in database.", json["name"], Level.ReportMedium))

        # Check for DOI but not PMID
        if doi and not pmcid:
            # Check if DOI to PMID can be automatically converted
            pmcid = doi_to_pmcid(doi)
            if pmcid:
                output.append(Message("DOI_BUT_NOT_PMCID", f"Publication DOI {doi} (https://www.doi.org/{doi}) has a PMCID {pmcid} (https://pubmed.ncbi.nlm.nih.gov/{pmcid}) but is not in database.", json["name"], Level.ReportMedium))

        # Check for PMID/PMCID but not DOI
        if (pmcid or pmid) and not doi:
            # Check if DOI to PMID can be automatically converted
            doi_pmid = pmid_or_pmcid_to_doi(pmid)
            doi_pmcid = pmid_or_pmcid_to_doi(pmcid)
            if doi_pmid:
                output.append(Message("PMID_BUT_NOT_DOI", f"Publication PMID {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}) has a DOI {doi_pmid} (https://www.doi.org/{doi_pmid}) but is not in database.", json["name"], Level.ReportMedium))

            if doi_pmcid:
                output.append(Message("PMCID_BUT_NOT_DOI", f"Publication PMCID {pmcid} (https://pubmed.ncbi.nlm.nih.gov/{pmcid}) has a DOI {doi_pmcid} (https://www.doi.org/{doi_pmcid}) but is not in database.", json["name"], Level.ReportMedium))

    if output == []:
        return None
    return output

def doi_to_pmid(doi: str) -> str | None:
    """Convert DOI to PMID."""
    try:
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
    except Exception as e:
        logging.critical(f"Error while making API request to idconv: {e}")
        return None

def doi_to_pmcid(doi: str) -> str | None:
    """Convert DOI to PMCID."""
    try:
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
    except Exception as e:
        logging.critical(f"Error while making API request to idconv: {e}")
        return None

def pmid_or_pmcid_to_doi(pc_c_id: str) -> str | None:
    """Convert PMCID/PMID to doi.

    Last time I checked `madap` had this so use it for testing.
    """
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=biotools-linter&email=251814@mail.muni.cz&ids={pc_c_id}&format=json"

        result = req_session.get(url).json()

        if result and result["status"] == "ok":
            pub = result["records"][0]

            if "live" in pub and pub["live"] == "false":
                return None

            if "doi" not in pub:
                return None

            return pub["doi"]
    except Exception as e:
        logging.critical(f"Error while making API request to idconv: {e}")

    return None
