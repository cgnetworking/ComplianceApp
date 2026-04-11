# Network and Infrastructure Security Policy

| Document Control | Value |
| --- | --- |
| Document ID | POL-06 |
| Document Type | Policy |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Define security expectations for networks, remote connectivity, datacenter infrastructure, Azure hosting, redundancy, and secure service design.

## 2. Scope
Applies to Fortigate, Azure networking, colocation network equipment, remote access, segmentation, and network service providers used within the ISMS scope.

## 3. Authority and Compliance
This policy is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Managers shall ensure that personnel within their areas of responsibility comply with the requirements of this document.
- All workers, contractors, and third parties in scope shall comply with the requirements defined in this document.

## 5. Policy Requirements
### 5.1 Network Requirements
- Network security controls shall be designed and maintained for internal, remote access, management, and production traffic paths.
- Critical management networks shall be segregated from user and public-facing networks where technically practical.
- Remote access shall use approved VPN or zero-trust mechanisms, strong authentication, and logging.

### 5.2 Service Protection
- Security requirements for network services shall be documented for Azure, Fortigate, internet connectivity, and the colocation environment.
- Redundancy shall be implemented for critical information processing where business continuity objectives require it.
- Network changes shall follow the formal change management process and be tested before production implementation.

### 5.3 Network Security Requirements
- Network boundaries, trusted zones, management paths, and remote access paths shall be documented and protected by approved security controls.
- Administrative access to network infrastructure shall be limited to authorized personnel using strong authentication and logged sessions where supported.
- Network rules and segmentation changes shall be approved, tested, and reviewed to prevent unintended exposure between user, management, and production environments.

### 5.4 Service Resilience Requirements
- Security requirements, availability expectations, and logging expectations shall be defined for network services and third-party connectivity.
- Redundancy and failover arrangements shall be implemented where required to meet recovery objectives for critical services.
- Provider dependency for datacenter connectivity or cloud networking shall be included in continuity and supplier risk assessments.

## 6. Related Documents
- PR-02 - Datacenter Access and Equipment Handling Procedure
- PR-07 - Vulnerability, Patch and Configuration Management Procedure
- PR-09 - Change Management Procedure
- POL-11 - Business Continuity, Backup and Disaster Recovery Policy

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
