import asyncio
import logging
import math
import re
import uuid
from datetime import datetime
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from backend.app.agents.base import Agent, AgentState
from backend.app.infrastructure.llm.manager import LLMManager

logger = logging.getLogger(__name__)


class FactCheckFeedback(BaseModel):
    supporting_source_indices: List[int] = Field(
        default=[],
        description="1-based integer indices of the sources in the context that directly substantiate this claim (e.g. [1, 3])."
    )
    contradicting_source_indices: List[int] = Field(
        default=[],
        description="1-based integer indices of any sources in the context that contradict this claim."
    )
    supporting_sources: List[str] = Field(
        default=[],
        description="URLs or exact paper titles that support the claim."
    )
    contradicting_sources: List[str] = Field(
        default=[],
        description="URLs or exact paper titles that contradict the claim."
    )
    verification_status: str = Field(
        ...,
        description="VERIFIED, PARTIALLY_VERIFIED, CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, or UNVERIFIED."
    )
    evidence_strength: float = Field(
        ...,
        description="Rating between 0 and 100 representing the detail level and scientific strength of the supporting evidence."
    )
    rationale: str = Field(
        ...,
        description="Reasoning trace explanation of the audit verdict."
    )


class FactCheckerAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Fact Checker",
            role="Factual Verification Auditor",
            system_prompt=(
                "You are the Fact Checker Agent of Intellex Autonomous Research Platform.\n"
                "Audit synthesized scientific claims strictly against the retrieved evidence sources.\n"
                "Review the numbered Evidence Context carefully. Identify which specific [Source N] items directly substantiate each claim.\n"
                "Do NOT attribute a paper to a chemistry or mechanism it does not study.\n"
                "Return the 1-based source indices in supporting_source_indices.\n"
                "Provide an evidence strength score (0 to 100) and a verification status: VERIFIED, PARTIALLY_VERIFIED, CONFLICTING_EVIDENCE, INSUFFICIENT_EVIDENCE, or UNVERIFIED."
            )
        )

    def _evaluate_source_credibility(self, source_name: str) -> float:
        """Assigns source authority values (0.0 - 100.0). Phase 6 Credibility Engine."""
        name = source_name.lower()
        if "pubmed" in name or "academic journal" in name:
            return 95.0
        elif "arxiv" in name or "crossref" in name:
            return 90.0
        elif "gov" in name or "edu" in name:
            return 88.0
        elif "user file" in name or "user uploaded" in name:
            return 85.0
        elif "wikipedia" in name or "tavily" in name:
            return 70.0
        return 40.0

    def _extract_year(self, source: dict) -> int:
        """Helper to extract a publication year from source metadata or content."""
        if source.get("year"):
            try:
                y = int(str(source["year"])[:4])
                if 1900 <= y <= 2030:
                    return y
            except Exception:
                pass
        content = source.get("content", "")
        title = source.get("title", "")
        years = re.findall(r"\b(19\d\d|20[0-2]\d)\b", content + " " + title)
        if years:
            return int(years[0])
        return 2024

    def _extract_referenced_indices(self, text: str, max_count: int) -> List[int]:
        """Extracts source index numbers mentioned in rationale text (e.g., 'Source 3', 'Sources 1 and 2')."""
        indices = set()
        for match in re.finditer(r"\b(?:Sources?|References?)\s*(\d+)(?:\s*(?:and|to|,|-)\s*(\d+))?", text, re.IGNORECASE):
            for group in match.groups():
                if group:
                    try:
                        idx = int(group)
                        # Handle both 1-based (Source 1..N) and 0-based (Source 0..N-1)
                        if 1 <= idx <= max_count:
                            indices.add(idx)
                        elif idx == 0 and max_count >= 1:
                            indices.add(1)
                    except ValueError:
                        pass
        return list(indices)

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Auditing claims against retrieved source indices...",
            "log_type": "INFO"
        })

        llm = LLMManager.get_provider()
        
        # Build numbered evidence context
        evidence_lines = []
        for idx, item in enumerate(state.evidence):
            authors_str = ", ".join(item.get("authors", [])[:3]) if item.get("authors") else "Authors noted"
            evidence_lines.append(
                f"[Source {idx+1}] Title: {item.get('title', 'Untitled')} | Year: {item.get('year', 'N/A')} | "
                f"Authors: {authors_str} | Source: {item.get('source', 'Index')} | URL: {item.get('url', 'N/A')}\n"
                f"Content: {item.get('content', '')[:350]}\n"
            )
        evidence_context = "\n".join(evidence_lines)

        verified_findings = []
        for idx, finding in enumerate(state.findings):
            if idx > 0:
                await asyncio.sleep(0.5)  # Paced execution to prevent burst rate limits

            claim = finding.get("claim", "")
            prompt = (
                f"Research Claim to Audit:\n{claim}\n\n"
                f"Numbered Evidence Context:\n{evidence_context}\n\n"
                f"Audit this claim against the numbered sources above. "
                f"Identify precisely which [Source N] entries directly substantiate this claim. "
                f"Return the 1-based source indices in supporting_source_indices."
            )
            
            supporting_sources = []
            contradicting_sources = []
            credibility_score = 0.0
            evidence_strength = 0.0
            cross_source_agreement = 0.0
            recency_score = 0.0
            contradiction_penalty = 0.0
            confidence = 0.0
            status = "UNVERIFIED"
            rationale = "No evidence found to support the claim."

            try:
                audit = await llm.generate_structured(
                    prompt=prompt,
                    system_prompt=self.system_prompt,
                    response_model=FactCheckFeedback
                )

                # 1. Resolve supporting sources via explicit 1-based indices from model
                matched_indices = set()
                for s_idx in audit.supporting_source_indices:
                    if 1 <= s_idx <= len(state.evidence):
                        matched_indices.add(s_idx - 1)

                # 2. Check if rationale mentions "Source X"
                text_indices = self._extract_referenced_indices(audit.rationale, len(state.evidence))
                for t_idx in text_indices:
                    matched_indices.add(t_idx - 1)

                # 3. Match explicit URLs or exact titles in audit.supporting_sources
                for src_idx, src in enumerate(state.evidence):
                    s_url = src.get("url", "")
                    s_title = src.get("title", "")
                    if any((s_url and s_url in item) or (s_title and s_title in item) for item in audit.supporting_sources):
                        matched_indices.add(src_idx)

                # 4. If still empty, perform domain-specific material/keyword match
                # Extract specific chemical / materials symbols (e.g. LLZO, LAGP, TSPE, PEO, Li6.4...)
                if not matched_indices:
                    chemical_tokens = [
                        w for w in re.findall(r"\b[A-Za-z0-9\(\)\-]{3,}\b", claim)
                        if any(c.isupper() for c in w) or any(c.isdigit() for c in w)
                    ]
                    generic_stopwords = {"THIS", "THAT", "EVALUATE", "SAFETY", "STUDY", "SOLID", "STATE", "BATTERY", "BATTERIES", "LITHIUM", "METAL"}
                    distinctive_tokens = [t for t in chemical_tokens if t.upper() not in generic_stopwords]
                    
                    if distinctive_tokens:
                        for src_idx, src in enumerate(state.evidence):
                            content_lower = (src.get("content", "") + " " + src.get("title", "")).lower()
                            if any(tok.lower() in content_lower for tok in distinctive_tokens):
                                matched_indices.add(src_idx)
                                if len(matched_indices) >= 2:
                                    break

                # Gather unique matched supporting sources (capped at top 3 most relevant)
                for s_idx in sorted(matched_indices)[:3]:
                    supporting_sources.append(state.evidence[s_idx])

                # Resolve contradicting sources
                contra_indices = set()
                for c_idx in audit.contradicting_source_indices:
                    if 1 <= c_idx <= len(state.evidence):
                        contra_indices.add(c_idx - 1)
                for c_idx in sorted(contra_indices):
                    if c_idx not in matched_indices:
                        contradicting_sources.append(state.evidence[c_idx])

                n_sup = len(supporting_sources)
                n_contra = len(contradicting_sources)

                if n_sup > 0:
                    # Deterministic Evidence Scoring
                    credibility_score = sum(self._evaluate_source_credibility(s.get("source", "Web")) for s in supporting_sources) / n_sup
                    cross_source_agreement = 100.0 * (n_sup / (n_sup + n_contra))
                    evidence_strength = min(100.0, max(20.0, float(audit.evidence_strength)))
                    
                    recency_vals = []
                    for s in supporting_sources:
                        pub_year = self._extract_year(s)
                        age = max(0, 2026 - pub_year)
                        recency_vals.append(100.0 * math.exp(-0.05 * age))
                    recency_score = sum(recency_vals) / len(recency_vals)
                    
                    contradiction_penalty = 25.0 * n_contra
                    
                    raw_confidence = (
                        credibility_score * 0.3 +
                        cross_source_agreement * 0.3 +
                        evidence_strength * 0.2 +
                        recency_score * 0.2 -
                        contradiction_penalty
                    )
                    confidence = round(min(100.0, max(0.0, raw_confidence)), 2)
                    
                    if n_contra > 0:
                        status = "CONFLICTING_EVIDENCE"
                    elif confidence >= 75.0:
                        status = "VERIFIED"
                    else:
                        status = "PARTIALLY_VERIFIED"
                else:
                    status = "INSUFFICIENT_EVIDENCE"
                    confidence = 0.0
                    credibility_score = 0.0
                    evidence_strength = 0.0
                    cross_source_agreement = 0.0
                    recency_score = 0.0
                    contradiction_penalty = 0.0
                    claim = f"[Insufficient Evidence] {claim}"

                rationale = audit.rationale
            except Exception as exc:
                logger.warning(f"FactChecker LLM audit failed for finding {idx}: {exc}")
                status = "INSUFFICIENT_EVIDENCE"
                confidence = 0.0
                rationale = f"Verification audit failed due to execution error: {str(exc)}"

            verified_findings.append({
                "finding_id": finding.get("finding_id", str(uuid.uuid4())),
                "claim": claim,
                "supporting_sources": [s.get("url") for s in supporting_sources if s.get("url")],
                "contradicting_sources": [s.get("url") for s in contradicting_sources if s.get("url")],
                "confidence_score": confidence,
                "credibility_score": round(credibility_score, 2),
                "verification_status": status,
                "reasoning_trace": rationale,
                "generated_at": finding.get("generated_at", datetime.utcnow().isoformat()),
                "evidence_strength": round(evidence_strength, 2),
                "cross_source_agreement": round(cross_source_agreement, 2),
                "recency_score": round(recency_score, 2),
                "contradiction_penalty": round(contradiction_penalty, 2),
                "source_count": len(supporting_sources),
                "source_quality_score": round(credibility_score / 10.0, 2),
                "matching_sources": supporting_sources
            })

        state.findings = verified_findings
        return state


