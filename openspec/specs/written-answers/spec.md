# written-answers Specification

## Purpose
Lets a student hand in a handwritten or drawn solution as a picture from whatever device they have, and keeps those pictures private and only as long as needed.

## Requirements

### Requirement: Handing in a written answer
A written answer SHALL be handed in as a picture: from the board, or by photographing paper. On a phone the camera opens; on a computer the student uploads an image or asks their own phone to take the photo.

#### Scenario: Photo on a phone
- **WHEN** a student on a phone chooses to photograph their answer
- **THEN** the camera opens and the picture is handed in

### Requirement: Photo request to the phone
A computer SHALL be able to create a photo request for one answer. The student's phone, signed in to the same account, SHALL show the request with a 4-digit code that matches the one on the computer. The computer SHALL show the state: waiting for the phone, uploading, received, failed, expired, or replaced by a newer request.

#### Scenario: Matching code
- **WHEN** a student asks for a photo from the computer and opens the app on their phone
- **THEN** the phone shows the same 4-digit code as the computer and a camera button

#### Scenario: Newer request
- **WHEN** a student makes a second photo request for the same answer
- **THEN** the first one shows as replaced

### Requirement: Push notification to the phone
A phone SHALL be able to turn notifications on. When the computer creates a photo request, the phone SHALL be notified even if the app is closed; tapping the notification SHALL open the request. Only phones subscribe; a subscription the push service no longer knows SHALL be deleted.

#### Scenario: App closed
- **WHEN** a student asks for a photo from the computer while the app is closed on their phone
- **THEN** the phone shows a notification that opens the request

### Requirement: Private pictures
Answer pictures SHALL be kept in private storage tied to the account and read only by the server. Pictures no answer refers to SHALL be removed every hour.

#### Scenario: Direct link
- **WHEN** someone tries to open an answer picture without going through the server
- **THEN** it is refused

### Requirement: Keeping pictures for a school year
Answer pictures SHALL be removed after 31 August of the school year they were handed in; grades and teachers' comments stay. A teacher of the class, a manager or a developer SHALL be able to delete a student's pictures earlier on request.

#### Scenario: New school year
- **WHEN** 1 September comes
- **THEN** last year's answer pictures are gone and their grades remain
