from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
import aiohttp

from cacheout import Cache
from message import Level, Message

from .url import client_args

cache: Cache = Cache(maxsize=8192, ttl=0, default=None)

TYPES = ["doi", "pmid", "pmcid"]


async def filter_pub(json: dict) -> list[Message] | None:
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

        # Convert naively
        converted = await PublicationData.convert(doi or pmid or pmcid)

        if not converted:
            continue

        # Other IDs not present in DB
        if doi and not pmid and converted.pmid:
            output.append(
                Message(
                    "DOI_BUT_NOT_PMID",
                    f"Publication DOI {doi} (https://www.doi.org/{doi}) does not have a PMID in the database.",
                    json["name"],
                    Level.ReportMedium,
                ),
            )

        if doi and not pmcid and converted.pmcid:
            output.append(
                Message(
                    "DOI_BUT_NOT_PMCID",
                    f"Publication DOI {doi} (https://www.doi.org/{doi}) does not have a PMCID in the database.",
                    json["name"],
                    Level.ReportMedium,
                ),
            )

        if pmid and not doi and converted.doi:
            output.append(
                Message(
                    "PMID_BUT_NOT_DOI",
                    f"Publication PMID {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}) does not have a DOI in the database.",
                    json["name"],
                    Level.ReportMedium,
                ),
            )

        if pmcid and not doi and converted.doi:
            output.append(
                Message(
                    "PMCID_BUT_NOT_DOI",
                    f"Publication PMCID {pmcid} (https://pubmed.ncbi.nlm.nih.gov/{pmcid}) does not have a DOI in the database.",
                    json["name"],
                    Level.ReportMedium,
                ),
            )

        # Check for publication discrepancy (two different publications were entered in one, may be due to a user error)
        for checked_id in TYPES:
            converted = await PublicationData.convert(locals()[checked_id])
            for checking_id in array_without_value(TYPES, checked_id):
                if locals()[checking_id] is None or converted is None:
                    continue

                original_id: str = locals()[checking_id].strip().lower()
                if checking_id in converted.__dict__ and converted.__dict__[checking_id] is not None:
                    converted_id: str = converted.__dict__[checking_id].strip().lower()
                    if original_id != converted_id:
                        output.append(
                            Message(
                                # Can be DOI_DISCREPANCY, PMID_DISCREPANCY, PMCID_DISCREPANCY
                                f"{checking_id.upper()}_DISCREPANCY",
                                f"Converting {checked_id.upper()} {locals()[checked_id]} led to a different {checking_id.upper()} ({converted_id}) than in annotation ({original_id})",
                                json["name"],
                                Level.ReportHigh,
                            ),
                        )

    if output == []:
        return None
    return output

def array_without_value(arr: list, value: any) -> list:
    """Return given array without a given value.

    Args:
    ----
        arr (list): Input array
        value (any): Value to ignore

    Returns:
    -------
        list: Output array

    """
    return [x for x in arr if x != value]

@dataclass
class PublicationData:

    """A class to handle conversions between DOI, PMID, and PMCID."""

    doi: Optional[str] = None
    pmid: Optional[str] = None
    pmcid: Optional[str] = None

    @staticmethod
    async def convert(identifier: str) -> PublicationData | None:
        """Convert a given identifier (DOI, PMID, or PMCID) to the other formats."""
        if identifier in cache:
            return cache.get(identifier)

        try:
            url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool=biotools-linter&email=251814@mail.muni.cz&ids={identifier}&format=json"

            # TODO Move session into singleton (needs to be initialized in async run loop)
            async with aiohttp.ClientSession(**client_args) as session:
                # https://github.com/aio-libs/aiohttp/issues/3203
                # AIOHTTP has an issue with timeouts appearing where they shouldn't be.
                # Making a new timeout for each request seems to eliminate this issue
                response = await session.get(url, timeout=aiohttp.ClientTimeout(total=None,
                                                                                  sock_connect=10,
                                                                                  sock_read=10))
                result = await response.json()

                if not result or result.get("status") != "ok":
                    return None

                pub = result["records"][0]
                if pub.get("live") == "false":
                    return None

                pub_data = PublicationData(
                    doi=pub.get("doi"),
                    pmid=pub.get("pmid"),
                    pmcid=pub.get("pmcid"),
                )
                cache.set(identifier, pub_data)
                return pub_data

        except Exception as e:
            logging.critical(
                f"Error while making API request to idconv for {identifier}: {e}",
            )
            return None
