# Spec Delta

## Purpose

Coordinate a private phone capture with a computer question attempt so students can safely submit handwritten answers across devices using the same account.

## ADDED Requirements

### Requirement: Owned scan request and mobile discovery
The system SHALL create a scan request only for the signed-in student's open-ended attempt and SHALL allow only that student to discover, inspect, confirm, upload to, or retry it. Opening the mobile app signed in to the same account SHALL discover pending requests without requiring a pairing link.

#### Scenario: Same account opens the phone app
- **WHEN** a student initiates a scan on the computer and opens the mobile app with the same account
- **THEN** the phone offers the pending request with enough question context to identify its attempt

#### Scenario: Several pending questions
- **WHEN** the student has pending requests for multiple question attempts
- **THEN** the mobile app lets the student select a request by its question and attempt context
- **AND** confirmation and upload apply only to that selected request

#### Scenario: Different or missing account
- **WHEN** another student or an unauthenticated caller attempts to discover or access the request
- **THEN** the system exposes no request or answer data
- **AND** knowing a request identifier does not grant access

### Requirement: Confirm before camera access
The mobile app SHALL ask the student to confirm the selected scan before invoking camera capture or requesting camera permission. Denial or cancellation SHALL leave the answer unsubmitted and provide a way to try again.

#### Scenario: Confirmation accepted
- **WHEN** the student confirms the selected request
- **THEN** the app opens camera capture and requests permission if the platform requires it

#### Scenario: Confirmation declined
- **WHEN** the student declines confirmation
- **THEN** the app does not open the camera or request camera permission
- **AND** no answer is uploaded

#### Scenario: Camera permission denied
- **WHEN** camera access is denied or capture is cancelled
- **THEN** the app explains how to retry and leaves the attempt without a submitted photograph

### Requirement: Review and retake before submission
The mobile app SHALL display a captured photograph for review, SHALL allow retaking it, and SHALL upload only after an explicit submit action.

#### Scenario: Retake the photograph
- **WHEN** the student retakes a photograph on the review screen
- **THEN** the new capture replaces the local preview
- **AND** neither capture is submitted until the student selects submit

### Requirement: Shared status and upload feedback
The computer SHALL display Waiting for phone, Uploading, Answer received, Upload failed, or Request expired as appropriate. Status SHALL be associated with the original attempt and restored after reconnection. Both devices SHALL confirm success only when the answer is durably attached.

#### Scenario: Upload begins and finishes
- **WHEN** the student submits the reviewed photograph
- **THEN** the computer displays Uploading while the transfer is active
- **AND** displays Answer received with the attachment after successful completion

#### Scenario: Network interruption
- **WHEN** upload or persistence fails
- **THEN** the system displays Upload failed once the failure is detected
- **AND** the phone retains the preview for retry while its page remains open
- **AND** the computer resumes authoritative status checks after reconnection

### Requirement: Expiry and safe retries
The system SHALL expire unused scan requests after 15 minutes and reject new submissions to expired or superseded requests. The student SHALL be able to retry a failed upload or replace an expired request for the same attempt. Repeated or concurrent submissions SHALL create at most one answer attachment for a request.

#### Scenario: Expired request
- **WHEN** the student submits to a request after its expiry
- **THEN** the system rejects the upload and offers a fresh request for the same attempt
- **AND** the replacement invalidates the expired request

#### Scenario: Upload retry after failure
- **WHEN** the student retries a failed upload on an unexpired request
- **THEN** the system retries attachment to the original attempt without creating a new attempt

#### Scenario: Success response was lost
- **WHEN** the phone repeats a submission that already completed
- **THEN** the system reports the existing successful attachment without duplicating it

#### Scenario: Concurrent or superseded upload
- **WHEN** two phones submit to one request or an older request finishes after replacement
- **THEN** at most one valid attachment is committed
- **AND** the obsolete submission cannot overwrite the accepted answer

### Requirement: Answer capture is independent of the solver
The system SHALL support answer scanning without an AI solver key. The existing photographed-problem solving flow SHALL remain usable with its established configuration and behavior.

#### Scenario: AI is not configured
- **WHEN** a signed-in student requests an answer scan without an AI solver key configured
- **THEN** scan capture and attachment remain available when answer storage is configured
