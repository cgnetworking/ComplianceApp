# Access Control and Identity Management Policy

| Document Control | Value |
| --- | --- |
| Document ID | POL-02 |
| Document Type | Policy |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Define how identities are created, authenticated, authorized, reviewed, and removed across the scoped environment.

## 2. Scope
Applies to Entra SSO, Microsoft 365, Azure, GitLab, Jira, Confluence, Fortigate VPN, privileged accounts, source code, and administrative tooling.

## 3. Authority and Compliance
This policy is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Managers shall ensure that personnel within their areas of responsibility comply with the requirements of this document.
- All workers, contractors, and third parties in scope shall comply with the requirements defined in this document.

## 5. Policy Requirements
### 5.1 Identity and Authentication Requirements
- All workforce identities shall be unique, centrally managed where possible, and linked to a documented business need.
- MFA shall be enforced for Microsoft 365, Azure, GitLab, Atlassian services, Fortigate VPN, and all privileged administration.
- Authentication secrets shall be protected, rotated when compromise is suspected, and never shared through unsecured channels.

### 5.2 Access Authorization
- Access shall follow least privilege and role-based assignment where practical.
- Privileged access shall be limited to named administrators, approved by management, and periodically reviewed.
- Source code write access, production deployment rights, and security tooling administration shall be restricted and monitored.

### 5.3 Lifecycle and Review
- Joiner, mover, leaver actions shall be completed through a documented workflow with manager approval.
- User access shall be reviewed at least quarterly and privileged access at least quarterly.
- Access to utility programs, shells, and direct production administration shall be restricted to authorized administrators only.
- Installation of software on production systems and company endpoints shall be limited to approved mechanisms and authorized personnel.

### 5.4 Provisioning and Authentication Controls
- Access shall be provisioned only from authorized requests tied to an approved role, business need, and data sensitivity.
- Separate privileged administrator accounts shall be used for administrative activities where technically feasible.
- Dormant, generic, shared, emergency, and service accounts shall be tightly controlled, assigned an owner, reviewed regularly, and disabled when no longer required.
- Strong authentication settings shall be enforced for enrollment, reset, recovery, and remote access workflows.

### 5.5 Authorization and Recertification Controls
- Privileged access, source code write access, production access, and security-tool administration shall require explicit approval and heightened review.
- Access recertification shall validate continued need, privilege level, segregation of duties, and removal of excessive entitlements.
- Software installation rights shall be restricted to approved mechanisms, managed catalogs, or authorized administrators.

## 6. Related Documents
- PR-01 - Joiner, Mover, Leaver and Access Review Procedure
- PR-03 - Mobile BYOD and App Protection Standard
- PR-09 - Change Management Procedure

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
