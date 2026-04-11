# ISMS Package Overview

| Document Control | Value |
| --- | --- |
| Document ID | README |
| Document Type | Guide |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Provide a navigation guide for the ISO 27001:2022 document package created for a remote-first software company operating company-owned equipment in a colocated datacenter and Azure.

## 2. Scope
This guide covers the full document set, workbooks, templates, and assumptions prepared in this package.

## 3. Authority and Compliance
This guide is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Process participants shall perform the activities defined in this document and retain evidence where required.
- System owners and control owners shall support execution of this document within their assigned environments.

## 5. Guidance
### 5.1 Package Contents
- 01_Governance contains ISMS governance documents, the Statement of Applicability, and the annual review schedule.
- 02_Policies contains the formal policy suite used to address applicable Annex A controls.
- 03_Procedures_and_Standards contains operating procedures and technical standards referenced by the policies.
- 04_Registers_and_Templates contains practical templates for evidence generation and recurring review activities.
- ISO27001_2022_Control_Mapping.xlsx provides the Annex A control mapping, implementation status, document mapping, and document register in Excel format.
- ISO27001_2022_Review_Schedule.xlsx provides the annual review schedule and recurring review checklist in Excel format.

### 5.2 Assumptions
- The organization is a fully remote software company with approximately 300 workers in scope.
- The organization uses Microsoft 365, Azure, GitLab, Jira, Confluence, CrowdStrike, Intune, Fortigate, and Entra SSO with MFA.
- Company laptops are managed through Intune and protected by CrowdStrike. Mobile devices are BYOD and restricted through app protection policies.
- A small office is used for shipments only, with no production equipment hosted there. Printing is prohibited.
- Company-owned infrastructure is installed in a third-party colocation facility. Physical visits are limited to authorized personnel.
- No customer personal information is handled. Employee and business information remain in scope.

### 5.3 Use Guidance
- Replace assumptions that require organization-specific wording before formal adoption.
- Run the annual schedule and retain the generated evidence in a controlled repository.
- Keep the Statement of Applicability aligned with the risk assessment, supplier inventory, and current architecture.

## 6. Related Documents
- GOV-01 - Information Security Governance Policy
- GOV-02 - Risk Assessment and Treatment Methodology
- GOV-03 - Statement of Applicability
- GOV-04 - Annual Review Schedule and Checklist

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
