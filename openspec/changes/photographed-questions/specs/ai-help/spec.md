## ADDED Requirements

### Requirement: Photographing a question
A student SHALL photograph a question with the phone's 4-digit code request or from the device, at most 5 a day. The AI SHALL read it at once and keep its answer and steps without showing them; an unreadable photo SHALL say so and offer another photo. Without the AI the feature SHALL be hidden.

#### Scenario: Read
- **WHEN** a student sends a photo of "פתרו: 2x + 3 = 11" from the phone
- **THEN** the sheet shows the question with a box "x =" and a suggested skill, and nothing of its answer

### Requirement: Classifying and solving
The AI SHALL suggest one of the subject's skills or "external", and the student MAY change it before handing in. The student SHALL solve the question on the board and hand it in at most 3 times; the AI SHALL give a grade from 0 to 100, a verdict and feedback on the way, and then the full solution SHALL show.

#### Scenario: Graded
- **WHEN** the student writes the way on the board and hands in
- **THEN** a grade out of 100, a verdict and feedback appear, with the full solution folded

### Requirement: The class's bank
After its first check, a photographed question SHALL wait for the class's teacher, who MAY fix its wording, answer and skill and SHALL approve it into the class's bank or reject it. The class's other students SHALL solve approved questions from the same sheet; such a copy SHALL NOT go to the teacher again.

#### Scenario: Approved
- **WHEN** the teacher approves a photographed question
- **THEN** the class's other students see it under "שאלות מהכיתה" and can solve it
