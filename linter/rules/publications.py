from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp
from cacheout import Cache
from message import Level, Message
from utils import array_without_value

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
    if json is None or "publication" not in json:
        return None

    if "publication" not in json or not json["publication"]:
        return None

    tasks = [process_publication(json, pub_index, publication) for pub_index, publication in enumerate(json["publication"])]
    results = await asyncio.gather(*tasks)
    messages = [message for result in results for message in result if result]

    return messages if messages else None

async def process_publication(json: dict, pub_index, publication: dict) -> list[Message]:
    output = []
    doi: str | None = publication["doi"] if "doi" in publication else None
    pmid: str | None = publication["pmid"] if "pmid" in publication else None
    pmcid: str | None = publication["pmcid"] if "pmcid" in publication else None
    identifier: str | None = doi or pmid or pmcid
    if identifier is None:
        return []
    converted = await PublicationData.convert(identifier)
    location = f"{json['name']}//publication/{pub_index}"

    if not converted:
        return output

    # Other IDs not present in DB
    if doi and not pmid and converted.pmid:
        output.append(
            Message(
                "DOI_BUT_NOT_PMID",
                #f"Publication DOI {doi} (https://www.doi.org/{doi}) does not have a PMID in the database.",
                # TODO: Add links to articles for all error messages
                f'Article {doi} has both DOI and PMID ({converted.pmid}), but only DOI is provided. Use NCBI AnyID Converter for verification.',
                f"{location}/doi",
                Level.ReportMedium,
            ),
        )

    if doi and not pmcid and converted.pmcid:
        output.append(
            Message(
                "DOI_BUT_NOT_PMCID",
                #f"Publication DOI {doi} (https://www.doi.org/{doi}) does not have a PMCID in the database.",
                f'Article {doi} has both DOI and PMCID ({converted.pmcid}), but only DOI is provided. Use NCBI AnyID Converter for verification.',
                f"{location}/doi",
                Level.ReportMedium,
            ),
        )

    if pmid and not doi and converted.doi:
        output.append(
            Message(
                "PMID_BUT_NOT_DOI",
                #"Publication PMID {pmid} (https://pubmed.ncbi.nlm.nih.gov/{pmid}) does not have a DOI in the database.",
                f'Article {pmid} has both PMID and DOI ({converted.doi}), but only PMID is provided. Use NCBI AnyID Converter for verification.',
                f"{location}/pmid",
                Level.ReportMedium,
            ),
        )

    if pmcid and not doi and converted.doi:
        output.append(
            Message(
                "PMCID_BUT_NOT_DOI",
                #f"Publication PMCID {pmcid} (https://pubmed.ncbi.nlm.nih.gov/{pmcid}) does not have a DOI in the database.",
                f'Article {pmcid} has both PMCID and DOI ({converted.doi}), but only PMCID is provided. Use NCBI AnyID Converter for verification.',
                f"{location}/pmcid",
                Level.ReportMedium,
            ),
        )

    if pmcid and not pmid and converted.pmid:
        output.append(
            Message(
                "PMCID_BUT_NOT_PMID",
                #f"Publication PMCID {pmcid} (https://pubmed.ncbi.nlm.nih.gov/{pmcid}) does not have a DOI in the database.",
                f'Article {pmcid} has both PMCID and PMID ({converted.pmid}), but only PMCID is provided. Use NCBI AnyID Converter for verification.',
                f"{location}/pmcid",
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
                            #f"Converting {checked_id.upper()} {locals()[checked_id]} led to a different {checking_id.upper()} ({converted_id}) than in annotation ({original_id})",
                            f"{checked_id.upper()} ({locals()[checked_id]}) and {checking_id.upper()} ({converted_id}) do not correspond to the same publication.",
                            f"{location}/{checked_id.lower()}",
                            Level.ReportHigh,
                        ),
                    )

    return output

@dataclass
class PublicationData:

    """A class to handle conversions between DOI, PMID, and PMCID."""

    doi: Optional[str] | None = None
    pmid: Optional[str] | None = None
    pmcid: Optional[str] | None = None

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
                                                                                  sock_connect=5,
                                                                                  sock_read=5))
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
