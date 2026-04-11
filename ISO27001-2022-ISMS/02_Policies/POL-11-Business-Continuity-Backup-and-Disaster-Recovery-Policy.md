# Business Continuity, Backup and Disaster Recovery Policy

| Document Control | Value |
| --- | --- |
| Document ID | POL-11 |
| Document Type | Policy |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Define continuity, backup, recovery, and resilience requirements for the remote-first operating model and supporting technology stack.

## 2. Scope
Applies to Azure services, Microsoft 365, company-owned datacenter systems, identity services, source code repositories, collaboration platforms, and endpoint recovery requirements.

## 3. Authority and Compliance
This policy is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Managers shall ensure that personnel within their areas of responsibility comply with the requirements of this document.
- All workers, contractors, and third parties in scope shall comply with the requirements defined in this document.

## 5. Policy Requirements
### 5.1 Continuity Objectives
- Critical services shall be assigned recovery objectives. Default objectives are RTO 8 hours and RPO 4 hours for Tier 1 production and identity services, RTO 24 hours and RPO 24 hours for Tier 2 internal business systems, and RTO 72 hours and RPO 48 hours for Tier 3 supporting services unless documented otherwise.
- Continuity plans shall consider remote workforce disruption, loss of cloud service availability, colocation outage, cyber incident, and supplier failure.

### 5.2 Backup and Recovery
- Backups shall be enabled for critical data and configuration where supported by the platform or implemented through approved tools.
- Backup success and failure alerts shall be reviewed routinely, and restoration capability shall be tested at least semi-annually for critical systems.
- Redundancy and failover controls shall be implemented where needed to meet defined recovery objectives.

### 5.3 Testing and Review
- Business continuity and disaster recovery exercises shall be performed at least annually, including at least one scenario involving loss of a critical hosted service or site dependency.
- Findings from exercises or actual disruptions shall result in documented corrective actions and plan updates.

### 5.4 Continuity Planning Requirements
- Critical services shall have documented recovery priorities, dependencies, minimum operating requirements, and alternate processing or recovery strategies.
- Continuity plans shall address remote workforce disruption, identity service failure, cloud service degradation, datacenter outage, cyber extortion, and critical supplier failure.
- Continuity roles, emergency contacts, escalation paths, and communication methods shall be documented and periodically validated.

### 5.5 Backup and Recovery Requirements
- Backup scope, schedule, retention, encryption, access restrictions, and restoration testing requirements shall be defined for critical systems and data sets.
- Backup copies shall be protected from unauthorized alteration, deletion, or ransomware impact through segregation or immutable or independent mechanisms where appropriate.
- Recovery exercises shall measure achieved RTO and RPO results, document gaps, and track remediation to closure.

## 6. Related Documents
- PR-04 - Backup Restore and Recovery Test Procedure
- GOV-02 - Risk Assessment and Treatment Methodology
- POL-09 - Supplier and Cloud Security Policy
- TMP-01 - Management Review Minutes Template

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
