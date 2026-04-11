# Cryptography, Privacy and Records Protection Policy

| Document Control | Value |
| --- | --- |
| Document ID | POL-07 |
| Document Type | Policy |
| Classification | Internal Use |
| Owner | Head of IT |
| Approver | CTO |
| Review Frequency | Annual |
| Version | 1.0 |
| Effective Date | 2026-04-10 |

## 1. Purpose
Define requirements for encryption, key handling, records protection, legal and contractual compliance, privacy, and protection against data leakage.

## 2. Scope
Applies to information stored or transmitted in Microsoft 365, Azure, GitLab, endpoint devices, and any controlled repository containing business or employee information.

## 3. Authority and Compliance
This policy is issued under the authority of the CTO. Compliance with this document is mandatory for all personnel, contractors, and third parties within its scope. Non-compliance shall be addressed through management action, corrective action, contractual enforcement, or disciplinary measures as applicable.

## 4. Roles and Responsibilities
- The CTO is the document approver and provides executive authorization for this document.
- The Head of IT is the document owner and is responsible for implementation, maintenance, and periodic review.
- Managers shall ensure that personnel within their areas of responsibility comply with the requirements of this document.
- All workers, contractors, and third parties in scope shall comply with the requirements defined in this document.

## 5. Policy Requirements
### 5.1 Cryptography
- Encryption shall be used for laptops, mobile app data containers, network sessions carrying sensitive data, and sensitive cloud storage where supported.
- Key management responsibilities shall be assigned, and use of vendor-managed key services shall follow documented configuration and access restrictions.

### 5.2 Privacy, Records and Legal Obligations
- Employee personal information shall be protected in accordance with applicable privacy obligations and internal need-to-know principles.
- Records that provide contractual, legal, financial, personnel, or security evidence shall be protected from unauthorized alteration or deletion.
- Intellectual property, licensing, software use rights, and contractual obligations shall be respected and monitored.

### 5.3 Data Leakage Prevention
- Approved DLP, sensitivity labeling, sharing restrictions, and endpoint controls shall be used where supported by Microsoft 365 and other platforms.
- The organization shall prohibit use of real customer data in non-production environments and prefer synthetic or sanitized information for testing.

### 5.4 Cryptographic and Key Management Requirements
- Approved encryption mechanisms shall be used for endpoint storage, administrative access, VPN sessions, and sensitive data at rest or in transit.
- Cryptographic key ownership, storage, rotation, revocation, and recovery responsibilities shall be defined for internally managed and vendor-managed keys.
- Any proposed exception to encryption requirements shall be risk-assessed and explicitly approved.

### 5.5 Privacy, Records and Data Protection Requirements
- Retention, handling, access, and disposal requirements shall be defined for employee information, contractual records, audit records, and security evidence.
- Data loss prevention, sharing restrictions, and information protection settings shall be configured to reduce unauthorized disclosure through email, collaboration tools, mobile devices, and cloud repositories.
- Non-production data sets shall be synthetic or sanitized and shall not expose live customer or sensitive production data without formal approval and protection measures.

## 6. Related Documents
- POL-01 - Asset, Acceptable Use and Information Handling Policy
- POL-02 - Access Control and Identity Management Policy
- POL-08 - Secure Development and Change Management Policy
- PR-03 - Mobile BYOD and App Protection Standard

## 7. Exceptions and Deviations
Any exception, deviation, or temporary waiver from this document shall be documented, risk-assessed, approved by the Head of IT, and authorized by the CTO before implementation unless emergency conditions prevent prior approval.

## 8. Review and Maintenance
This document shall be reviewed at least annually and whenever significant changes occur to the business, technology stack, supplier model, organizational structure, or applicable legal and contractual obligations.
