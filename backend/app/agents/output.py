from backend.app.agents.base import Agent, AgentState

class OutputAgent(Agent):
    def __init__(self):
        super().__init__(
            name="Report Synthesis Agent",
            role="Technical Writer",
            system_prompt="You compile structured academic research reports from findings, debates, and citations."
        )

    async def execute(self, state: AgentState) -> AgentState:
        state.logs.append({
            "agent_name": self.name,
            "agent_role": self.role,
            "message": "Assembling finalized Markdown research report...",
            "log_type": "INFO"
        })

        # Build table of findings
        findings_table = [
            "| ID | Synthesized Claim | Verification Status | Confidence | Sources | Quality |",
            "|:---|:---|:---|:---|:---|:---|"
        ]
        for idx, f in enumerate(state.findings):
            citations_keys = [c.get("id") for c in f.get("citations", [])]
            ref_str = ", ".join(f"[{k}]" for k in citations_keys) if citations_keys else "N/A"
            findings_table.append(
                f"| {idx+1} | {f.get('claim')} {ref_str} | **{f.get('verification_status')}** | "
                f"{f.get('confidence_score')}% | {f.get('source_count')} | {f.get('source_quality_score')}/10 |"
            )
        findings_table_str = "\n".join(findings_table)

        # Build detailed sections
        detailed_findings = []
        for idx, f in enumerate(state.findings):
            detailed_findings.append(
                f"### Finding {idx+1}: {f.get('claim')}\n"
                f"- **Verification Status**: {f.get('verification_status')}\n"
                f"- **Confidence Score**: {f.get('confidence_score')}%\n"
                f"- **Consensus Rationale**: {f.get('consensus_rationale')}\n"
            )
        detailed_findings_str = "\n".join(detailed_findings)

        # Build debates section
        debate_str = ""
        if state.debates:
            debate_str += "## 3. Contradiction & Debate Resolutions\n\n"
            for d in state.debates:
                debate_str += (
                    f"### Conflict: {d.get('debate_summary')}\n"
                    f"- **Resolution Rationale**: {d.get('consensus_claim')}\n"
                    f"- **Resolved Confidence**: {d.get('resolved_confidence')}%\n\n"
                )

        # Build references bibliography
        references = ["| Key | Reference Details | Link |", "|:---|:---|:---|"]
        for c in state.citations:
            references.append(
                f"| {c.get('id')} | {c.get('source_title')} | [Source Link]({c.get('source_url') or '#'}) |"
            )
        references_str = "\n".join(references)

        # Final layout assembly
        report = (
            f"# Intellex Research Intelligence Synthesis\n\n"
            f"**Research Target**: {state.query}\n"
            f"**Status**: Factual Verification Audited\n\n"
            f"## 1. Executive Summary Table\n\n"
            f"{findings_table_str}\n\n"
            f"## 2. In-Depth Claims Analysis\n\n"
            f"{detailed_findings_str}\n"
            f"{debate_str}"
            f"## 4. Bibliography References\n\n"
            f"{references_str}\n"
        )

        state.report_markdown = report
        return state
