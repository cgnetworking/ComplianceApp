# Secure Development Standard

| Document Control | Value |
| --- | --- |
| Document ID | PR-08 |
| Document Type | Standard |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Set minimum secure development, review, testing, and release requirements for internally developed software.

## 2. Scope
Applies to source code, build pipelines, infrastructure as code, scripts, and application releases.

## 3. Authority and Compliance
This standard is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Managers shall ensure that personnel within their areas of responsibility comply with the requirements of this document.
- All workers, contractors, and third parties in scope shall comply with the requirements defined in this document.

## 5. Control Requirements
### 5.1 Minimum Requirements
- Repositories shall enforce role-based access, branch protection, and peer review before merge to protected branches.
- Developers shall use secure coding guidance appropriate to the language and framework in use.
- Static analysis, dependency review, and security testing shall be integrated into the development workflow where feasible.
- Secrets shall not be stored in source code or pipeline configuration in plaintext.

## 6. Related Documents
- POL-08 - Secure Development and Change Management Policy
- PR-09 - Change Management Procedure

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