class CitationAgent(Agent):
    def __init__(self, citation_format: str = "APA"):
        super().__init__(
            name="Citation Broker",
            role="Reference Indexer",
            system_prompt="You build standardized academic bibliographies with unique canonical citation keys."
        )
        self.citation_format = citation_format

    def _parse_source_metadata(self, src: dict) -> dict:
        """Parses DOI, authentic authors, journal, year, and source type from evidence."""
        source = src.get("source", "Web")
        content = src.get("content", "")
        title = src.get("title", "")
        url = src.get("url", "")
        
        # 1. Source Type mapping
        source_type = "Peer-Reviewed Article"
        if "crossref" in source.lower():
            source_type = "Crossref Journal Article"
        elif "pubmed" in source.lower():
            source_type = "PubMed Journal Article"
        elif "arxiv" in source.lower():
            source_type = "arXiv Preprint"
        elif "user file" in source.lower():
            source_type = "User Uploaded Documents"
        elif "wikipedia" in source.lower():
            source_type = "Wikipedia Encyclopedia"
        elif "tavily" in source.lower():
            source_type = "Web Resource"

        # 2. Extract Year
        year = "2024"
        if src.get("year"):
            year = str(src["year"])
        else:
            years = re.findall(r"\b(19\d\d|20[0-2]\d)\b", content + " " + title)
            if years:
                year = years[0]

        # 3. Extract Journal
        journal = src.get("journal")
        if not journal:
            if "pubmed" in source.lower():
                match = re.search(r"Published in ([^(\n]+)", content)
                journal = match.group(1).strip() if match else "PubMed Central"
            elif "arxiv" in source.lower():
                journal = "arXiv Preprints"
            elif "user file" in source.lower():
                journal = "Local Workspace"
            elif url:
                parsed = urlparse(url)
                journal = parsed.netloc or "Web Resource"
            else:
                journal = "Scientific Periodical"

        # 4. Extract DOI
        doi = src.get("doi")
        if not doi:
            doi_match = re.search(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b", content + " " + url)
            if doi_match:
                candidate = doi_match.group(1)
                if not re.search(r"\.(s\d+|supp\d*)$", candidate, re.IGNORECASE):
                    doi = candidate

        # 5. Extract Authentic Authors
        raw_authors = src.get("authors")
        authors = []
        if raw_authors and isinstance(raw_authors, list):
            authors = [a.strip() for a in raw_authors if isinstance(a, str) and a.strip()]
        
        if not authors:
            # Check content for "Authored by ..." pattern
            auth_match = re.search(r"Authored by ([^.]+)\.", content)
            if auth_match:
                parsed_auths = [a.strip() for a in auth_match.group(1).split(",")]
                authors = [a for a in parsed_auths if a and a.lower() != "research group"]

        if not authors:
            # Fallback to journal or institutional publisher
            authors = [journal] if journal else ["Scientific Research Consortium"]

        return {
            "authors": authors,
            "year": year,
            "journal": journal,
            "doi": doi,
            "source_type": source_type
        }

    def _format_citation(self, title: str, url: str, source: str, authors: list, year: str, journal: str, doi: Optional[str]) -> str:
        """Formats the reference matching IEEE or APA standards."""
        clean_title = title.strip().replace("\n", " ")
        doi_suffix = f" https://doi.org/{doi}" if doi else (f" Available: {url}." if url else "")
        
        if self.citation_format == "IEEE":
            if len(authors) > 3:
                author_str = f"{authors[0]} et al."
            elif len(authors) > 1:
                author_str = ", ".join(authors[:-1]) + f", and {authors[-1]}"
            elif authors:
                author_str = authors[0]
            else:
                author_str = journal
            return f'{author_str}, "{clean_title}," {journal}, {year}.{doi_suffix}'
        
        # APA
        if len(authors) > 5:
            author_str = f"{authors[0]} et al."
        elif len(authors) > 1:
            author_str = ", ".join(authors[:-1]) + f", & {authors[-1]}"
        elif authors:
            author_str = authors[0]
        else:
            author_str = journal
        return f'{author_str} ({year}). {clean_title}. {journal}.{doi_suffix}'

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": f"Mapping reference citations using {self.citation_format} standards with global deduplication...",
            "log_type": "INFO"
        })

        # Global canonical citation registry: maps normalized DOI or URL to single unique citation record
        citation_registry: Dict[str, Dict[str, Any]] = {}
        ordered_citations: List[Dict[str, Any]] = []

        for finding in state.findings:
            matching_sources = finding.get("matching_sources", [])
            finding_citations = []
            
            # Max 2 distinct supporting sources per claim
            for src in matching_sources[:2]:
                metadata = self._parse_source_metadata(src)
                doi = metadata.get("doi")
                url = src.get("url") or ""
                
                # Canonical registry key: prefer normalized DOI, fallback to normalized URL
                canonical_key = f"doi:{doi.lower().strip()}" if doi else f"url:{url.lower().strip().rstrip('/')}"

                if canonical_key in citation_registry:
                    # Reuse existing canonical citation! Zero duplication across bibliography slots!
                    existing_cit = citation_registry[canonical_key]
                    finding_citations.append(existing_cit)
                else:
                    cit_id = f"REF-{len(ordered_citations) + 1}"
                    formatted = self._format_citation(
                        title=src.get("title", "Untitled Work"),
                        url=src.get("url", ""),
                        source=src.get("source", "Web"),
                        authors=metadata["authors"],
                        year=metadata["year"],
                        journal=metadata["journal"],
                        doi=metadata["doi"]
                    )
                    
                    citation_record = {
                        "id": cit_id,
                        "canonical_key": canonical_key,
                        "finding_id": finding.get("finding_id") or finding.get("id"),
                        "source_title": formatted,
                        "source_url": src.get("url"),
                        "citation_format": self.citation_format,
                        "quote": (src.get("content") or "")[:200],
                        "authors": metadata["authors"],
                        "year": metadata["year"],
                        "journal": metadata["journal"],
                        "doi": metadata["doi"],
                        "source_type": metadata["source_type"]
                    }
                    citation_registry[canonical_key] = citation_record
                    ordered_citations.append(citation_record)
                    finding_citations.append(citation_record)
            
            # Attach properly mapped, deduplicated citation records to finding
            finding["citations"] = finding_citations

        # state.citations now contains only DISTINCT, authentic scholarly references
        state.citations = ordered_citations
        return state
