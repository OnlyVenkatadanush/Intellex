import re
import logging
import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from backend.app.config import settings

logger = logging.getLogger(__name__)


class SearchTools:
    @staticmethod
    async def web_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Searches the live web using Tavily Search API if configured.
        Otherwise executes real live retrieval via DuckDuckGo Instant Answers and Wikipedia Search.
        Zero mock or placeholder results.
        """
        if settings.TAVILY_API_KEY:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": settings.TAVILY_API_KEY,
                            "query": query,
                            "max_results": max_results,
                            "search_depth": "advanced"
                        },
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        data = response.json()
                        return [
                            {
                                "title": item.get("title", "No Title"),
                                "url": item.get("url", ""),
                                "content": item.get("content", ""),
                                "source": "Tavily Web Search"
                            }
                            for item in data.get("results", [])
                        ]
            except Exception as e:
                logger.warning(f"Tavily search failed: {e}. Falling back to open web search.")

        # Real Open Web Search fallback: Wikipedia + DuckDuckGo
        return await SearchTools._fallback_search(query, max_results)

    @staticmethod
    async def _fallback_search(query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Retrieves real live encyclopedia and instant answer data from Wikipedia and DuckDuckGo API.
        """
        results: List[Dict[str, Any]] = []

        # 1. Wikipedia Search API
        try:
            async with httpx.AsyncClient() as client:
                wiki_url = "https://en.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": max_results
                }
                res = await client.get(wiki_url, params=params, timeout=6.0)
                if res.status_code == 200:
                    data = res.json()
                    search_results = data.get("query", {}).get("search", [])
                    for item in search_results:
                        title = item.get("title", "")
                        snippet = item.get("snippet", "")
                        clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                        page_id = item.get("pageid")
                        url = f"https://en.wikipedia.org/?curid={page_id}"
                        results.append({
                            "title": title,
                            "url": url,
                            "content": clean_snippet,
                            "source": "Wikipedia Encyclopedia"
                        })
        except Exception as e:
            logger.debug(f"Wikipedia search skipped: {e}")

        # 2. DuckDuckGo Instant Answer API
        try:
            async with httpx.AsyncClient() as client:
                ddg_url = "https://api.duckduckgo.com/"
                ddg_params = {
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1"
                }
                res = await client.get(ddg_url, params=ddg_params, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
                    abstract = data.get("AbstractText", "")
                    heading = data.get("Heading", "")
                    abstract_url = data.get("AbstractURL", "")
                    if abstract and heading:
                        results.append({
                            "title": f"{heading} (Overview)",
                            "url": abstract_url or f"https://duckduckgo.com/?q={query}",
                            "content": abstract,
                            "source": "DuckDuckGo Instant Answer"
                        })
                    
                    # Related topics
                    for topic in data.get("RelatedTopics", [])[:2]:
                        t_text = topic.get("Text")
                        t_url = topic.get("FirstURL")
                        if t_text and t_url:
                            results.append({
                                "title": t_text[:60] + "...",
                                "url": t_url,
                                "content": t_text,
                                "source": "DuckDuckGo Knowledge"
                            })
        except Exception as e:
            logger.debug(f"DuckDuckGo search skipped: {e}")

        return results[:max_results]

    @staticmethod
    async def fetch_arxiv_papers(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries arXiv API for academic preprints in CS, physics, math, and quantitative biology.
        Extracts verified paper authors, publication year, abstract, and canonical arXiv URLs.
        """
        url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, params=params, timeout=8.0)
                if res.status_code == 200:
                    root = ET.fromstring(res.text)
                    papers = []
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    for entry in root.findall("atom:entry", ns):
                        title = entry.find("atom:title", ns)
                        summary = entry.find("atom:summary", ns)
                        id_url = entry.find("atom:id", ns)
                        published = entry.find("atom:published", ns)
                        
                        title_text = title.text.strip().replace("\n", " ") if title is not None else "Untitled Preprint"
                        summary_text = summary.text.strip().replace("\n", " ") if summary is not None else ""
                        url_text = id_url.text.strip() if id_url is not None else ""
                        pub_year = published.text[:4] if published is not None and published.text else "2024"
                        
                        # Extract real authors
                        authors = []
                        for author_elem in entry.findall("atom:author", ns):
                            name_elem = author_elem.find("atom:name", ns)
                            if name_elem is not None and name_elem.text:
                                authors.append(name_elem.text.strip())
                        
                        papers.append({
                            "title": title_text,
                            "url": url_text,
                            "content": summary_text,
                            "source": "arXiv Academic API",
                            "journal": "arXiv Preprints",
                            "year": pub_year,
                            "authors": authors
                        })
                    return papers
        except Exception as e:
            logger.warning(f"arXiv retrieval failed: {e}")
        return []

    @staticmethod
    async def fetch_pubmed_papers(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries PubMed NCBI E-utilities API for clinical, biological, and medical literature.
        Fetches authentic abstracts, author rosters, journal names, and publication years.
        """
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        try:
            async with httpx.AsyncClient() as client:
                search_params = {
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": max_results
                }
                res = await client.get(search_url, params=search_params, timeout=6.0)
                if res.status_code != 200:
                    return []

                id_list = res.json().get("esearchresult", {}).get("idlist", [])
                if not id_list:
                    return []

                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(id_list),
                    "retmode": "xml"
                }
                fetch_res = await client.get(fetch_url, params=fetch_params, timeout=8.0)
                if fetch_res.status_code == 200:
                    root = ET.fromstring(fetch_res.text)
                    papers = []
                    for article in root.findall(".//PubmedArticle"):
                        title = article.findtext(".//ArticleTitle") or "Untitled Study"
                        abstract = article.findtext(".//AbstractText") or ""
                        pmid = article.findtext(".//PMID") or ""
                        journal = article.findtext(".//Journal/Title") or "Peer-Reviewed Medical Journal"
                        
                        # Real Year extraction
                        year = (
                            article.findtext(".//JournalIssue/PubDate/Year") or
                            article.findtext(".//ArticleDate/Year") or
                            article.findtext(".//DateCompleted/Year") or
                            "2024"
                        )
                        # Extract first 4 digits if date contains month/text
                        year_match = re.search(r"\b(19\d\d|20[0-2]\d)\b", year)
                        clean_year = year_match.group(1) if year_match else "2024"

                        # Extract authentic author names
                        authors = []
                        for author in article.findall(".//AuthorList/Author"):
                            last = author.findtext("LastName") or ""
                            fore = author.findtext("ForeName") or author.findtext("Initials") or ""
                            if last:
                                authors.append(f"{fore} {last}".strip() if fore else last)

                        # Extract DOI if present in article ID list
                        doi = None
                        for aid in article.findall(".//ArticleIdList/ArticleId"):
                            if aid.attrib.get("IdType") == "doi" and aid.text:
                                doi = aid.text.strip()
                                break

                        content = abstract if abstract else f"Published in {journal} ({clean_year}). PubMed ID: {pmid}"
                        papers.append({
                            "title": title,
                            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                            "content": content,
                            "source": "PubMed Medicine API",
                            "journal": journal,
                            "year": clean_year,
                            "authors": authors,
                            "doi": doi
                        })
                    if papers:
                        return papers
        except Exception as e:
            logger.warning(f"PubMed retrieval failed: {e}")
        return []

    @staticmethod
    async def fetch_crossref_papers(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries Crossref API across 140M+ peer-reviewed cross-disciplinary publications.
        Enforces type:journal-article to exclude supplementary deposits and components (.s001, .s002).
        Returns real DOI links, journal containers, author attributions, and publication metadata.
        """
        url = "https://api.crossref.org/works"
        params = {
            "query": query,
            "rows": max_results * 2,  # Fetch slightly more to filter out any remaining components
            "filter": "type:journal-article",
            "select": "DOI,title,abstract,author,published,published-print,published-online,created,container-title,type,score"
        }
        headers = {
            "User-Agent": "IntellexResearchBot/1.0 (mailto:research@intellex.ai)"
        }
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, params=params, headers=headers, timeout=8.0)
                if res.status_code == 200:
                    items = res.json().get("message", {}).get("items", [])
                    papers = []
                    seen_dois = set()
                    
                    for item in items:
                        # Exclude components or non-journal articles
                        if item.get("type") == "component":
                            continue

                        doi = item.get("DOI", "").strip()
                        # Strict rejection of supplementary deposit extensions like .s001, .s002, etc.
                        if not doi or re.search(r"\.(s\d+|supp\d*)$", doi, re.IGNORECASE):
                            continue

                        # Clean base DOI deduplication
                        norm_doi = doi.lower()
                        if norm_doi in seen_dois:
                            continue
                        seen_dois.add(norm_doi)

                        titles = item.get("title", [])
                        title = titles[0].strip().replace("\n", " ") if titles else "Untitled Scholarly Work"
                        
                        journals = item.get("container-title", [])
                        journal = journals[0].strip() if journals else "Peer-Reviewed Journal"
                        
                        # Multi-tiered real publication year extraction
                        pub_year = None
                        for date_field in ["published-print", "published-online", "published", "created"]:
                            date_parts = item.get(date_field, {}).get("date-parts", [])
                            if date_parts and date_parts[0] and date_parts[0][0]:
                                pub_year = str(date_parts[0][0])
                                break
                        year = pub_year if pub_year else "2024"

                        # Extract authentic authors
                        authors = []
                        for a in item.get("author", []):
                            given = a.get("given", "").strip()
                            family = a.get("family", "").strip()
                            if family:
                                authors.append(f"{given} {family}".strip() if given else family)
                            elif a.get("name"):
                                authors.append(a.get("name").strip())
                        
                        # Abstract cleanup
                        raw_abstract = item.get("abstract", "")
                        clean_abstract = re.sub(r"<[^>]+>", "", raw_abstract).strip() if raw_abstract else ""

                        author_str = ", ".join(authors[:3]) if authors else journal
                        content = clean_abstract if clean_abstract else f"Authored by {author_str}. Published in {journal} ({year}). DOI: {doi}"
                        
                        papers.append({
                            "title": title,
                            "url": f"https://doi.org/{doi}",
                            "content": content,
                            "source": "Crossref Peer-Reviewed Index",
                            "journal": journal,
                            "year": year,
                            "authors": authors,
                            "doi": doi
                        })

                        if len(papers) >= max_results:
                            break

                    return papers
        except Exception as e:
            logger.warning(f"Crossref retrieval failed: {e}")
        return []
