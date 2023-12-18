from __future__ import annotations
from dataclasses import dataclass

import logging
from typing import Optional

from cacheout import Cache
from message import Level, Message

from .url import req_session

cache: Cache = Cache(maxsize=8192, ttl=0, default=None)


def filter_pub(json: dict) -> list[Message] | None:
    """Run publication checks.

    Args:
    ----
        json (dict): The entire tool's JSON, not small parts like other filters

    Returns:
    -------
        list[Message] | None: Errors
    """
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

        # Convert
        converted = PublicationData.convert(doi or pmid or pmcid)

        if doi and not pmid and converted.pmid:
            output.append(
                Message(
                    "DOI_BUT_NOT_PMID",
                    f"Publication DOI {doi} (https://www.doi.org/{doi}) does not have a PMID in the database.",
                    json["name"],
                    Level.ReportMedium,
                )
            )

        if doi and not pmcid and converted.pmcid:
            output.append(
                Message(
                    "DOI_BUT_NOT_PMCID",
                    f"Publication DOI {doi} (https://www.doi.org/{doi}) does not have a PMCID in the database.",
                    json["name"],
                    Level.ReportMedium,
                )
            )

        if pmid and not doi and converted.doi:
            output.append(
                Message(
                    "PMID_BUT_NOT_DOI",
                    f"Publication PMID {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}) does not have a DOI in the database.",
                    json["name"],
                    Level.ReportMedium,
                )
            )

        if pmcid and not doi and converted.doi:
            output.append(
                Message(
                    "PMCID_BUT_NOT_DOI",
                    f"Publication PMCID {pmcid} (https://pubmed.ncbi.nlm.nih.gov/{pmcid}) does not have a DOI in the database.",
                    json["name"],
                    Level.ReportMedium,
                )
            )

    if output == []:
        return None
    return output


@dataclass
class PublicationData:
    """
    A class to handle conversions between DOI, PMID, and PMCID.
    """

    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None

    def convert(identifier: str) -> PublicationData | None:
        """
        Convert a given identifier (DOI, PMID, or PMCID) to the other formats.
        """

        if identifier in cache:
            return cache.get(identifier)

        try:
            url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=biotools-linter&email=251814@mail.muni.cz&ids={identifier}&format=json"
            result = req_session.get(url).json()

            if not result or result.get("status") != "ok":
                return None

            pub = result["records"][0]
            if pub.get("live") == "false":
                return None

            pub_data = PublicationData(
                doi=pub.get("doi"), pmid=pub.get("pmid"), pmcid=pub.get("pmcid")
            )
            cache.set(identifier, pub_data)
            return pub_data

        except Exception as e:
            logging.critical(
                f"Error while making API request to idconv for {identifier}: {e}"
            )
            return None
