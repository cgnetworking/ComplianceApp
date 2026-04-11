# Secure Development and Change Management Policy

| Document Control | Value |
| --- | --- |
| Document ID | POL-08 |
| Document Type | Policy |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Establish secure development lifecycle requirements, change control, testing expectations, architecture principles, and protection of source code and environments.

## 2. Scope
Applies to internally developed software, infrastructure as code, GitLab repositories, development and test environments, release pipelines, and production deployments.

## 3. Authority and Compliance
This policy is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Managers shall ensure that personnel within their areas of responsibility comply with the requirements of this document.
- All workers, contractors, and third parties in scope shall comply with the requirements defined in this document.

## 5. Policy Requirements
### 5.1 Secure Development Requirements
- Security requirements shall be defined for applications, services, APIs, infrastructure components, and significant design changes before implementation.
- Secure architecture principles, threat-informed design, secure coding standards, peer review, and security testing shall be integrated into the SDLC.
- Access to source code repositories shall be restricted to authorized personnel and monitored.

### 5.2 Environment and Test Control
- Development, test, and production environments shall be separated by accounts, permissions, or equivalent technical controls.
- Real customer data shall not be used in non-production environments. Test data shall be synthetic or sanitized where needed.
- Audit or assessment activities against production systems shall be planned to avoid service disruption.

### 5.3 Change Management
- Production changes shall require documented approval, risk consideration, testing evidence, rollback planning, and post-implementation validation.
- Emergency changes shall be logged, approved retrospectively, and reviewed for lessons learned.

### 5.4 Secure Development Lifecycle Requirements
- Security requirements shall be identified during planning, design, development, testing, release, and maintenance activities.
- Design reviews shall consider trust boundaries, authentication, authorization, cryptography, logging, error handling, dependency risk, and exposure of secrets or sensitive data.
- Source code repositories, pipelines, and deployment tooling shall enforce branch protection, peer review, change traceability, and restricted administrative access.

### 5.5 Development and Change Control Requirements
- Developers shall follow secure coding practices, manage third-party components responsibly, and remediate identified defects based on risk.
- Development, test, and production environments shall remain logically or physically separated, with controlled movement of code, configuration, and data between them.
- Security testing, rollback planning, emergency change handling, and controlled audit or assessment activity shall be required before production-impacting work is closed.

## 6. Related Documents
- PR-08 - Secure Development Standard
- PR-09 - Change Management Procedure
- POL-05 - Operations Security, Monitoring and Vulnerability Management Policy
- POL-06 - Network and Infrastructure Security Policy

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
